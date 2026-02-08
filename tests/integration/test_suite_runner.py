"""Config-driven suites runner (pytest integration).

This test module discovers JSON5 suites under `suites/` and generates pytest
parameterized tests dynamically.

Usage:
    # Run all config-driven tests
    pytest tests/integration/test_suite_runner.py -v

    # Run a specific provider
    pytest tests/integration/test_suite_runner.py -k "openai" -v

    # Run a specific test
    pytest tests/integration/test_suite_runner.py -k "test_param_temperature" -v
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.runners import ConfigDrivenTestRunner, SpecTestCase, SpecTestSuite, load_test_suite

if TYPE_CHECKING:
    pass


pytestmark = pytest.mark.integration


REPO_ROOT = Path(__file__).resolve().parents[2]
SUITES_DIR = REPO_ROOT / "suites"

# Cache loaded suites and collectors
_SUITE_CACHE: dict[Path, SpecTestSuite] = {}
_COLLECTORS: dict[Path, ReportCollector] = {}


def _get_suite(config_path: Path) -> SpecTestSuite:
    """Get or load a TestSuite (cached)."""
    if config_path not in _SUITE_CACHE:
        _SUITE_CACHE[config_path] = load_test_suite(config_path)
    return _SUITE_CACHE[config_path]


def _get_collector(config_path: Path, client: Any) -> ReportCollector:
    """Get or create a ReportCollector (cached by suite path)."""
    if config_path not in _COLLECTORS:
        suite = _get_suite(config_path)
        _COLLECTORS[config_path] = ReportCollector(
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
        try:
            suite = _get_suite(config_file)

            for test in suite.tests:
                # Human-readable test id, e.g.:
                #   openai/chat_completions::test_param_temperature
                relative_path = config_file.relative_to(SUITES_DIR)
                test_id = f"{relative_path.with_suffix('')}::{test.name}"
                configs.append((config_file, test.name, test_id))

        except Exception as e:
            # Skip invalid suites but warn
            print(f"Warning: Failed to load {config_file}: {e}")

    return configs


# Collect test configs at import time for parametrization
_TEST_CONFIGS = discover_test_configs()


@pytest.mark.parametrize(
    "config_path,test_name",
    [(c[0], c[1]) for c in _TEST_CONFIGS],
    ids=[c[2] for c in _TEST_CONFIGS],
)
def test_from_config(config_path: Path, test_name: str, request: pytest.FixtureRequest):
    """Run a single test case from a suite config.

    Args:
        config_path: JSON5 suite config path
        test_name: test case name
        request: pytest fixture request
    """
    suite = _get_suite(config_path)

    # Resolve the provider client fixture
    client_fixture_name = f"{suite.provider}_client"
    try:
        client = request.getfixturevalue(client_fixture_name)
    except pytest.FixtureLookupError:
        pytest.skip(f"Client fixture '{client_fixture_name}' not found")
        return

    # Shared ReportCollector per suite config
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

    # Run
    runner = ConfigDrivenTestRunner(suite, client, collector, logger)
    success = runner.run_test(test_case)

    # Report generation is handled at session end (see conftest.py)
    # output_dir = getattr(request.config, "run_reports_dir", "./reports")
    # collector.finalize(output_dir)

    # Assert
    assert success, f"Test '{test_name}' failed"


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
def finalize_config_reports(request: pytest.FixtureRequest):
    """Finalize per-suite reports at session end."""
    yield

    output_dir = getattr(request.config, "run_reports_dir", "./reports")

    if not _COLLECTORS:
        return

    print(f"\nFinalizing config-driven reports (to {output_dir})...")
    for collector in _COLLECTORS.values():
        try:
            report_path = collector.finalize(output_dir)
            print(f"✅ Report generated: {report_path}")
        except Exception as e:
            print(f"Warning: Failed to finalize report for {collector.endpoint}: {e}")
