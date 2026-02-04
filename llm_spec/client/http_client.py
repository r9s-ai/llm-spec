"""HTTP 客户端 httpx 实现"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from llm_spec.client.base_client import BaseHTTPClient
from llm_spec.client.logger import RequestLogger
from llm_spec.types import Headers, JSONValue


class HTTPClient(BaseHTTPClient):
    """基于 httpx 的 HTTP 客户端实现

    使用连接池复用 HTTP 连接，提升批量请求性能。
    """

    def __init__(self, logger: RequestLogger, default_timeout: float = 30.0):
        """初始化 HTTP 客户端

        Args:
            logger: 请求日志器
            default_timeout: 默认超时时间（秒）
        """
        self.logger = logger
        self.default_timeout = default_timeout
        # 延迟初始化的 client 实例（连接池复用）
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    @property
    def sync_client(self) -> httpx.Client:
        """获取或创建同步 HTTP 客户端（复用连接池）"""
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=self.default_timeout)
        return self._sync_client

    @property
    def async_client(self) -> httpx.AsyncClient:
        """获取或创建异步 HTTP 客户端（复用连接池）"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.default_timeout)
        return self._async_client

    def close(self) -> None:
        """关闭同步客户端，释放连接池资源"""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self) -> None:
        """关闭异步客户端，释放连接池资源"""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def _handle_error(self, request_id: str, error: Exception) -> Exception:
        """处理和记录错误

        Args:
            request_id: 请求 ID
            error: 原始异常

        Returns:
            处理后的异常
        """
        if isinstance(error, httpx.TimeoutException):
            error_type = "network_error"
            error_message = f"请求超时: {error}"
        elif isinstance(error, httpx.NetworkError):
            error_type = "network_error"
            error_message = f"网络错误: {error}"
        elif isinstance(error, httpx.HTTPStatusError):
            error_type = "http_error"
            error_message = f"HTTP {error.response.status_code}: {error.response.text}"
        else:
            error_type = "unknown_error"
            error_message = str(error)

        self.logger.log_error(
            request_id=request_id,
            error_type=error_type,
            error_message=error_message,
        )

        return error

    def request(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """发起同步 HTTP 请求"""
        request_id = self.logger.generate_request_id()
        timeout_val = timeout if timeout is not None else self.default_timeout

        # 记录请求
        self.logger.log_request(
            request_id=request_id,
            method=method,
            url=url,
            headers=dict(headers) if headers is not None else None,
            body=json or data,
        )

        start_time = time.time()

        try:
            # 使用连接池复用的 client
            response = self.sync_client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                data=data,
                files=files,
                timeout=timeout_val,
            )

            duration_ms = (time.time() - start_time) * 1000

            # 记录响应
            self.logger.log_response(
                request_id=request_id,
                status_code=response.status_code,
                headers=dict(response.headers),
                body=None,
                duration_ms=duration_ms,
            )

            # 4xx 和 5xx 状态码不抛出异常，由调用者处理
            return response

        except Exception as error:
            raise self._handle_error(request_id, error) from error

    async def request_async(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """发起异步 HTTP 请求"""
        request_id = self.logger.generate_request_id()
        timeout_val = timeout if timeout is not None else self.default_timeout

        # 记录请求
        self.logger.log_request(
            request_id=request_id,
            method=method,
            url=url,
            headers=dict(headers) if headers is not None else None,
            body=json or data,
        )

        start_time = time.time()

        try:
            # 使用连接池复用的 async client
            response = await self.async_client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                data=data,
                files=files,
                timeout=timeout_val,
            )

            duration_ms = (time.time() - start_time) * 1000

            # 记录响应
            self.logger.log_response(
                request_id=request_id,
                status_code=response.status_code,
                headers=dict(response.headers),
                body=None,
                duration_ms=duration_ms,
            )

            return response

        except Exception as error:
            raise self._handle_error(request_id, error) from error

    def stream(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """发起同步流式请求（Server-Sent Events）

        Yields:
            响应的字节流
        """
        request_id = self.logger.generate_request_id()
        timeout_val = timeout if timeout is not None else self.default_timeout

        # 记录请求
        self.logger.log_request(
            request_id=request_id,
            method=method,
            url=url,
            headers=dict(headers) if headers is not None else None,
            body=json,
        )

        try:
            # 使用连接池复用的 client 进行流式请求
            with self.sync_client.stream(
                method=method,
                url=url,
                headers=headers,
                json=json,
                timeout=timeout_val,
            ) as response:
                # 记录响应开始
                self.logger.log_response(
                    request_id=request_id,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=None,  # 流式响应不记录 body
                )

                # 流式返回数据
                yield from response.iter_bytes()

        except Exception as error:
            raise self._handle_error(request_id, error) from error

    async def stream_async(
        self,
        method: str,
        url: str,
        headers: Headers | None = None,
        json: JSONValue | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[bytes]:
        """发起异步流式请求（Server-Sent Events）

        Yields:
            响应的字节流
        """
        request_id = self.logger.generate_request_id()
        timeout_val = timeout if timeout is not None else self.default_timeout

        # 记录请求
        self.logger.log_request(
            request_id=request_id,
            method=method,
            url=url,
            headers=dict(headers) if headers is not None else None,
            body=json,
        )

        try:
            # 使用连接池复用的 async client 进行流式请求
            async with self.async_client.stream(
                method=method,
                url=url,
                headers=headers,
                json=json,
                timeout=timeout_val,
            ) as response:
                # 记录响应开始
                self.logger.log_response(
                    request_id=request_id,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=None,  # 流式响应不记录 body
                )

                # 流式返回数据
                async for chunk in response.aiter_bytes():
                    yield chunk

        except Exception as error:
            raise self._handle_error(request_id, error) from error
