"""Backward-compatible re-export of reporting typed dicts.

Prefer importing from `llm_spec.reporting.report_types`.
"""

from __future__ import annotations

from llm_spec.reporting.report_types import (  # noqa: F401
    ParameterSupportInfo,
    ReportData,
    ReportParameters,
    SupportedParameter,
    TestSummary,
    UnsupportedParameter,
)

__all__ = [
    "UnsupportedParameter",
    "SupportedParameter",
    "ParameterSupportInfo",
    "ReportParameters",
    "TestSummary",
    "ReportData",
]
