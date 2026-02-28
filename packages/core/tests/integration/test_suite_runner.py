"""Config-driven suites runner (pytest integration).

This test module discovers JSON5 suites under `suites-registry/providers/` and generates pytest
parameterized tests dynamically.

Usage:
    # Run all config-driven tests
    pytest packages/core/tests/integration/test_suite_runner.py -v

    # Run a specific provider
    pytest packages/core/tests/integration/test_suite_runner.py -k "openai" -v

    # Run a specific test
    pytest packages/core/tests/integration/test_suite_runner.py -k "temperature" -v
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from mock_loader import MockDataLoader

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.registry import ExpandedSuite, load_registry_suites
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.runners import (
    ConfigDrivenTestRunner,
    SpecTestCase,
    SpecTestSuite,
    load_test_suite_from_dict,
)

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.integration


REPO_ROOT = Path(__file__).resolve().parents[4]
SUITES_DIR = REPO_ROOT / "suites-registry" / "providers"

# Cache loaded suites and collectors
_SUITE_CACHE: dict[str, tuple[ExpandedSuite, SpecTestSuite]] = {}
_COLLECTORS: dict[str, EndpointResultBuilder] = {}


def _get_suite(suite_key: str) -> tuple[ExpandedSuite, SpecTestSuite]:
    """Get or load a TestSuite (cached)."""
    return _SUITE_CACHE[suite_key]


def _get_collector(suite_key: str, client: ProviderAdapter) -> EndpointResultBuilder:
    """Get or create a EndpointResultBuilder (cached by suite path)."""
    if suite_key not in _COLLECTORS:
        _expanded, suite = _get_suite(suite_key)
        _COLLECTORS[suite_key] = EndpointResultBuilder(
            provider=suite.provider,
            endpoint=suite.endpoint,
            base_url=client.get_base_url(),
        )
    return _COLLECTORS[suite_key]


def discover_test_configs() -> list[tuple[str, str, str]]:
    """Discover all suite configs.

    Returns:
        A list of (suite_key, test_name, test_id).
    """
    configs: list[tuple[str, str, str]] = []

    if not SUITES_DIR.exists():
        return configs

    for item in load_registry_suites(SUITES_DIR):
        suite = load_test_suite_from_dict(item.suite_dict, item.source_route_path)
        suite_key = f"{item.provider}/{item.route}/{item.model}"
        _SUITE_CACHE[suite_key] = (item, suite)

        for test in suite.tests:
            test_id = f"{suite_key}::{test.name}"
            configs.append((suite_key, test.name, test_id))

    return configs


# Collect test configs at import time for parametrization
_TEST_CONFIGS = discover_test_configs()


@pytest.mark.parametrize(
    "suite_key,test_name",
    [(c[0], c[1]) for c in _TEST_CONFIGS],
    ids=[c[2] for c in _TEST_CONFIGS],
)
def test_from_config(
    suite_key: str,
    test_name: str,
    request: pytest.FixtureRequest,
    mock_mode: bool,
    respx_mock: respx.MockRouter | None,
    mock_data_loader: MockDataLoader,
) -> None:
    """Run a single test case from a suite config.

    Supports both real API calls and mock mode (via --mock flag).

    Args:
        suite_key: provider/route/model key
        test_name: test case name
        request: pytest fixture request
        mock_mode: whether mock mode is enabled
        respx_mock: respx mock router (if mock mode enabled)
        mock_data_loader: mock data loader instance
    """
    _expanded, suite = _get_suite(suite_key)

    # Resolve the provider client fixture
    client_fixture_name = f"{suite.provider}_client"
    try:
        client = request.getfixturevalue(client_fixture_name)
    except pytest.FixtureLookupError:
        pytest.skip(f"Client fixture '{client_fixture_name}' not found")
        return

    # Shared EndpointResultBuilder per suite config
    collector = _get_collector(suite_key, client)

    # Find the target test case
    test_case: SpecTestCase | None = None
    for t in suite.tests:
        if t.name == test_name:
            test_case = t
            break

    if test_case is None:
        pytest.fail(f"Test '{test_name}' not found in config")
        return

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
    runner = ConfigDrivenTestRunner(suite, client, collector)
    success = runner.run_test(test_case)

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
