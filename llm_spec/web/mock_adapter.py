"""Mock adapter for offline web runs using integration mock fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig
from llm_spec.json_types import Headers, JSONValue
from llm_spec.logger import current_test_name
from tests.integration.mock_loader import MockDataLoader


class MockProviderAdapter(ProviderAdapter):
    """Adapter implementation that reads fixture responses from mock files."""

    def __init__(self, config: ProviderConfig, base_dir: str | Path, provider_name: str):
        super().__init__(config=config, http_client=HTTPClient(default_timeout=config.timeout))
        self.loader = MockDataLoader(Path(base_dir))
        self.provider_name = provider_name

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        del additional_headers
        return {"content-type": "application/json"}

    @staticmethod
    def _resolve_test_name() -> str:
        full_name = current_test_name.get() or ""
        if "::" not in full_name:
            return "test_baseline"
        return full_name.split("::", 1)[1]

    def request(
        self,
        endpoint: str,
        params: JSONValue,
        additional_headers: Headers | None = None,
        method: str = "POST",
        files: Any | None = None,
    ) -> httpx.Response:
        del params, additional_headers, method, files
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
        del params, additional_headers, method, files
        data = self.loader.load_response(
            provider=self.provider_name,
            endpoint=endpoint,
            test_name=self._resolve_test_name(),
            is_stream=True,
        )
        if isinstance(data, dict):
            raise TypeError(f"Expected iterator mock response, got {type(data)}")
        return data
