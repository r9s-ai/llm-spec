from __future__ import annotations

from typing import Any, TypedDict


class TestedParameter(TypedDict):
    name: str
    value: Any


class TestParameterRecord(TypedDict):
    name: str
    value: Any
    value_type: str


class TestRequestRecord(TypedDict, total=False):
    ok: bool
    http_status: int
    latency_ms: int


class TestValidationRecord(TypedDict, total=False):
    schema_ok: bool
    required_fields_ok: bool
    stream_rules_ok: bool
    missing_fields: list[str]
    missing_events: list[str]


class TestResultRecord(TypedDict, total=False):
    status: str
    fail_stage: str | None
    reason_code: str | None
    reason: str | None


class TestTimestampsRecord(TypedDict, total=False):
    started_at: str
    finished_at: str


class TestRecord(TypedDict, total=False):
    test_id: str
    test_name: str
    parameter: TestParameterRecord
    request: TestRequestRecord
    validation: TestValidationRecord
    result: TestResultRecord
    timestamps: TestTimestampsRecord


class TestExecutionResult(TypedDict, total=False):
    test_name: str
    params: dict[str, Any]
    status_code: int
    response_body: Any
    error: str | None
    missing_fields: list[str]
    expected_fields: list[str]
    tested_param: TestedParameter | None
    is_baseline: bool
    request_ok: bool
    schema_ok: bool
    required_fields_ok: bool
    stream_rules_ok: bool
    missing_events: list[str]
    started_at: str
    finished_at: str
    latency_ms: int


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
    test_summary: TestSummary
    response_fields: dict[str, Any]
    errors: list[dict[str, Any]]
    tests: list[TestRecord]
    # allow forward/backward compatible extra keys
    details: dict[str, Any]


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
