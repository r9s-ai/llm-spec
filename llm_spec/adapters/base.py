"""Provider adapter base class."""

from __future__ import annotations

import json as _json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig
from llm_spec.json_types import Headers, JSONValue
from llm_spec.logger import RequestLogger


def _serialize_form_data(params: Any) -> dict[str, Any]:
    """Serialize complex values (dict/list) in form-data params to JSON strings.

    httpx multipart encoder only accepts primitive types (str/int/float/bytes).
    Dict and list values must be JSON-serialized before passing as form fields.
    """
    if not isinstance(params, dict):
        return params
    form_data: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, (dict, list)):
            form_data[k] = _json.dumps(v)
        else:
            form_data[k] = v
    return form_data


class ProviderAdapter(ABC):
    """Provider adapter base class (composition over inheritance with HTTPClient)."""

    def __init__(
        self,
        config: ProviderConfig,
        http_client: HTTPClient,
        logger: RequestLogger | None = None,
    ):
        """Initialize a provider adapter.

        Args:
            config: provider config
            http_client: HTTP client instance
            logger: request logger instance (used by runner for structured logs)
        """
        self.config = config
        self.http_client = http_client
        self.logger = logger

    @abstractmethod
    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """Prepare request headers (including auth).

        Args:
            additional_headers: extra headers

        Returns:
            full headers dict
        """
        pass

    def get_base_url(self) -> str:
        """Get base URL.

        Returns:
            base URL
        """
        return self.config.base_url

    def request(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> httpx.Response:
        """Send a synchronous request.

        Args:
            endpoint: API endpoint path (e.g. "/v1/chat/completions")
            params: request params
            additional_headers: extra headers
            method: HTTP method
            files: multipart/form-data files

        Returns:
            (status_code, response_headers, response_body)
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        # If files are present, use multipart/form-data (data + files)
        if files:
            # Let httpx set multipart boundaries; remove manual Content-Type.
            headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
            return self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                data=_serialize_form_data(params),
                files=files,
                timeout=self.config.timeout,
            )

        # Default: JSON body
        return self.http_client.request(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )

    async def request_async(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> httpx.Response:
        """Send an asynchronous request.

        Args:
            endpoint: API endpoint path
            params: request params
            additional_headers: extra headers
            method: HTTP method
            files: multipart/form-data files

        Returns:
            (status_code, response_headers, response_body)
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        if files:
            headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
            return await self.http_client.request_async(
                method=method,
                url=url,
                headers=headers,
                data=_serialize_form_data(params),
                files=files,
                timeout=self.config.timeout,
            )

        return await self.http_client.request_async(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )

    def stream(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> Iterator[bytes]:
        """Send a synchronous streaming request.

        Args:
            endpoint: API endpoint path
            params: request params
            additional_headers: extra headers
            method: HTTP method
            files: multipart/form-data files

        Yields:
            response byte chunks
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        if files:
            headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
            return self.http_client.stream(
                method=method,
                url=url,
                headers=headers,
                data=_serialize_form_data(params),
                files=files,
                timeout=self.config.timeout,
            )

        return self.http_client.stream(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )

    def stream_async(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> AsyncIterator[bytes]:
        """Send an asynchronous streaming request.

        Args:
            endpoint: API endpoint path
            params: request params
            additional_headers: extra headers
            method: HTTP method
            files: multipart/form-data files

        Yields:
            response byte chunks
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        if files:
            headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
            return self.http_client.stream_async(
                method=method,
                url=url,
                headers=headers,
                data=_serialize_form_data(params),
                files=files,
                timeout=self.config.timeout,
            )

        return self.http_client.stream_async(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )
