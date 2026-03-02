"""API-family driven provider adapter.

This module centralizes provider authentication/header policies by api_family,
so caller code does not need one adapter class per provider.
"""

from __future__ import annotations

from collections.abc import Callable

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig
from llm_spec.json_types import Headers

HeaderBuilder = Callable[[str], dict[str, str]]


def _build_bearer_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _build_anthropic_headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }


def _build_gemini_headers(api_key: str) -> dict[str, str]:
    return {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }


API_FAMILY_HEADER_BUILDERS: dict[str, HeaderBuilder] = {
    "openai": _build_bearer_headers,
    "xai": _build_bearer_headers,
    "anthropic": _build_anthropic_headers,
    "gemini": _build_gemini_headers,
}


class APIFamilyAdapter(ProviderAdapter):
    """Generic provider adapter selected by api_family."""

    def __init__(
        self,
        config: ProviderConfig,
        http_client: HTTPClient,
        api_family: str,
    ) -> None:
        super().__init__(config=config, http_client=http_client)
        self.api_family = api_family.strip().lower()

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        builder = API_FAMILY_HEADER_BUILDERS.get(self.api_family)
        if builder is None:
            raise ValueError(f"Unsupported api_family: {self.api_family}")

        headers = builder(self.config.api_key)
        headers.update(self.config.headers)
        if additional_headers:
            headers.update(additional_headers)
        return headers


def create_api_family_adapter(
    provider: str,
    config: ProviderConfig,
    http_client: HTTPClient,
) -> APIFamilyAdapter:
    """Create a generic adapter by config.api_family fallback provider name."""
    family = (config.api_family or provider).strip().lower()
    if family not in API_FAMILY_HEADER_BUILDERS:
        raise ValueError(f"Unsupported provider/api_family: {provider}/{config.api_family}")
    return APIFamilyAdapter(config=config, http_client=http_client, api_family=family)
