"""xAI Provider Adapter"""

from llm_spec.providers.base import ProviderAdapter


class XAIAdapter(ProviderAdapter):
    """xAI API 适配器（使用 OpenAI 兼容接口）"""

    def prepare_headers(
        self, additional_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
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
