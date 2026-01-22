"""Core module containing base abstractions and utilities."""

from __future__ import annotations

from llm_spec.core.client import BaseClient
from llm_spec.core.config import LogConfig, ProviderConfig, config
from llm_spec.core.exceptions import ConfigError, LLMSpecError, RequestError, ValidationError
from llm_spec.core.logger import get_logger, setup_logging
from llm_spec.core.report import FieldResult, FieldStatus, ValidationReport
from llm_spec.core.validator import SchemaValidator

__all__ = [
    "BaseClient",
    "config",
    "ConfigError",
    "FieldResult",
    "FieldStatus",
    "get_logger",
    "LLMSpecError",
    "LogConfig",
    "ProviderConfig",
    "RequestError",
    "SchemaValidator",
    "setup_logging",
    "ValidationError",
    "ValidationReport",
]
