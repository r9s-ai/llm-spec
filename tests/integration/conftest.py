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
from llm_spec.reporting.aggregator import AggregatedReportCollector
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


# Aggregated report tracking
_aggregated_reports: dict[str, list[Path]] = {}

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
    """Pytest hook: finalize per-endpoint and aggregated reports.

    Usage:
    1. Run config-driven suites: pytest tests/integration/test_suite_runner.py
       → per-endpoint reports + aggregated reports (when multiple endpoints exist)
    """
    global _RUN_REPORTS_DIR
    # Only scan reports produced in this run
    reports_dir = _RUN_REPORTS_DIR or Path("./reports")

    if not reports_dir.exists():
        return

    # Group reports by provider
    provider_reports = {}

    for report_subdir in reports_dir.iterdir():
        if not report_subdir.is_dir():
            continue

        # Skip already-aggregated reports
        if "aggregated" in report_subdir.name:
            continue

        report_json = report_subdir / "report.json"
        if not report_json.exists():
            continue

        try:
            with open(report_json, encoding="utf-8") as f:
                report_data = json.load(f)
                provider = report_data.get("provider", "unknown")

                if provider not in provider_reports:
                    provider_reports[provider] = []

                provider_reports[provider].append(report_json)
        except (OSError, json.JSONDecodeError):
            continue

    # Finalize for each provider
    for provider, report_files in provider_reports.items():
        if len(report_files) == 1:
            # Single report
            _print_single_report_info(report_files[0])

        elif len(report_files) > 1:
            # Multiple reports → aggregated report
            try:
                aggregator = AggregatedReportCollector(provider)
                aggregator.merge_reports(report_files)

                output_dir = getattr(session.config, "run_reports_dir", "./reports")
                output_paths = aggregator.finalize(output_dir)

                _print_aggregated_report_info(provider, report_files, output_paths)
            except Exception as e:
                print(f"⚠️  Failed to generate aggregated report for {provider}: {e}")


def _print_single_report_info(report_json: Path) -> None:
    """Print per-endpoint report info."""
    try:
        with open(report_json, encoding="utf-8") as f:
            report = json.load(f)

        endpoint = report.get("endpoint", "unknown")
        provider = report.get("provider", "unknown")
        summary = report.get("test_summary", {})

        print(f"\n{'=' * 60}")
        print(f"✅ {provider.upper()} - {endpoint} report generated:")
        print(f"  - Total tests: {summary.get('total_tests', 0)}")
        print(f"  - Passed: {summary.get('passed', 0)} ✅")
        print(f"  - Failed: {summary.get('failed', 0)} ❌")
        print(f"  - Report dir: {report_json.parent.name}/")
        print("    - JSON:     report.json")
        print("    - Markdown: report.md")
        print("    - HTML:     report.html")
        print(f"{'=' * 60}\n")
    except Exception as e:
        print(f"⚠️  Failed to read report: {e}")


def _print_aggregated_report_info(provider: str, report_files: list, output_paths: dict) -> None:
    """Print aggregated report info."""
    try:
        with open(output_paths["json"], encoding="utf-8") as f:
            aggregated = json.load(f)

        summary = aggregated.get("summary", {})

        print(f"\n{'=' * 70}")
        print(f"📊 {provider.upper()} aggregated report generated ({len(report_files)} endpoints)")
        print(f"{'=' * 70}")
        print("")
        print("📈 Summary:")
        print(f"  - Total tests: {summary.get('test_summary', {}).get('total_tests', 0)}")
        print(f"  - Passed: {summary.get('test_summary', {}).get('passed', 0)} ✅")
        print(f"  - Failed: {summary.get('test_summary', {}).get('failed', 0)} ❌")
        print(f"  - Pass rate: {summary.get('test_summary', {}).get('pass_rate', 'N/A')}")
        print("")
        print(f"🔗 Endpoint ({len(report_files)}):")
        for endpoint in summary.get("endpoints", []):
            print(f"  - {endpoint}")
        print("")
        print("📋 Parameters:")
        params = summary.get("parameters", {})
        print(f"  - Total unique: {params.get('total_unique', 0)}")
        print(f"  - Fully supported: {params.get('fully_supported', 0)}")
        print(f"  - Partially supported: {params.get('partially_supported', 0)}")
        print(f"  - Unsupported: {params.get('unsupported', 0)}")
        print("")
        print("📄 Files:")
        print(f"  - JSON:     {output_paths['json']}")
        print(f"  - Markdown: {output_paths['markdown']}")
        print(f"  - HTML:     {output_paths['html']}")
        print(f"{'=' * 70}\n")
    except Exception as e:
        print(f"⚠️  Failed to print aggregated report info: {e}")
