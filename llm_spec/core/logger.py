"""Logging utilities for LLM-Spec."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_spec.core.config import LogConfig

# Sensitive field patterns - auto-masked in log output
SENSITIVE_PATTERNS = [
    (r'"api_key"\s*:\s*"[^"]*"', '"api_key": "***"'),
    (r'"Authorization"\s*:\s*"[^"]*"', '"Authorization": "***"'),
    (r'"x-api-key"\s*:\s*"[^"]*"', '"x-api-key": "***"'),
    (r"sk-[a-zA-Z0-9]{20,}", "sk-***"),  # OpenAI style keys
    (r"sk-ant-[a-zA-Z0-9-]{20,}", "sk-ant-***"),  # Anthropic style keys
    (r"AIza[a-zA-Z0-9_-]{35}", "AIza***"),  # Google API keys
    (r"xai-[a-zA-Z0-9]{20,}", "xai-***"),  # xAI style keys
]

# Module-level flag to track if logging has been set up
_logging_initialized = False


def mask_sensitive(text: str) -> str:
    """Mask sensitive information in log output.

    Args:
        text: The text to mask

    Returns:
        Text with sensitive information replaced with ***
    """
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def get_logger(name: str = "llm_spec") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (default: "llm_spec")

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def setup_logging(config: LogConfig) -> None:
    """Setup logging based on configuration.

    Args:
        config: Log configuration instance
    """
    global _logging_initialized

    if not config.enabled:
        return

    logger = logging.getLogger("llm_spec")
    logger.setLevel(getattr(logging, config.level))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Prevent propagation to root logger
    logger.propagate = False

    # Console handler (if enabled)
    if config.console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(config.format))
        logger.addHandler(console_handler)

    # File handler (if configured)
    if config.file:
        config.file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(config.format))
        logger.addHandler(file_handler)

    _logging_initialized = True


def truncate_body(body: Any, max_length: int) -> str:
    """Truncate body for logging.

    Args:
        body: The body to truncate (dict or string)
        max_length: Maximum length to keep

    Returns:
        Truncated string representation
    """
    if body is None:
        return ""
    text = json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else str(body)
    if len(text) > max_length:
        return text[:max_length] + "...(truncated)"
    return text


def log_request(
    logger: logging.Logger,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    log_body: bool = True,
    max_length: int = 1000,
) -> None:
    """Log an outgoing HTTP request.

    Args:
        logger: Logger instance to use
        method: HTTP method (GET, POST, etc.)
        url: Full request URL
        body: Request body (optional)
        log_body: Whether to log the body
        max_length: Maximum body length to log
    """
    logger.info(f"-> {method} {url}")
    if log_body and body:
        body_str = truncate_body(body, max_length)
        logger.debug(f"   Body: {mask_sensitive(body_str)}")


def log_response(
    logger: logging.Logger,
    status_code: int,
    elapsed_ms: float = 0,
    body: Any = None,
    log_body: bool = False,
    max_length: int = 1000,
) -> None:
    """Log an incoming HTTP response.

    Args:
        logger: Logger instance to use
        status_code: HTTP status code
        elapsed_ms: Request duration in milliseconds
        body: Response body (optional)
        log_body: Whether to log the body
        max_length: Maximum body length to log
    """
    logger.info(f"<- {status_code} ({elapsed_ms:.0f}ms)")
    if log_body and body:
        body_str = truncate_body(body, max_length)
        logger.debug(f"   Body: {mask_sensitive(body_str)}")


def log_error(
    logger: logging.Logger,
    method: str,
    url: str,
    error: Exception,
    elapsed_ms: float = 0,
) -> None:
    """Log a request error.

    Args:
        logger: Logger instance to use
        method: HTTP method
        url: Request URL
        error: The exception that occurred
        elapsed_ms: Request duration in milliseconds
    """
    logger.error(f"<- ERROR {method} {url} ({elapsed_ms:.0f}ms): {error}")
