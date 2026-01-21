"""LLM-Spec: A testing framework to validate LLM API responses against official specifications."""

from __future__ import annotations

from llm_spec.core.config import config
from llm_spec.core.report import FieldResult, FieldStatus, ValidationReport

__version__ = "0.1.5"

__all__ = [
    "__version__",
    "config",
    "FieldResult",
    "FieldStatus",
    "ValidationReport",
]
