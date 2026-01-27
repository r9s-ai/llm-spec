"""HTTP 客户端基础抽象类"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any


class BaseHTTPClient(ABC):
    """HTTP 客户端抽象基类，定义所有 HTTP 操作的接口"""

    @abstractmethod
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        """发起同步 HTTP 请求

        Args:
            method: HTTP 方法（GET, POST 等）
            url: 请求 URL
            headers: 请求头
            json: JSON 请求体
            data: Form 数据
            files: 上传文件
            timeout: 超时时间（秒）

        Returns:
            (status_code, response_headers, response_body)

        Raises:
            Exception: 各种 HTTP 或网络错误
        """
        pass

    @abstractmethod
    async def request_async(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        """发起异步 HTTP 请求

        Args:
            method: HTTP 方法（GET, POST 等）
            url: 请求 URL
            headers: 请求头
            json: JSON 请求体
            data: Form 数据
            files: 上传文件
            timeout: 超时时间（秒）

        Returns:
            (status_code, response_headers, response_body)

        Raises:
            Exception: 各种 HTTP 或网络错误
        """
        pass

    @abstractmethod
    def stream(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """发起同步流式请求（Server-Sent Events）

        Args:
            method: HTTP 方法（通常是 POST）
            url: 请求 URL
            headers: 请求头
            json: JSON 请求体
            timeout: 超时时间（秒）

        Yields:
            响应的字节流

        Raises:
            Exception: 各种 HTTP 或网络错误
        """
        pass

    @abstractmethod
    async def stream_async(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[bytes]:
        """发起异步流式请求（Server-Sent Events）

        Args:
            method: HTTP 方法（通常是 POST）
            url: 请求 URL
            headers: 请求头
            json: JSON 请求体
            timeout: 超时时间（秒）

        Yields:
            响应的字节流

        Raises:
            Exception: 各种 HTTP 或网络错误
        """
        pass
