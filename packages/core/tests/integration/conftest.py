"""Pytest fixtures for testing"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
import respx
from mock_loader import MockDataLoader

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig, load_config


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
        MockDataLoader instance pointing to packages/core/tests/integration/mocks/
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

    # HTTP client (transport only)
    http_client = HTTPClient(default_timeout=provider_config.timeout)

    adapter = OpenAIAdapter(provider_config, http_client)

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
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter = AnthropicAdapter(provider_config, http_client)

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
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter = GeminiAdapter(provider_config, http_client)

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
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter = XAIAdapter(provider_config, http_client)

    # Attach mock loader in mock mode
    if mock_mode:
        adapter._mock_loader = mock_data_loader  # type: ignore[attr-defined]
        adapter._mock_provider = "xai"  # type: ignore[attr-defined]

    yield adapter

    # Close connection pool at session end
    http_client.close()
