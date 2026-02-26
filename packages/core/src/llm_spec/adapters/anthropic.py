"""Anthropic Provider Adapter"""

from __future__ import annotations

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.json_types import Headers


class AnthropicAdapter(ProviderAdapter):
    """Anthropic API adapter."""

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """Prepare Anthropic request headers.

        Args:
            additional_headers: extra headers

        Returns:
            full headers including auth
        """
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers
