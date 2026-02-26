"""Google Gemini Provider Adapter"""

from __future__ import annotations

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.json_types import Headers


class GeminiAdapter(ProviderAdapter):
    """Google Gemini API adapter."""

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """Prepare Gemini request headers.

        Args:
            additional_headers: extra headers

        Returns:
            full headers including auth
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.config.api_key,
            # "x-onr-provider":"gemini"
        }
        headers.update(self.config.headers)

        if additional_headers:
            headers.update(additional_headers)

        return headers

    # Note: Gemini does not need a custom request() override; ProviderAdapter.request already
    # supports header-based auth. Keep ProviderAdapter.request signature.
