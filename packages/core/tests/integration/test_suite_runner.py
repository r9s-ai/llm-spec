"""Config-driven suites runner (pytest integration).

This test module discovers JSON5 suites under `suites-registry/providers/` and generates pytest
parameterized tests dynamically.

Usage:
    # Run all config-driven tests
    pytest packages/core/tests/integration/test_suite_runner.py -v

    # Run a specific provider
    pytest packages/core/tests/integration/test_suite_runner.py -k "openai" -v

    # Run a specific test
    pytest packages/core/tests/integration/test_suite_runner.py -k "test_param_temperature" -v
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from mock_loader import MockDataLoader

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.cli import _build_run_result
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.reporting.report_types import ReportData
from llm_spec.reporting.run_result_formatter import RunResultFormatter
from llm_spec.runners import ConfigDrivenTestRunner, SpecTestCase, SpecTestSuite, load_test_suite

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.integration


REPO_ROOT = Path(__file__).resolve().parents[4]
SUITES_DIR = REPO_ROOT / "suites-registry" / "providers"

# Cache loaded suites and collectors
_SUITE_CACHE: dict[Path, SpecTestSuite] = {}
_COLLECTORS: dict[Path, EndpointResultBuilder] = {}


def _get_suite(config_path: Path) -> SpecTestSuite:
    """Get or load a TestSuite (cached)."""
    if config_path not in _SUITE_CACHE:
        _SUITE_CACHE[config_path] = load_test_suite(config_path)
    return _SUITE_CACHE[config_path]


def _get_collector(config_path: Path, client: ProviderAdapter) -> EndpointResultBuilder:
    """Get or create a EndpointResultBuilder (cached by suite path)."""
    if config_path not in _COLLECTORS:
        suite = _get_suite(config_path)
        _COLLECTORS[config_path] = EndpointResultBuilder(
            provider=suite.provider,
            endpoint=suite.endpoint,
            base_url=client.get_base_url(),
        )
    return _COLLECTORS[config_path]


def discover_test_configs() -> list[tuple[Path, str, str]]:
    """Discover all suite configs.

    Returns:
        A list of (config_path, test_name, test_id).
    """
    configs: list[tuple[Path, str, str]] = []

    if not SUITES_DIR.exists():
        return configs

    for config_file in sorted(SUITES_DIR.rglob("*.json5")):
        suite = _get_suite(config_file)

        for test in suite.tests:
            # Human-readable test id, e.g.:
            #   openai/chat_completions::test_param_temperature
            relative_path = config_file.relative_to(SUITES_DIR)
            test_id = f"{relative_path.with_suffix('')}::{test.name}"
            configs.append((config_file, test.name, test_id))

    return configs


# Collect test configs at import time for parametrization
_TEST_CONFIGS = discover_test_configs()


@pytest.mark.parametrize(
    "config_path,test_name",
    [(c[0], c[1]) for c in _TEST_CONFIGS],
    ids=[c[2] for c in _TEST_CONFIGS],
)
def test_from_config(
    config_path: Path,
    test_name: str,
    request: pytest.FixtureRequest,
    mock_mode: bool,
    respx_mock: respx.MockRouter | None,
    mock_data_loader: MockDataLoader,
) -> None:
    """Run a single test case from a suite config.

    Supports both real API calls and mock mode (via --mock flag).

    Args:
        config_path: JSON5 suite config path
        test_name: test case name
        request: pytest fixture request
        mock_mode: whether mock mode is enabled
        respx_mock: respx mock router (if mock mode enabled)
        mock_data_loader: mock data loader instance
    """
    suite = _get_suite(config_path)

    # Resolve the provider client fixture
    client_fixture_name = f"{suite.provider}_client"
    try:
        client = request.getfixturevalue(client_fixture_name)
    except pytest.FixtureLookupError:
        pytest.skip(f"Client fixture '{client_fixture_name}' not found")
        return

    # Shared EndpointResultBuilder per suite config
    collector = _get_collector(config_path, client)

    # Find the target test case
    test_case: SpecTestCase | None = None
    for t in suite.tests:
        if t.name == test_name:
            test_case = t
            break

    if test_case is None:
        pytest.fail(f"Test '{test_name}' not found in config")
        return

    # Logger is attached to adapters
    logger = getattr(client, "logger", None)

    # Mock mode: setup respx route for this specific test
    if mock_mode and respx_mock:
        _setup_mock_route(
            respx_mock=respx_mock,
            mock_loader=mock_data_loader,
            suite=suite,
            test_case=test_case,
            client=client,
        )

    # Run
    runner = ConfigDrivenTestRunner(suite, client, collector, logger)
    success = runner.run_test(test_case)

    # Run-level report generation is handled at session end (see conftest.py)

    # Assert
    assert success, f"Test '{test_name}' failed"


def _setup_mock_route(
    respx_mock: respx.MockRouter,
    mock_loader: MockDataLoader,
    suite: SpecTestSuite,
    test_case: SpecTestCase,
    client: ProviderAdapter,
) -> None:
    """Setup respx mock route for a single test case.

    Registers HTTP mock responses based on mock data files.
    Supports both streaming and non-streaming responses.

    Args:
        respx_mock: respx mock router
        mock_loader: mock data loader instance
        suite: test suite configuration
        test_case: specific test case to mock
        client: provider client adapter
    """
    # Build full URL
    base_url = client.get_base_url()
    endpoint = test_case.endpoint_override or suite.endpoint
    full_url = f"{base_url}{endpoint}"

    is_stream = test_case.stream

    # Load mock data
    try:
        mock_data = mock_loader.load_response(
            provider=suite.provider,
            endpoint=endpoint,
            test_name=test_case.name,
            is_stream=is_stream,
        )
    except FileNotFoundError as e:
        pytest.skip(f"Mock data not available: {e}")
        return
    except Exception as e:
        print(f"\n[MOCK ERROR] Failed to load mock data for '{test_case.name}': {e}")
        pytest.fail(f"Mock data error: {e}")
        return

    # Register respx route
    if is_stream:
        # Streaming response: combine all chunks into single response
        # The HTTPClient.stream() method will iterate over the bytes
        if isinstance(mock_data, dict):
            raise TypeError(
                f"Expected Iterator[bytes] for streaming response, got {type(mock_data)}"
            )
        try:
            chunks = list(mock_data)  # mock_data is Iterator[bytes]
        except Exception as e:
            print(f"\n[MOCK ERROR] Failed to parse stream data for '{test_case.name}': {e}")
            pytest.fail(f"Mock stream error: {e}")
            return
        combined_content = b"".join(chunks)

        respx_mock.post(full_url).mock(
            return_value=httpx.Response(
                status_code=200,
                headers={"content-type": "text/event-stream"},
                content=combined_content,
            )
        )
    else:
        # Non-streaming response
        if not isinstance(mock_data, dict):
            raise TypeError(f"Expected dict for non-streaming response, got {type(mock_data)}")

        # Support binary mock data via base64
        if "body_base64" in mock_data:
            import base64

            # Handle missing padding in base64 string
            b64_data = mock_data["body_base64"]
            padding_needed = (-len(b64_data)) % 4
            if padding_needed:
                b64_data += "=" * padding_needed
            content = base64.b64decode(b64_data)
            respx_mock.post(full_url).mock(
                return_value=httpx.Response(
                    status_code=mock_data["status_code"],
                    headers=mock_data.get("headers", {}),
                    content=content,
                )
            )
        else:
            respx_mock.post(full_url).mock(
                return_value=httpx.Response(
                    status_code=mock_data["status_code"],
                    headers=mock_data.get("headers", {}),
                    json=mock_data["body"],
                )
            )


# ============================================================================
# Optional provider group classes (kept for readability / future extensions)
# ============================================================================


class TestOpenAIFromConfig:
    """OpenAI config-driven tests."""

    # Provider-specific fixtures or settings can live here.
    pass


class TestGeminiFromConfig:
    """Gemini config-driven tests."""

    pass


@pytest.fixture(scope="session", autouse=True)
def finalize_config_reports(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Finalize run_result + run-level views at session end."""
    yield

    output_dir = getattr(request.config, "run_reports_dir", "./reports")

    if not _COLLECTORS:
        return

    print(f"\nFinalizing run_result reports (to {output_dir})...")
    reports_by_provider: dict[str, list[ReportData]] = {}
    for collector in _COLLECTORS.values():
        report_data = collector.build_report_data()
        provider = str(report_data.get("provider", "unknown"))
        reports_by_provider.setdefault(provider, []).append(report_data)

    run_id = Path(output_dir).name
    run_result = _build_run_result(
        run_id=run_id,
        started_at="N/A",
        finished_at="N/A",
        reports_by_provider=reports_by_provider,
    )

    output_dir_path = Path(output_dir)
    run_result_path = output_dir_path / "run_result.json"
    import json

    run_result_path.write_text(
        json.dumps(run_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    formatter = RunResultFormatter(run_result)
    md_path = formatter.save_markdown(output_dir)
    html_path = formatter.save_html(output_dir)
    print(f"✅ run_result generated: {run_result_path}")
    print(f"✅ markdown generated: {md_path}")
    print(f"✅ html generated: {html_path}")
