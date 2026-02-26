"""Backward-compatible re-export of reporting typed dicts.

Prefer importing from `llm_spec.reporting.report_types`.
"""

from __future__ import annotations

from llm_spec.reporting.report_types import (  # noqa: F401
    ReportData,
    TestedParameter,
    TestExecutionResult,
    TestParameterRecord,
    TestRecord,
    TestRequestRecord,
    TestResultRecord,
    TestSummary,
    TestTimestampsRecord,
    TestValidationRecord,
)

__all__ = [
    "TestedParameter",
    "TestParameterRecord",
    "TestRequestRecord",
    "TestValidationRecord",
    "TestResultRecord",
    "TestTimestampsRecord",
    "TestRecord",
    "TestExecutionResult",
    "TestSummary",
    "ReportData",
]
