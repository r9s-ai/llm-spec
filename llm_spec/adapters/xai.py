"""xAI Provider Adapter"""

from __future__ import annotations

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.types import Headers


class XAIAdapter(ProviderAdapter):
    """xAI API 适配器（使用 OpenAI 兼容接口）"""

    def prepare_headers(self, additional_headers: Headers | None = None) -> dict[str, str]:
        """准备 xAI 请求头

        Args:
            additional_headers: 额外的请求头

        Returns:
            包含认证的完整请求头
        """
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers
