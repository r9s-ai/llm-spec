"""Google Gemini Provider Adapter"""

from __future__ import annotations

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.types import Headers


class GeminiAdapter(ProviderAdapter):
    """Google Gemini API 适配器"""

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """准备 Gemini 请求头

        Args:
            additional_headers: 额外的请求头

        Returns:
            包含认证的完整请求头
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.config.api_key,
            # "x-onr-provider":"gemini"
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    # Note: Gemini does not need a custom request() override; ProviderAdapter.request already
    # supports header-based auth. Keep ProviderAdapter.request signature.
