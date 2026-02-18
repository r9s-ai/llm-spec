"""Pytest fixtures for testing"""

import json
import os
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest
import respx

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig, load_config
from llm_spec.logger import RequestLogger
from tests.integration.mock_loader import MockDataLoader


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom pytest command line options."""
    parser.addoption(
        "--mock",
        action="store_true",
        default=False,
        help="Run tests with mock data instead of real API calls",
    )


@pytest.fixture(scope="session")
def mock_mode(request: pytest.FixtureRequest) -> bool:
    """Determine if mock mode is enabled.

    Priority: command line argument > environment variable

    Returns:
        True if mock mode is enabled, False otherwise
    """
    return request.config.getoption("--mock", default=False) or os.getenv("MOCK_MODE", "0") == "1"


@pytest.fixture(scope="session")
def respx_mock(mock_mode: bool) -> Generator[respx.MockRouter | None, None, None]:
    """Provide respx mock context for HTTP mocking.

    Only active when mock_mode is enabled.

    Yields:
        respx.MockRouter if mock mode is enabled, None otherwise
    """
    if not mock_mode:
        yield None
        return

    with respx.mock as router:
        yield router


@pytest.fixture(scope="session")
def mock_data_loader() -> MockDataLoader:
    """Create mock data loader instance.

    Returns:
        MockDataLoader instance pointing to tests/integration/mocks/
    """
    return MockDataLoader(base_dir=Path(__file__).parent / "mocks")


@pytest.fixture(scope="session")
def config() -> AppConfig:
    """Load config."""
    return load_config("llm-spec.toml")


@pytest.fixture(scope="session")
def openai_client(
    config: AppConfig, mock_mode: bool, mock_data_loader: MockDataLoader
) -> Generator[OpenAIAdapter, None, None]:
    """Create an OpenAI client adapter.

    Supports both real API calls and mock mode.
    In mock mode, attaches mock loader to adapter for route setup.
    """
    provider_config = config.get_provider_config("openai")

    # Logger
    logger = RequestLogger(config.log)

    # HTTP client (transport only)
    http_client = HTTPClient(default_timeout=provider_config.timeout)

    # Adapter holds the logger for runner-level logging
    adapter = OpenAIAdapter(provider_config, http_client, logger)

    # Attach mock loader in mock mode (for test setup)
    if mock_mode:
        adapter._mock_loader = mock_data_loader  # type: ignore[attr-defined]
        adapter._mock_provider = "openai"  # type: ignore[attr-defined]

    yield adapter

    # Close connection pool at session end
    http_client.close()


@pytest.fixture(scope="session")
def anthropic_client(
    config: AppConfig, mock_mode: bool, mock_data_loader: MockDataLoader
) -> Generator[AnthropicAdapter, None, None]:
    """Create an Anthropic client adapter.

    Supports both real API calls and mock mode.
    """
    provider_config = config.get_provider_config("anthropic")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter = AnthropicAdapter(provider_config, http_client, logger)

    # Attach mock loader in mock mode
    if mock_mode:
        adapter._mock_loader = mock_data_loader  # type: ignore[attr-defined]
        adapter._mock_provider = "anthropic"  # type: ignore[attr-defined]

    yield adapter

    # Close connection pool at session end
    http_client.close()


@pytest.fixture(scope="session")
def gemini_client(
    config: AppConfig, mock_mode: bool, mock_data_loader: MockDataLoader
) -> Generator[GeminiAdapter, None, None]:
    """Create a Gemini client adapter.

    Supports both real API calls and mock mode.
    """
    provider_config = config.get_provider_config("gemini")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter = GeminiAdapter(provider_config, http_client, logger)

    # Attach mock loader in mock mode
    if mock_mode:
        adapter._mock_loader = mock_data_loader  # type: ignore[attr-defined]
        adapter._mock_provider = "gemini"  # type: ignore[attr-defined]

    yield adapter

    # Close connection pool at session end
    http_client.close()


@pytest.fixture(scope="session")
def xai_client(
    config: AppConfig, mock_mode: bool, mock_data_loader: MockDataLoader
) -> Generator[XAIAdapter, None, None]:
    """Create an xAI client adapter.

    Supports both real API calls and mock mode.
    """
    provider_config = config.get_provider_config("xai")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter = XAIAdapter(provider_config, http_client, logger)

    # Attach mock loader in mock mode
    if mock_mode:
        adapter._mock_loader = mock_data_loader  # type: ignore[attr-defined]
        adapter._mock_provider = "xai"  # type: ignore[attr-defined]

    yield adapter

    # Close connection pool at session end
    http_client.close()


# Report root dir for this pytest run (avoid mixing with historical runs)
_RUN_REPORTS_DIR: Path | None = None


def pytest_configure(config):
    """Pytest hook: initialize report output directory."""
    global _RUN_REPORTS_DIR

    # Use a timestamp as run_id; write all reports under reports/<run_id>/
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Prefer llm-spec.toml [report].output_dir if available; otherwise default to ./reports
    report_root = Path("./reports")
    config_path = Path("llm-spec.toml")
    if config_path.exists():
        try:
            report_root = Path(load_config(config_path).report.output_dir)
        except Exception:
            report_root = Path("./reports")

    _RUN_REPORTS_DIR = report_root / run_id
    _RUN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Expose this run output directory to tests/collectors
    config.run_reports_dir = str(_RUN_REPORTS_DIR)  # type: ignore[attr-defined]


def pytest_sessionfinish(session, exitstatus):
    """Pytest hook: print run-level report summary.

    Usage:
    1. Run config-driven suites: pytest tests/integration/test_suite_runner.py
       → run_result.json + run-level report.md/html
    """
    global _RUN_REPORTS_DIR
    reports_dir = _RUN_REPORTS_DIR or Path("./reports")
    if not reports_dir.exists():
        return

    run_result_json = reports_dir / "run_result.json"
    if not run_result_json.exists():
        return

    try:
        with open(run_result_json, encoding="utf-8") as f:
            run_result = json.load(f)
        summary = run_result.get("summary", {})
        providers = run_result.get("providers", [])
        print(f"\n{'=' * 70}")
        print("📊 run_result.json generated")
        print(f"{'=' * 70}")
        print("📈 Summary:")
        print(f"  - Total tests: {summary.get('total', 0)}")
        print(f"  - Passed: {summary.get('passed', 0)} ✅")
        print(f"  - Failed: {summary.get('failed', 0)} ❌")
        print(f"  - Providers: {len(providers)}")
        print("📄 Files:")
        print(f"  - JSON:     {reports_dir / 'run_result.json'}")
        print(f"  - Markdown: {reports_dir / 'report.md'}")
        print(f"  - HTML:     {reports_dir / 'report.html'}")
        print(f"{'=' * 70}\n")
    except Exception as e:
        print(f"⚠️  Failed to print run_result report info: {e}")
