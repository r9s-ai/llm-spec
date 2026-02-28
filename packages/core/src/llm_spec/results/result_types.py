from __future__ import annotations

from typing import Any, Literal, Required, TypedDict


class CaseParameter(TypedDict):
    name: str | None
    value: Any
    value_type: str


class CaseRequest(TypedDict, total=False):
    method: str
    endpoint: str
    params: dict[str, Any]
    files: list[dict[str, Any]]
    ok: bool
    http_status: int
    latency_ms: int


class CaseResponse(TypedDict, total=False):
    http_status: int
    body: Any


class CaseValidation(TypedDict, total=False):
    schema_ok: bool
    required_fields_ok: bool
    stream_rules_ok: bool
    missing_fields: list[str]
    missing_events: list[str]


class CaseResultState(TypedDict, total=False):
    status: Literal["pass", "fail", "error"]
    fail_stage: str | None
    reason_code: str | None
    reason: str | None


class CaseResult(TypedDict, total=False):
    version: str
    test_id: str
    test_name: Required[str]
    is_baseline: bool
    provider: str
    model: str | None
    route: str | None
    endpoint: str
    parameter: CaseParameter
    request: CaseRequest
    response: CaseResponse
    validation: CaseValidation
    result: CaseResultState
    started_at: str
    finished_at: str
    meta: dict[str, Any]


class TaskSelection(TypedDict, total=False):
    provider: Required[str]
    model: Required[str | None]
    route: Required[str | None]
    endpoint: Required[str]


class TaskResult(TypedDict, total=False):
    version: Required[str]
    run_id: Required[str]
    started_at: Required[str]
    finished_at: Required[str]
    selection: Required[TaskSelection]
    cases: Required[list[CaseResult]]


__all__ = [
    "CaseParameter",
    "CaseRequest",
    "CaseResponse",
    "CaseValidation",
    "CaseResultState",
    "CaseResult",
    "TaskSelection",
    "TaskResult",
]
