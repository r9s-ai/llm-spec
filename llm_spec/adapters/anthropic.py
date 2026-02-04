"""Anthropic Provider Adapter"""

from __future__ import annotations

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.types import Headers


class AnthropicAdapter(ProviderAdapter):
    """Anthropic API 适配器"""

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """准备 Anthropic 请求头

        Args:
            additional_headers: 额外的请求头

        Returns:
            包含认证的完整请求头
        """
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers
