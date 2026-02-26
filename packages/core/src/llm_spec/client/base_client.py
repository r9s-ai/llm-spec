"""Base abstractions for an HTTP client."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from llm_spec.json_types import Headers, JSONValue


class BaseHTTPClient(ABC):
    """Abstract HTTP client defining the interface for all HTTP operations."""

    @abstractmethod
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

        Args:
            method: HTTP method (GET, POST, ...)
            url: request URL
            headers: request headers
            json: JSON request body
            data: form data
            files: upload files
            timeout: timeout in seconds

        Returns:
            httpx.Response

        Raises:
            Exception: various HTTP/network errors
        """
        pass

    @abstractmethod
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

        Args:
            method: HTTP method (GET, POST, ...)
            url: request URL
            headers: request headers
            json: JSON request body
            data: form data
            files: upload files
            timeout: timeout in seconds

        Returns:
            httpx.Response

        Raises:
            Exception: various HTTP/network errors
        """
        pass

    @abstractmethod
    def stream(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """Send a synchronous streaming request (Server-Sent Events).

        Transport only; no business logic. Chunk aggregation and logging are handled by upper layers.

        Args:
            method: HTTP method (usually POST)
            url: request URL
            headers: request headers
            json: JSON request body
            data: form data
            files: upload files
            timeout: timeout in seconds

        Yields:
            response byte chunks

        Raises:
            Exception: various HTTP/network errors
        """
        pass

    @abstractmethod
    def stream_async(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[bytes]:
        """Send an asynchronous streaming request (Server-Sent Events).

        Transport only; no business logic.

        Args:
            method: HTTP method (usually POST)
            url: request URL
            headers: request headers
            json: JSON request body
            data: form data
            files: upload files
            timeout: timeout in seconds

        Yields:
            response byte chunks

        Raises:
            Exception: various HTTP/network errors
        """
        pass
