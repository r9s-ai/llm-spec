"""Base HTTP client with sync/async/stream support."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from llm_spec.core.config import ProviderConfig, get_config
from llm_spec.core.exceptions import RequestError
from llm_spec.core.logger import (
    get_logger,
    log_error,
    log_request,
    log_response,
    setup_logging,
)
from llm_spec.core.report import ValidationReport


class BaseClient(ABC):
    """Abstract base client for LLM API providers."""

    provider_name: str = ""
    default_base_url: str = ""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        config: ProviderConfig | None = None,
    ) -> None:
        """Initialize client with optional overrides.

        Priority: method params > config param > global config > defaults
        """
        self._config = config
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

        # Setup logging
        self._log_config = get_config().log
        setup_logging(self._log_config)
        self._logger = get_logger(f"llm_spec.{self.provider_name}")

    @property
    def api_key(self) -> str | None:
        """Get API key with priority resolution."""
        if self._api_key is not None:
            return self._api_key
        if self._config is not None:
            return self._config.api_key
        return self._get_global_config().api_key

    @property
    def base_url(self) -> str:
        """Get base URL with priority resolution."""
        if self._base_url is not None:
            return self._base_url
        if self._config is not None and self._config.base_url is not None:
            return self._config.base_url
        global_url = self._get_global_config().base_url
        return global_url if global_url is not None else self.default_base_url

    @property
    def timeout(self) -> float:
        """Get timeout with priority resolution."""
        if self._timeout is not None:
            return self._timeout
        if self._config is not None:
            return self._config.timeout
        return self._get_global_config().timeout

    @abstractmethod
    def _get_global_config(self) -> ProviderConfig:
        """Get the global config for this provider."""
        ...

    @abstractmethod
    def _build_headers(self) -> dict[str, str]:
        """Build request headers including authentication."""
        ...

    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._build_headers(),
            )
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._build_headers(),
            )
        return self._async_client

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a synchronous HTTP request and parse result as JSON."""
        response_text = self.request_raw(
            method, endpoint, json=json, params=params, data=data, files=files
        )
        import json as json_lib

        return json_lib.loads(response_text)

    def request_raw(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> str:
        """Make a synchronous HTTP request and return raw text.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json: JSON body (for application/json)
            params: Query parameters
            data: Form data (for multipart/form-data)
            files: Files to upload (for multipart/form-data)
        """
        client = self._get_sync_client()
        url = f"{self.base_url}{endpoint}"

        # Log request
        if self._log_config.enabled:
            log_request(
                self._logger,
                method,
                url,
                body=json or data,
                log_body=self._log_config.log_request_body,
                max_length=self._log_config.max_body_length,
            )

        start_time = time.perf_counter()
        try:
            response = client.request(
                method, endpoint, json=json, params=params, data=data, files=files
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            response.raise_for_status()
            result = response.text

            # Log response
            if self._log_config.enabled:
                log_response(
                    self._logger,
                    response.status_code,
                    elapsed_ms=elapsed_ms,
                    body=result,
                    log_body=self._log_config.log_response_body,
                    max_length=self._log_config.max_body_length,
                )

            return result
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e), status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e)) from e

    def request_binary(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> bytes:
        """Make a synchronous HTTP request returning binary data."""
        client = self._get_sync_client()
        url = f"{self.base_url}{endpoint}"

        # Log request
        if self._log_config.enabled:
            log_request(
                self._logger,
                method,
                url,
                body=json,
                log_body=self._log_config.log_request_body,
                max_length=self._log_config.max_body_length,
            )

        start_time = time.perf_counter()
        try:
            response = client.request(method, endpoint, json=json)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            response.raise_for_status()

            # Log response (no body for binary)
            if self._log_config.enabled:
                log_response(self._logger, response.status_code, elapsed_ms=elapsed_ms)

            return response.content
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e), status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e)) from e

    async def async_request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an asynchronous HTTP request and parse result as JSON."""
        response_text = await self.async_request_raw(method, endpoint, json=json, params=params)
        import json as json_lib

        return json_lib.loads(response_text)

    async def async_request_raw(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Make an asynchronous HTTP request and return raw text."""
        client = self._get_async_client()
        url = f"{self.base_url}{endpoint}"

        # Log request
        if self._log_config.enabled:
            log_request(
                self._logger,
                method,
                url,
                body=json,
                log_body=self._log_config.log_request_body,
                max_length=self._log_config.max_body_length,
            )

        start_time = time.perf_counter()
        try:
            response = await client.request(method, endpoint, json=json, params=params)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            response.raise_for_status()
            result = response.text

            # Log response
            if self._log_config.enabled:
                log_response(
                    self._logger,
                    response.status_code,
                    elapsed_ms=elapsed_ms,
                    body=result,
                    log_body=self._log_config.log_response_body,
                    max_length=self._log_config.max_body_length,
                )

            return result
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e), status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e)) from e

    def stream(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Make a synchronous streaming request (SSE).

        Supports both JSON (application/json) and multipart/form-data streams
        by allowing ``data``/``files`` to be passed through to httpx.
        """
        client = self._get_sync_client()
        url = f"{self.base_url}{endpoint}"

        # Log request
        if self._log_config.enabled:
            log_request(
                self._logger,
                method,
                url,
                body=json if json is not None else data,
                log_body=self._log_config.log_request_body,
                max_length=self._log_config.max_body_length,
            )

        start_time = time.perf_counter()
        try:
            with client.stream(method, endpoint, json=json, data=data, files=files) as response:
                response.raise_for_status()

                # Log response start
                if self._log_config.enabled:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    self._logger.info(f"<- {response.status_code} STREAM ({elapsed_ms:.0f}ms)")

                for line in response.iter_lines():
                    if line.startswith("data: "):
                        yield line[6:]
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e), status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e)) from e

    async def async_stream(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Make an asynchronous streaming request (SSE)."""
        client = self._get_async_client()
        url = f"{self.base_url}{endpoint}"

        # Log request
        if self._log_config.enabled:
            log_request(
                self._logger,
                method,
                url,
                body=json,
                log_body=self._log_config.log_request_body,
                max_length=self._log_config.max_body_length,
            )

        start_time = time.perf_counter()
        try:
            async with client.stream(method, endpoint, json=json) as response:
                response.raise_for_status()

                # Log response start
                if self._log_config.enabled:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    self._logger.info(f"<- {response.status_code} STREAM ({elapsed_ms:.0f}ms)")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line[6:]
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e), status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._log_config.enabled:
                log_error(self._logger, method, url, e, elapsed_ms)
            raise RequestError(str(e)) from e

    @abstractmethod
    def validate_chat_completion(self, **kwargs: Any) -> ValidationReport:
        """Validate chat completion endpoint. Must be implemented by providers."""
        ...

    def close(self) -> None:
        """Close sync client."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """Close async client."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self) -> BaseClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    async def __aenter__(self) -> BaseClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
