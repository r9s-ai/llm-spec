"""pytest configuration and fixtures."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest

if TYPE_CHECKING:
    from llm_spec.providers.openai import OpenAIClient
    from llm_spec.providers.anthropic import AnthropicClient
    from llm_spec.providers.gemini import GeminiClient
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
        "--run-expensive",
        action="store_true",
        default=False,
        help="Run expensive tests (image generation, etc.)",
    )


@pytest.fixture
def run_expensive(request: pytest.FixtureRequest) -> bool:
    """Check if expensive tests should run."""
    return request.config.getoption("--run-expensive")


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test artifacts.

    The directory is automatically cleaned up after the test.

    Yields:
        Path to the temporary directory
    """
    tmp_path = Path(tempfile.mkdtemp(prefix="llm_spec_test_"))
    yield tmp_path
    # Cleanup after test
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
