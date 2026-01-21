"""Custom exceptions for LLM-Spec."""

from __future__ import annotations


class LLMSpecError(Exception):
    """Base exception for all LLM-Spec errors."""


class ConfigError(LLMSpecError):
    """Configuration related errors."""


class RequestError(LLMSpecError):
    """HTTP request errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ValidationError(LLMSpecError):
    """Schema validation errors."""

    def __init__(self, message: str, field_path: str | None = None) -> None:
        super().__init__(message)
        self.field_path = field_path
