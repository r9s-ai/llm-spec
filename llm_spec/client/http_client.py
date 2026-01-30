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
    """基于 httpx 的 HTTP 客户端实现"""

    def __init__(self, logger: RequestLogger, default_timeout: float = 30.0):
        """初始化 HTTP 客户端

        Args:
            logger: 请求日志器
            default_timeout: 默认超时时间（秒）
        """
        self.logger = logger
        self.default_timeout = default_timeout

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
            with httpx.Client(timeout=timeout_val) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    data=data,
                    files=files,
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
            raise self._handle_error(request_id, error)

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
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    data=data,
                    files=files,
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
            raise self._handle_error(request_id, error)

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
            with httpx.Client(timeout=timeout_val) as client:
                with client.stream(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                ) as response:
                    # 记录响应开始
                    self.logger.log_response(
                        request_id=request_id,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=None,  # 流式响应不记录 body
                    )

                    # 流式返回数据
                    for chunk in response.iter_bytes():
                        yield chunk

        except Exception as error:
            raise self._handle_error(request_id, error)

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
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                async with client.stream(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
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
            raise self._handle_error(request_id, error)
