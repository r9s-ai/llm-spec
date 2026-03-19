"""Pure data-mapping functions between domain objects and ORM/API models.

All functions here are stateless and side-effect-free.
"""

from __future__ import annotations

import dataclasses
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from llm_spec.execute.types import FailureInfo, RunResult, TestVerdict
from llm_spec.suites.types import CoverParams, ExecutableCase, HttpRequest, ValidationSpec
from llm_spec_web.models.run import RunCase, RunTestResult


def _cover_params_name(cover_params: list[CoverParams]) -> str | None:
    if not cover_params:
        return None
    if len(cover_params) == 1:
        return cover_params[0].name
    return ", ".join(param.name for param in cover_params)


def _cover_params_value(cover_params: list[CoverParams]) -> Any:
    if not cover_params:
        return None
    return [{"name": param.name, "value": deepcopy(param.value)} for param in cover_params]


def _cover_params_from_row(name: str | None, value: Any) -> list[CoverParams]:
    if isinstance(value, list):
        out: list[CoverParams] = []
        for item in value:
            if isinstance(item, dict) and "name" in item:
                out.append(CoverParams(name=str(item["name"]), value=item.get("value")))
        if out:
            return out
    if name:
        return [CoverParams(name=name, value=value)]
    return []


def test_case_to_run_case(run_id: str, case: ExecutableCase) -> RunCase:
    """Persist a ExecutableCase as a RunCase snapshot."""
    return RunCase(
        run_id=run_id,
        case_id=case.case_id,
        test_name=case.test_name,
        description=case.description,
        is_baseline=case.is_baseline,
        tags=list(case.tags),
        cover_params_name=_cover_params_name(case.cover_params),
        cover_params_value=_cover_params_value(case.cover_params),
        request_method=case.request.method,
        request_endpoint=case.request.endpoint,
        request_params=deepcopy(case.request.params),
        request_files=deepcopy(case.request.files) if case.request.files else None,
        request_stream=case.request.stream,
        response_schema=case.checks.response_schema,
        stream_chunk_schema=case.checks.stream_chunk_schema,
        required_fields=list(case.checks.required_fields),
        stream_rules=deepcopy(case.checks.stream_rules) if case.checks.stream_rules else None,
        provider=case.provider,
        model=case.model,
        route=case.route,
        api_family=case.api_family,
    )


def run_case_to_test_case(run_case: RunCase) -> ExecutableCase:
    """Reconstruct a ExecutableCase from a persisted RunCase snapshot."""
    return ExecutableCase(
        case_id=run_case.case_id,
        test_name=run_case.test_name,
        description=run_case.description,
        is_baseline=bool(run_case.is_baseline),
        tags=list(run_case.tags),
        cover_params=_cover_params_from_row(
            run_case.cover_params_name, run_case.cover_params_value
        ),
        request=HttpRequest(
            method=run_case.request_method,
            endpoint=run_case.request_endpoint,
            params=deepcopy(run_case.request_params),
            files=deepcopy(run_case.request_files) if run_case.request_files else None,
            stream=bool(run_case.request_stream),
        ),
        checks=ValidationSpec(
            response_schema=run_case.response_schema,
            stream_chunk_schema=run_case.stream_chunk_schema,
            required_fields=list(run_case.required_fields),
            stream_rules=deepcopy(run_case.stream_rules) if run_case.stream_rules else None,
        ),
        provider=run_case.provider,
        model=run_case.model,
        route=run_case.route,
        api_family=run_case.api_family,
    )


def verdict_to_test_result_row(
    run_id: str, run_case_id: str | None, verdict: TestVerdict
) -> RunTestResult:
    """Map a TestVerdict to a RunTestResult ORM row."""
    return RunTestResult(
        run_id=run_id,
        run_case_id=run_case_id,
        case_id=verdict.case_id,
        test_name=verdict.test_name,
        cover_params_name=_cover_params_name(verdict.cover_params),
        cover_params_value=_cover_params_value(verdict.cover_params),
        status=verdict.status,
        latency_ms=verdict.latency_ms,
        http_status=verdict.http_status,
        schema_ok=verdict.schema_ok,
        required_fields_ok=verdict.required_fields_ok,
        stream_rules_ok=verdict.stream_rules_ok,
        fail_stage=verdict.failure.stage if verdict.failure else None,
        fail_code=verdict.failure.code if verdict.failure else None,
        fail_message=verdict.failure.message if verdict.failure else None,
        missing_fields=list(verdict.failure.missing_fields) if verdict.failure else [],
        missing_events=list(verdict.failure.missing_events) if verdict.failure else [],
        started_at=verdict.started_at,
        finished_at=verdict.finished_at,
    )


def error_verdict(case: ExecutableCase, error: Exception) -> TestVerdict:
    """Build an error TestVerdict for a case that failed before execution."""
    now = datetime.now(UTC).isoformat()
    return TestVerdict(
        case_id=case.case_id,
        test_name=case.test_name,
        cover_params=case.cover_params,
        status="error",
        started_at=now,
        finished_at=now,
        failure=FailureInfo(
            stage="request",
            code="REQUEST_ERROR",
            message=str(error),
        ),
    )


def verdict_to_dict(verdict: TestVerdict) -> dict[str, Any]:
    """Serialize a TestVerdict to a JSON-safe dict."""
    return dataclasses.asdict(verdict)


def verdict_to_case_row(verdict: TestVerdict, run_case_id: str | None = None) -> dict[str, Any]:
    """Convert a TestVerdict into the front-end TestResultRow shape."""
    row: dict[str, Any] = {
        "test_name": verdict.test_name,
    }
    if run_case_id:
        row["run_case_id"] = run_case_id
    if verdict.cover_params:
        primary = verdict.cover_params[0]
        row["parameter"] = {
            "name": primary.name,
            "value": primary.value,
            "value_type": type(primary.value).__name__ if primary.value is not None else "str",
        }
        row["parameters"] = [
            {
                "name": param.name,
                "value": param.value,
                "value_type": type(param.value).__name__ if param.value is not None else "str",
            }
            for param in verdict.cover_params
        ]
    if verdict.http_status is not None or verdict.latency_ms is not None:
        row["request"] = {
            "http_status": verdict.http_status or 0,
            "latency_ms": verdict.latency_ms or 0,
        }
    row["result"] = {
        "status": verdict.status,
    }
    if verdict.failure:
        row["result"]["reason"] = verdict.failure.message
    row["validation"] = {
        "schema_ok": verdict.schema_ok,
        "required_fields_ok": verdict.required_fields_ok,
        "stream_rules_ok": verdict.stream_rules_ok,
        "missing_fields": verdict.failure.missing_fields if verdict.failure else [],
        "missing_events": verdict.failure.missing_events if verdict.failure else [],
    }
    return row


def run_result_to_dict(
    result: RunResult,
    case_id_to_run_case_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Serialize a RunResult to the JSON shape expected by the front-end."""
    mapping = case_id_to_run_case_id or {}
    return {
        "version": result.version,
        "run_id": result.run_id,
        "cases": [verdict_to_case_row(v, mapping.get(v.case_id)) for v in result.verdicts],
    }
