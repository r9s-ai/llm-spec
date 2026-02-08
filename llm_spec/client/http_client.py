"""httpx-based HTTP client implementation.

Transport-only layer: does not handle logging, schema validation, or other business logic.
Those responsibilities belong to upper layers (adapters/runners).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from llm_spec.client.base_client import BaseHTTPClient
from llm_spec.json_types import Headers, JSONValue


class HTTPClient(BaseHTTPClient):
    """HTTP client implementation based on httpx.

    Uses connection pooling to improve throughput for batch requests.
    Single responsibility: HTTP transport only (no logging/validation).
    """

    def __init__(self, default_timeout: float = 30.0):
        """Initialize the HTTP client.

        Args:
            default_timeout: default timeout in seconds
        """
        self.default_timeout = default_timeout
        # Lazy-initialized clients (connection pooling)
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None
        # Status code of the most recent stream response (useful for callers)
        self.stream_status_code: int | None = None

    @property
    def sync_client(self) -> httpx.Client:
        """Get or create a sync httpx client (connection pooled)."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=self.default_timeout)
        return self._sync_client

    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create an async httpx client (connection pooled)."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.default_timeout)
        return self._async_client

    def close(self) -> None:
        """Close the sync client and release resources."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self) -> None:
        """Close the async client and release resources."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def request(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send a synchronous HTTP request.

        Transport only; logging is handled by upper layers.
        """
        timeout_val = timeout if timeout is not None else self.default_timeout

        # Use the pooled client
        response = self.sync_client.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout_val,
        )

        return response

    async def request_async(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send an asynchronous HTTP request.

        Transport only; logging is handled by upper layers.
        """
        timeout_val = timeout if timeout is not None else self.default_timeout

        response = await self.async_client.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout_val,
        )

        return response

    def stream(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """Send a synchronous streaming request (Server-Sent Events).

        Transport-only streaming. Chunk aggregation and logging are handled by upper layers.

        Args:
            method: HTTP method
            url: request URL
            headers: request headers
            json: JSON request body
            timeout: timeout in seconds

        Yields:
            response byte chunks
        """
        timeout_val = timeout if timeout is not None else self.default_timeout

        # Stream using the pooled client
        with self.sync_client.stream(
            method=method,
            url=url,
            headers=headers,
            json=json,
            timeout=timeout_val,
        ) as response:
            self.stream_status_code = response.status_code
            # Raise on non-2xx to prevent upper layers from validating error responses as normal streams.
            # Call read() so e.response.text is available to callers catching HTTPStatusError.
            if response.status_code >= 400:
                response.read()
                response.raise_for_status()
            # Transport-only: yield raw bytes
            yield from response.iter_bytes()

    async def stream_async(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[bytes]:
        """Send an asynchronous streaming request (Server-Sent Events).

        Transport-only streaming.

        Args:
            method: HTTP method
            url: request URL
            headers: request headers
            json: JSON request body
            timeout: timeout in seconds

        Yields:
            response byte chunks
        """
        timeout_val = timeout if timeout is not None else self.default_timeout

        async with self.async_client.stream(
            method=method,
            url=url,
            headers=headers,
            json=json,
            timeout=timeout_val,
        ) as response:
            self.stream_status_code = response.status_code
            if response.status_code >= 400:
                await response.aread()
                response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk
