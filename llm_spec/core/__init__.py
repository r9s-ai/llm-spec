"""Core module containing base abstractions and utilities."""

from __future__ import annotations

from llm_spec.core.client import BaseClient
from llm_spec.core.config import config, ProviderConfig
from llm_spec.core.exceptions import ConfigError, LLMSpecError, RequestError, ValidationError
from llm_spec.core.report import FieldResult, FieldStatus, ValidationReport
from llm_spec.core.validator import SchemaValidator

__all__ = [
    "BaseClient",
    "config",
    "ConfigError",
    "FieldResult",
    "FieldStatus",
    "LLMSpecError",
    "ProviderConfig",
    "RequestError",
    "SchemaValidator",
    "ValidationError",
    "ValidationReport",
]
