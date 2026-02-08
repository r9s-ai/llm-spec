"""Request/response structured logger."""

import contextvars
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_spec.config.loader import LogConfig

# Context variable for current test name (used to tag logs)
current_test_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "test_name", default=None
)


class TestNameFilter(logging.Filter):
    """Replace the log record name with the current test name."""

    def filter(self, record: logging.LogRecord) -> bool:
        test_name = current_test_name.get()
        if test_name:
            record.name = test_name
        return True


class RequestLogger:
    """Structured request/response logger."""

    def __init__(self, config: LogConfig):
        """Initialize logger.

        Args:
            config: logging config
        """
        self.config = config
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Create a configured logger instance.

        Returns:
            configured logger
        """
        logger = logging.getLogger("llm_spec")
        logger.setLevel(getattr(logging, self.config.level))
        logger.handlers.clear()  # clear existing handlers
        logger.propagate = False  # avoid propagating to root logger (e.g. pytest capture)

        # Add filter to dynamically tag records with the current test name
        test_name_filter = TestNameFilter()
        logger.addFilter(test_name_filter)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler (date-based filename)
        if self.config.file:
            from datetime import datetime

            # Convert ./logs/llm-spec.log -> ./logs/YYYY-MM-DD.log
            original_path = Path(self.config.file)
            today = datetime.now().strftime("%Y-%m-%d")
            file_path = original_path.parent / f"{today}.log"
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def generate_request_id(self) -> str:
        """Generate a unique request id.

        Returns:
            request id (UUID)
        """
        return str(uuid.uuid4())

    def _truncate_body(self, body: Any) -> Any:
        """Format request/response body (no truncation).

        Args:
            body: request/response body

        Returns:
            formatted data preserving original types (dict/list/str)
        """
        if body is None:
            return ""

        # Keep dict/list values as-is; json.dumps at the outer layer will serialize them.
        if isinstance(body, (dict, list)):
            return body

        # Fallback: stringify other types
        return str(body)

    def log_request(
        self,
        request_id: str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: Any = None,
    ) -> None:
        """Log a request.

        Args:
            request_id: request id
            method: HTTP method
            url: request URL
            headers: request headers
            body: request body
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
            # Hide sensitive headers
            safe_headers = {
                k: v if k.lower() != "authorization" else "***" for k, v in headers.items()
            }
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
        """Log a response.

        Args:
            request_id: request id
            status_code: HTTP status code
            headers: response headers
            body: response body
            duration_ms: request duration in milliseconds
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
        """Log an error.

        Args:
            request_id: request id
            error_type: error type
            error_message: error message
            details: extra details
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
