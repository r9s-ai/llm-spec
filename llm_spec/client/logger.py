"""请求/响应日志器模块"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_spec.config.loader import LogConfig


class RequestLogger:
    """结构化请求/响应日志器"""

    def __init__(self, config: LogConfig):
        """初始化日志器

        Args:
            config: 日志配置
        """
        self.config = config
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置 logger 实例

        Returns:
            配置好的 logger
        """
        logger = logging.getLogger("llm_spec")
        logger.setLevel(getattr(logging, self.config.level))
        logger.handlers.clear()  # 清除已有 handlers

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        if self.config.console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # File handler
        if self.config.file:
            file_path = Path(self.config.file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def generate_request_id(self) -> str:
        """生成唯一的请求 ID

        Returns:
            请求 ID（UUID）
        """
        return str(uuid.uuid4())

    def _truncate_body(self, body: Any) -> str:
        """截断请求/响应体到最大长度

        Args:
            body: 请求/响应体

        Returns:
            截断后的字符串
        """
        if body is None:
            return ""

        if isinstance(body, (dict, list)):
            body_str = json.dumps(body, ensure_ascii=False)
        else:
            body_str = str(body)

        max_length = self.config.max_body_length
        if len(body_str) > max_length:
            return body_str[:max_length] + f"... (截断，总长度: {len(body_str)})"
        return body_str

    def log_request(
        self,
        request_id: str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: Any = None,
    ) -> None:
        """记录请求日志

        Args:
            request_id: 请求 ID
            method: HTTP 方法
            url: 请求 URL
            headers: 请求头
            body: 请求体
        """
        if not self.config.enabled:
            return

        log_data: dict[str, Any] = {
            "request_id": request_id,
            "type": "request",
            "method": method,
            "url": url,
            "timestamp": datetime.now().isoformat(),
        }

        if headers:
            # 隐藏敏感信息
            safe_headers = {k: v if k.lower() != "authorization" else "***" for k, v in headers.items()}
            log_data["headers"] = safe_headers

        if self.config.log_request_body and body is not None:
            log_data["body"] = self._truncate_body(body)

        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    def log_response(
        self,
        request_id: str,
        status_code: int,
        headers: dict[str, str] | None = None,
        body: Any = None,
        duration_ms: float | None = None,
    ) -> None:
        """记录响应日志

        Args:
            request_id: 请求 ID
            status_code: HTTP 状态码
            headers: 响应头
            body: 响应体
            duration_ms: 请求耗时（毫秒）
        """
        if not self.config.enabled:
            return

        log_data: dict[str, Any] = {
            "request_id": request_id,
            "type": "response",
            "status_code": status_code,
            "timestamp": datetime.now().isoformat(),
        }

        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms

        if headers:
            log_data["headers"] = dict(headers)

        if self.config.log_response_body and body is not None:
            log_data["body"] = self._truncate_body(body)

        level = logging.INFO if 200 <= status_code < 400 else logging.WARNING
        self.logger.log(level, json.dumps(log_data, ensure_ascii=False))

    def log_error(
        self,
        request_id: str,
        error_type: str,
        error_message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """记录错误日志

        Args:
            request_id: 请求 ID
            error_type: 错误类型
            error_message: 错误消息
            details: 额外的错误详情
        """
        if not self.config.enabled:
            return

        log_data: dict[str, Any] = {
            "request_id": request_id,
            "type": "error",
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
        }

        if details:
            log_data["details"] = details

        self.logger.error(json.dumps(log_data, ensure_ascii=False))
