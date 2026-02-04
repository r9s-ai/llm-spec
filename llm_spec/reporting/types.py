from __future__ import annotations

from typing import Any, TypedDict


class UnsupportedParameter(TypedDict, total=False):
    parameter: str
    reason: str
    error_type: str
    status_code: int
    test_name: str
    value: Any


class SupportedParameter(TypedDict):
    parameter: str


class ReportParameters(TypedDict, total=False):
    tested: list[str]
    untested: list[str]
    supported: list[SupportedParameter]
    unsupported: list[UnsupportedParameter]


class TestSummary(TypedDict, total=False):
    total_tests: int
    passed: int
    failed: int
    skipped: int


class ReportData(TypedDict, total=False):
    provider: str
    endpoint: str
    test_time: str
    base_url: str
    parameters: ReportParameters
    test_summary: TestSummary
    response_fields: dict[str, Any]
    errors: list[dict[str, Any]]
    # allow forward/backward compatible extra keys
    details: dict[str, Any]
