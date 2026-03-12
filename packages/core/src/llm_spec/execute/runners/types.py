"""Runner-layer data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    error_message: str | None
    missing_fields: list[str]
    expected_fields: list[str]


__all__ = ["ValidationResult"]
