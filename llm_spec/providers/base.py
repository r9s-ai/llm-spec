"""Provider 适配器基类"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any

from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig


class ProviderAdapter(ABC):
    """Provider 适配器基类，使用组合模式持有 HTTPClient"""

    def __init__(self, config: ProviderConfig, http_client: HTTPClient):
        """初始化 Provider 适配器

        Args:
            config: Provider 配置
            http_client: HTTP 客户端实例
        """
        self.config = config
        self.http_client = http_client

    @abstractmethod
    def prepare_headers(self, additional_headers: dict[str, str] | None = None) -> dict[str, str]:
        """准备请求头（包括认证头）

        Args:
            additional_headers: 额外的请求头

        Returns:
            完整的请求头
        """
        pass

    def get_base_url(self) -> str:
        """获取基础 URL

        Returns:
            基础 URL
        """
        return self.config.base_url

    def request(
        self,
        endpoint: str,
        params: dict[str, Any],
        additional_headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> tuple[int, dict[str, str], Any]:
        """发起同步请求

        Args:
            endpoint: API 端点路径（如 "/v1/chat/completions"）
            params: 请求参数
            additional_headers: 额外的请求头
            method: HTTP 方法

        Returns:
            (status_code, response_headers, response_body)
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        return self.http_client.request(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )

    async def request_async(
        self,
        endpoint: str,
        params: dict[str, Any],
        additional_headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> tuple[int, dict[str, str], Any]:
        """发起异步请求

        Args:
            endpoint: API 端点路径
            params: 请求参数
            additional_headers: 额外的请求头
            method: HTTP 方法

        Returns:
            (status_code, response_headers, response_body)
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        return await self.http_client.request_async(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )

    def stream(
        self,
        endpoint: str,
        params: dict[str, Any],
        additional_headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> Iterator[bytes]:
        """发起同步流式请求

        Args:
            endpoint: API 端点路径
            params: 请求参数
            additional_headers: 额外的请求头
            method: HTTP 方法

        Yields:
            响应的字节流
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        return self.http_client.stream(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )

    def stream_async(
        self,
        endpoint: str,
        params: dict[str, Any],
        additional_headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> AsyncIterator[bytes]:
        """发起异步流式请求

        Args:
            endpoint: API 端点路径
            params: 请求参数
            additional_headers: 额外的请求头
            method: HTTP 方法

        Yields:
            响应的字节流
        """
        url = self.get_base_url().rstrip("/") + endpoint
        headers = self.prepare_headers(additional_headers)

        return self.http_client.stream_async(
            method=method,
            url=url,
            headers=headers,
            json=params,
            timeout=self.config.timeout,
        )
