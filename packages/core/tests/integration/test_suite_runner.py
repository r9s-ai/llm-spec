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
from llm_spec.runners import TestRunner
from llm_spec.suites import SuiteSpec, TestCase, build_execution_plan, load_registry_suites

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.integration


REPO_ROOT = Path(__file__).resolve().parents[4]
SUITES_DIR = REPO_ROOT / "suites-registry" / "providers"

# Cache loaded suites
_SUITE_CACHE: dict[str, SuiteSpec] = {}
_CASE_CACHE: dict[str, TestCase] = {}


def discover_test_configs() -> list[tuple[str, str, str]]:
    """Discover all suite configs.

    Returns:
        A list of (suite_key, test_name, test_id).
    """
    configs: list[tuple[str, str, str]] = []

    if not SUITES_DIR.exists():
        return configs

    for suite in load_registry_suites(SUITES_DIR):
        suite_key = f"{suite.provider_id}/{suite.route_id}/{suite.model_id}"
        _SUITE_CACHE[suite_key] = suite

        cases = build_execution_plan(suite)
        for case in cases:
            case_key = f"{suite_key}::{case.test_name}"
            _CASE_CACHE[case_key] = case
            test_id = case_key
            configs.append((suite_key, case.test_name, test_id))

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
    """Run a single test case from a suite config."""
    suite = _SUITE_CACHE[suite_key]
    case = _CASE_CACHE[f"{suite_key}::{test_name}"]

    # Resolve the provider client fixture
    client_fixture_name = f"{suite.provider_id}_client"
    try:
        client = request.getfixturevalue(client_fixture_name)
    except pytest.FixtureLookupError:
        pytest.skip(f"Client fixture '{client_fixture_name}' not found")
        return

    # Mock mode: setup respx route for this specific test
    if mock_mode and respx_mock:
        _setup_mock_route(
            respx_mock=respx_mock,
            mock_loader=mock_data_loader,
            suite=suite,
            case=case,
            client=client,
        )

    # Run
    runner = TestRunner(client, source_path=suite.source_path)
    verdict = runner.run(case)

    # Assert
    assert verdict.status == "pass", f"Test '{test_name}' failed: {verdict.failure}"


def _setup_mock_route(
    respx_mock: respx.MockRouter,
    mock_loader: MockDataLoader,
    suite: SuiteSpec,
    case: TestCase,
    client: ProviderAdapter,
) -> None:
    """Setup respx mock route for a single test case."""
    # Build full URL
    base_url = client.get_base_url()
    endpoint = case.request.endpoint
    full_url = f"{base_url}{endpoint}"

    is_stream = case.request.stream

    # Load mock data
    try:
        mock_data = mock_loader.load_response(
            provider=suite.provider_id,
            endpoint=endpoint,
            test_name=case.test_name,
            is_stream=is_stream,
        )
    except FileNotFoundError as e:
        pytest.skip(f"Mock data not available: {e}")
        return
    except Exception as e:
        print(f"\n[MOCK ERROR] Failed to load mock data for '{case.test_name}': {e}")
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
            print(f"\n[MOCK ERROR] Failed to parse stream data for '{case.test_name}': {e}")
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
