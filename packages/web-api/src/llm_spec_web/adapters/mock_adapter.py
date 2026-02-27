"""Mock adapter for offline web runs using integration mock fixtures."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig
from llm_spec.json_types import Headers, JSONValue
from llm_spec.logger import current_test_name
from packages.core.tests.integration.mock_loader import MockDataLoader

# Mock delay configuration
MOCK_MIN_DELAY = 1  # Minimum delay in seconds
MOCK_MAX_DELAY = 3  # Maximum delay in seconds


class MockProviderAdapter(ProviderAdapter):
    """Adapter implementation that reads fixture responses from mock files.

    This adapter is used for testing purposes, returning pre-recorded
    responses from mock fixture files instead of making real API calls.

    Attributes:
        loader: Mock data loader instance.
        provider_name: Name of the provider being mocked.
    """

    def __init__(
        self,
        config: ProviderConfig,
        base_dir: str | Path,
        provider_name: str,
    ) -> None:
        """Initialize the mock adapter.

        Args:
            config: Provider configuration.
            base_dir: Base directory for mock fixture files.
            provider_name: Name of the provider being mocked.
        """
        super().__init__(config=config, http_client=HTTPClient(default_timeout=config.timeout))
        self.loader = MockDataLoader(Path(base_dir))
        self.provider_name = provider_name

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """Prepare request headers.

        Args:
            additional_headers: Additional headers to include (ignored in mock mode).

        Returns:
            Mock headers dictionary.
        """
        del additional_headers
        return {"content-type": "application/json"}

    @staticmethod
    def _resolve_test_name() -> str:
        """Resolve the current test name from context.

        Returns:
            Test name for loading mock data.
        """
        full_name = current_test_name.get() or ""
        if "::" not in full_name:
            return "baseline"
        return full_name.split("::", 1)[1]

    def request(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> httpx.Response:
        """Make a mock request.

        Args:
            endpoint: API endpoint path.
            params: Request parameters (ignored in mock mode).
            additional_headers: Additional headers (ignored in mock mode).
            method: HTTP method (ignored in mock mode).
            files: Files to upload (ignored in mock mode).

        Returns:
            Mock HTTP response.

        Raises:
            TypeError: If mock response is not a dict.
        """
        del params, additional_headers, method, files
        # Simulate network latency
        delay = random.uniform(MOCK_MIN_DELAY, MOCK_MAX_DELAY)
        import time

        time.sleep(delay)
        data = self.loader.load_response(
            provider=self.provider_name,
            endpoint=endpoint,
            test_name=self._resolve_test_name(),
            is_stream=False,
        )
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict mock response, got {type(data)}")
        return httpx.Response(
            status_code=int(data.get("status_code", 200)),
            headers=dict(data.get("headers", {})),
            json=data.get("body"),
        )

    async def request_async(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> httpx.Response:
        """Make an async mock request.

        Args:
            endpoint: API endpoint path.
            params: Request parameters (ignored in mock mode).
            additional_headers: Additional headers (ignored in mock mode).
            method: HTTP method (ignored in mock mode).
            files: Files to upload (ignored in mock mode).

        Returns:
            Mock HTTP response.

        Raises:
            TypeError: If mock response is not a dict.
        """
        del params, additional_headers, method, files
        # Simulate network latency (async)
        delay = random.uniform(MOCK_MIN_DELAY, MOCK_MAX_DELAY)
        await asyncio.sleep(delay)
        data = self.loader.load_response(
            provider=self.provider_name,
            endpoint=endpoint,
            test_name=self._resolve_test_name(),
            is_stream=False,
        )
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict mock response, got {type(data)}")
        return httpx.Response(
            status_code=int(data.get("status_code", 200)),
            headers=dict(data.get("headers", {})),
            json=data.get("body"),
        )

    def stream(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> Iterator[bytes]:
        """Make a mock streaming request.

        Args:
            endpoint: API endpoint path.
            params: Request parameters (ignored in mock mode).
            additional_headers: Additional headers (ignored in mock mode).
            method: HTTP method (ignored in mock mode).
            files: Files to upload (ignored in mock mode).

        Returns:
            Mock streaming response iterator.

        Raises:
            TypeError: If mock response is not an iterator.
        """
        del params, additional_headers, method, files
        # Simulate initial connection latency
        delay = random.uniform(MOCK_MIN_DELAY, MOCK_MAX_DELAY)
        import time

        time.sleep(delay)
        data = self.loader.load_response(
            provider=self.provider_name,
            endpoint=endpoint,
            test_name=self._resolve_test_name(),
            is_stream=True,
        )
        if isinstance(data, dict):
            raise TypeError(f"Expected iterator mock response, got {type(data)}")

        def delayed_stream() -> Iterator[bytes]:
            """Wrap stream with delays between chunks."""
            for chunk in data:
                # Small delay between chunks to simulate streaming
                time.sleep(random.uniform(0.01, 0.05))
                yield chunk

        return delayed_stream()

    async def stream_async(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> AsyncIterator[bytes]:
        """Make an async mock streaming request.

        Args:
            endpoint: API endpoint path.
            params: Request parameters (ignored in mock mode).
            additional_headers: Additional headers (ignored in mock mode).
            method: HTTP method (ignored in mock mode).
            files: Files to upload (ignored in mock mode).

        Returns:
            Mock streaming response async iterator.

        Raises:
            TypeError: If mock response is not an iterator.
        """
        del params, additional_headers, method, files
        # Simulate initial connection latency (async)
        delay = random.uniform(MOCK_MIN_DELAY, MOCK_MAX_DELAY)
        await asyncio.sleep(delay)
        data = self.loader.load_response(
            provider=self.provider_name,
            endpoint=endpoint,
            test_name=self._resolve_test_name(),
            is_stream=True,
        )
        if isinstance(data, dict):
            raise TypeError(f"Expected iterator mock response, got {type(data)}")

        for chunk in data:
            # Small delay between chunks to simulate streaming (async)
            await asyncio.sleep(random.uniform(0.01, 0.05))
            yield chunk
