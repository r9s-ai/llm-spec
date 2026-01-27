"""Google Gemini Provider Adapter"""

from llm_spec.providers.base import ProviderAdapter


class GeminiAdapter(ProviderAdapter):
    """Google Gemini API 适配器"""

    def prepare_headers(
        self, additional_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        """准备 Gemini 请求头

        Args:
            additional_headers: 额外的请求头

        Returns:
            包含认证的完整请求头
        """
        headers = {
            "Content-Type": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def request(
        self,
        endpoint: str,
        params: dict,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> tuple[int, dict[str, str], dict | None]:
        """发起请求（Gemini 使用 URL 参数传递 API key）

        Args:
            endpoint: API 端点
            params: 请求参数
            headers: 额外的请求头
            method: HTTP 方法

        Returns:
            (status_code, headers, response_body)
        """
        # Gemini API key 通过 URL 参数传递
        url = f"{self.config.base_url}{endpoint}?key={self.config.api_key}"
        headers = self.prepare_headers(headers)

        return self.http_client.request(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )
