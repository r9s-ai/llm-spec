"""pytest configuration and fixtures."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from llm_spec.providers.anthropic import AnthropicClient
    from llm_spec.providers.gemini import GeminiClient
    from llm_spec.providers.openai import OpenAIClient
    from llm_spec.providers.xai import XAIClient


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require real API keys",
    )
    config.addinivalue_line(
        "markers",
        "expensive: marks tests that consume significant API credits",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--keep-temp",
        action="store_true",
        default=False,
        help="Keep temporary files after tests",
    )
    parser.addoption(
        "--run-expensive",
        action="store_true",
        default=False,
        help="Run expensive integration tests (e.g. image generation)",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Prepare environment at the start of the session."""
    from llm_spec.core.config import PROJECT_ROOT

    temp_dir = PROJECT_ROOT / "temp"
    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    """Capture test results for statistics."""
    outcome = yield
    report = outcome.get_result()

    # Only record call phase (actual test execution) results
    if report.when == "call":
        # Save test outcome to item for later use
        item.test_outcome = report.outcome  # 'passed', 'failed', 'skipped'

        # For failed tests, try to extract request parameters from exception
        if report.outcome == "failed" and report.longrepr:
            # Store failure info for parameter extraction
            item.test_failed = True
            item.test_exception = getattr(call, 'excinfo', None)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Save collected reports at the end of the test session."""
    from llm_spec.core.config import get_config
    from llm_spec.core.report import get_collector, reset_collector

    config = get_config().report
    collector = get_collector()

    # Collect pytest test outcomes by endpoint
    # Map test class names to endpoint paths (using slash notation to match ValidationReport.endpoint)
    endpoint_mapping = {
        "TestChatCompletions": ("openai", "chat/completions"),
        "TestResponses": ("openai", "responses"),
        "TestEmbeddings": ("openai", "embeddings"),
        "TestAudioSpeech": ("openai", "audio/speech"),
        "TestAudioTranscriptions": ("openai", "audio/transcriptions"),
        "TestAudioTranslations": ("openai", "audio/translations"),
        "TestImageGeneration": ("openai", "images/generations"),
        "TestImageEdit": ("openai", "images/edits"),
        # Add more mappings as needed
    }

    # Collect test outcomes grouped by endpoint
    test_outcomes_by_endpoint: dict[tuple[str, str], list[str]] = {}

    for item in session.items:
        # Get test class name
        class_name = item.parent.name if hasattr(item.parent, 'name') else None
        if not class_name or class_name not in endpoint_mapping:
            continue

        provider_endpoint = endpoint_mapping[class_name]

        if hasattr(item, 'test_outcome'):
            if provider_endpoint not in test_outcomes_by_endpoint:
                test_outcomes_by_endpoint[provider_endpoint] = []
            test_outcomes_by_endpoint[provider_endpoint].append(item.test_outcome)

    # Pass test outcomes to collector
    collector.set_test_outcomes(test_outcomes_by_endpoint)

    # Only save if we have reports and JSON output is enabled
    if collector.count > 0 and config.format in ("json", "both"):
        saved_paths = collector.save()
        print(f"\\nValidation reports saved ({len(saved_paths)} files):")
        for path in saved_paths:
            print(f"  - {path}")
        print(f"Total: {collector.count} tests collected")

    # Print parameter support matrix for terminal output

    # Print parameter support matrix for terminal output
    if collector.count > 0 and config.format in ("terminal", "both"):
        collector.print_all_parameter_support_matrices()

    # Reset collector for next session
    reset_collector()


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Store current test name before test runs."""
    from llm_spec.core.report import set_current_test_name
    set_current_test_name(item.name)


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    """Clear current test name after test finishes."""
    from llm_spec.core.report import set_current_test_name
    set_current_test_name(None)


@pytest.fixture
def temp_dir(request: pytest.FixtureRequest) -> Generator[Path, None, None]:
    """Create a temporary directory for test artifacts.

    The directory is automatically cleaned up after the test.

    Yields:
        Path to the temporary directory
    """
    from llm_spec.core.config import PROJECT_ROOT

    temp_root = PROJECT_ROOT / "temp"
    if not temp_root.exists():
        temp_root.mkdir(parents=True, exist_ok=True)

    tmp_path = Path(tempfile.mkdtemp(dir=temp_root, prefix="test_"))
    yield tmp_path

    # Cleanup after test unless --keep-temp is specified
    if not request.config.getoption("--keep-temp"):
        import shutil
        shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def openai_client() -> OpenAIClient:
    """Create an OpenAI client for testing.

    Uses API key from environment variable or config file.
    """
    from llm_spec.core.config import get_config
    from llm_spec.providers.openai import OpenAIClient

    api_key = os.environ.get("OPENAI_API_KEY") or get_config().openai.api_key
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set (env or config)")
    return OpenAIClient()


@pytest.fixture
def anthropic_client() -> AnthropicClient:
    """Create an Anthropic client for testing.

    Uses API key from environment variable or config file.
    """
    from llm_spec.core.config import get_config
    from llm_spec.providers.anthropic import AnthropicClient

    api_key = os.environ.get("ANTHROPIC_API_KEY") or get_config().anthropic.api_key
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set (env or config)")
    return AnthropicClient()


@pytest.fixture
def gemini_client() -> GeminiClient:
    """Create a Gemini client for testing.

    Uses API key from environment variable or config file.
    """
    from llm_spec.core.config import get_config
    from llm_spec.providers.gemini import GeminiClient

    api_key = os.environ.get("GEMINI_API_KEY") or get_config().gemini.api_key
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set (env or config)")
    return GeminiClient()


@pytest.fixture
def xai_client() -> XAIClient:
    """Create an xAI client for testing.

    Uses API key from environment variable or config file.
    """
    from llm_spec.core.config import get_config
    from llm_spec.providers.xai import XAIClient

    api_key = os.environ.get("XAI_API_KEY") or get_config().xai.api_key
    if not api_key:
        pytest.skip("XAI_API_KEY not set (env or config)")
    return XAIClient()


@pytest.fixture
def run_expensive(pytestconfig: pytest.Config) -> bool:
    """Fixture to check if expensive tests should be run.

    Returns:
        True if --run-expensive was passed, False otherwise
    """
    return bool(pytestconfig.getoption("--run-expensive"))


# =============================================================================
# Baseline Parameters for Single-Parameter Testing
# =============================================================================


@pytest.fixture
def baseline_params() -> dict:
    """Baseline parameters for chat completion tests.

    Contains only the minimum required parameters:
    - model: The model to use
    - messages: A simple test message
    - max_tokens: Explicitly set to control response length (50 tokens)

    This fixture is used for single-parameter testing where each test
    adds exactly one new parameter on top of this baseline.
    """

    return {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say 'test'."}],
        "max_tokens": 50,
    }


@pytest.fixture
def baseline_embedding_params() -> dict:
    """Baseline parameters for embeddings tests.

    Contains only the minimum required parameters:
    - model: The embedding model to use
    - input_text: A simple test string

    This fixture is used for single-parameter testing where each test
    adds exactly one new parameter on top of this baseline.
    """

    return {
        "model": "text-embedding-3-small",
        "input_text": "Hello, world!",
    }


@pytest.fixture
def baseline_responses_params() -> dict:
    """Baseline parameters for responses endpoint tests.

    Contains only the minimum required parameters:
    - model: The model to use
    - input_text: A simple test string
    - max_output_tokens: Explicitly set to control response length (50 tokens)

    This fixture is used for single-parameter testing where each test
    adds exactly one new parameter on top of this baseline.
    """
    return {
        "model": "gpt-4o-mini",
        "input_text": "Say 'test'.",
        "max_output_tokens": 50,
    }


@pytest.fixture
def baseline_speech_params() -> dict:
    """Baseline parameters for speech (TTS) tests."""
    return {
        "model": "gpt-4o-mini-tts",
        "input_text": "Hello, world!",
        "voice": "alloy",
    }


@pytest.fixture
def audio_file_en(openai_client: OpenAIClient) -> Path:
    """Fixture that provides an English audio file for testing.

    Uses cached audio from test_assets/ if available, generates on first run.
    """
    from llm_spec.core.config import PROJECT_ROOT

    cached_path = PROJECT_ROOT / "test_assets/audio/hello_en.mp3"
    if cached_path.exists():
        return cached_path

    # First-time generation
    cached_path.parent.mkdir(parents=True, exist_ok=True)
    audio_data, _ = openai_client.validate_speech(
        input_text="Hello, this is a test of the emergency broadcast system.",
        model="gpt-4o-mini-tts",
        voice="alloy",
    )

    cached_path.write_bytes(audio_data)
    return cached_path


@pytest.fixture
def audio_file_zh(openai_client: OpenAIClient) -> Path:
    """Fixture that provides a Chinese audio file for testing.

    Used for testing translations (Chinese to English).
    Uses cached audio from test_assets/ if available, generates on first run.
    """
    from llm_spec.core.config import PROJECT_ROOT

    cached_path = PROJECT_ROOT / "test_assets/audio/hello_zh.mp3"
    if cached_path.exists():
        return cached_path

    # First-time generation
    cached_path.parent.mkdir(parents=True, exist_ok=True)
    audio_data, _ = openai_client.validate_speech(
        input_text="你好，这是一个测试。",
        model="gpt-4o-mini-tts",
        voice="alloy",
    )

    cached_path.write_bytes(audio_data)
    return cached_path
@pytest.fixture
def baseline_image_params() -> dict:
    """Baseline parameters for image generation tests.

    Contains only the minimum required parameters:
    - prompt: A simple description
    - model: dall-e-2 (default)
    - n: 1
    - size: 256x256 (for speed and cost)
    """
    return {
        "prompt": "A simple red circle.",
        "model": "dall-e-2",
        "n": 1,
        "size": "256x256",
    }


@pytest.fixture
def test_image_png(openai_client: OpenAIClient) -> Path:
    """Fixture that provides a test PNG image for image editing tests.

    Uses cached image from test_assets/ if available, generates on first run.
    """
    from llm_spec.core.config import PROJECT_ROOT

    cached_path = PROJECT_ROOT / "test_assets/images/test_base.png"
    if cached_path.exists():
        return cached_path

    # First-time generation
    cached_path.parent.mkdir(parents=True, exist_ok=True)
    image_bytes, _ = openai_client.generate_image(
        prompt="A simple white square on black background",
        model="dall-e-2",
        n=1,
        size="256x256",
    )

    cached_path.write_bytes(image_bytes)
    return cached_path


@pytest.fixture
def baseline_image_edit_params(test_image_png: Path) -> dict:
    """Baseline parameters for image edit tests.

    Contains only the minimum required parameters:
    - image_path: Path to test image
    - prompt: Edit description
    - model: dall-e-2 (for speed and cost)
    - size: 256x256 (matches input image size)
    """
    return {
        "image_path": test_image_png,
        "prompt": "Add a blue border",
        "model": "dall-e-2",
        "size": "256x256",
    }
