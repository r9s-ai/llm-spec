"""httpx-based HTTP client implementation.

Transport-only layer: does not handle logging, schema validation, or other business logic.
Those responsibilities belong to upper layers (adapters/runners).
"""

from __future__ import annotations

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
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> tuple[int, list[bytes]]:
        """Send a synchronous streaming request (Server-Sent Events).

        Collects all chunks internally and returns them with the status code.

        Returns:
            ``(status_code, chunks)`` tuple.

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx responses.
        """
        timeout_val = timeout if timeout is not None else self.default_timeout

        with self.sync_client.stream(
            method=method,
            url=url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout_val,
        ) as response:
            if response.status_code >= 400:
                response.read()
                response.raise_for_status()
            return response.status_code, list(response.iter_bytes())

    async def stream_async(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> tuple[int, list[bytes]]:
        """Send an asynchronous streaming request (Server-Sent Events).

        Collects all chunks internally and returns them with the status code.

        Returns:
            ``(status_code, chunks)`` tuple.

        Raises:
            httpx.HTTPStatusError: on 4xx/5xx responses.
        """
        timeout_val = timeout if timeout is not None else self.default_timeout

        async with self.async_client.stream(
            method=method,
            url=url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout_val,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                response.raise_for_status()
            return response.status_code, [chunk async for chunk in response.aiter_bytes()]
