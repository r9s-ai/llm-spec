"""Run query service — read-only operations for runs, events, and test results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from llm_spec_web.core.exceptions import NotFoundError
from llm_spec_web.models.run import RunEvent, RunJob
from llm_spec_web.repositories.run_repo import RunRepository


class RunQueryService:
    """Read-only service for querying run data."""

    def get_run(self, db: Session, run_id: str) -> RunJob:
        run_repo = RunRepository(db)
        run = run_repo.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Run", run_id)
        return run

    def list_events(self, db: Session, run_id: str, after_seq: int = 0) -> Sequence[RunEvent]:
        run_repo = RunRepository(db)
        return run_repo.list_events(run_id, after_seq=after_seq)

    def get_task_result(self, db: Session, run_id: str) -> dict[str, Any]:
        """Get the run result JSON for a run."""
        run_repo = RunRepository(db)
        result = run_repo.get_run_result(run_id)
        if result is None:
            raise NotFoundError("RunResult", run_id)
        return result.result_json

    def list_test_results(self, db: Session, run_id: str) -> list[dict]:
        """List test results for a run as dicts."""
        run_repo = RunRepository(db)
        results = run_repo.list_test_results(run_id)
        out: list[dict] = []
        for r in results:
            out.append(
                {
                    "case_id": r.case_id,
                    "test_name": r.test_name,
                    "focus_name": r.focus_name,
                    "focus_value": r.focus_value,
                    "status": r.status,
                    "latency_ms": r.latency_ms,
                    "http_status": r.http_status,
                    "schema_ok": r.schema_ok,
                    "required_fields_ok": r.required_fields_ok,
                    "stream_rules_ok": r.stream_rules_ok,
                    "fail_stage": r.fail_stage,
                    "fail_code": r.fail_code,
                    "fail_message": r.fail_message,
                    "missing_fields": r.missing_fields,
                    "missing_events": r.missing_events,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                }
            )
        return out
