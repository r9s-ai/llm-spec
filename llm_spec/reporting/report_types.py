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


class ParameterSupportInfo(TypedDict, total=False):
    parameter: str
    request_ok: bool  # whether the request succeeded (HTTP 2xx)
    request_error: str | None  # request error message (e.g. "HTTP 400 (Bad Request)")
    validation_ok: bool  # whether schema/stream validation succeeded
    validation_error: (
        str | None
    )  # validation error message (e.g. "Missing fields: usage.total_tokens")
    http_status_code: int  # HTTP status code
    missing_fields: list[str]  # list of missing field paths
    test_name: str
    value: Any
    variant_value: str | None  # parameterized variant value (e.g. "image/webp", "512x512")


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
    parameter_support_details: list[ParameterSupportInfo]
    # allow forward/backward compatible extra keys
    details: dict[str, Any]


__all__ = [
    "UnsupportedParameter",
    "SupportedParameter",
    "ParameterSupportInfo",
    "ReportParameters",
    "TestSummary",
    "ReportData",
]
