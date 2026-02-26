"""OpenAI provider adapter."""

from __future__ import annotations

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.json_types import Headers


class OpenAIAdapter(ProviderAdapter):
    """OpenAI API adapter."""

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """Prepare OpenAI request headers.

        Args:
            additional_headers: extra headers

        Returns:
            full headers including auth
        """
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers
