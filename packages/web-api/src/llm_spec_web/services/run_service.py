"""Run service — backward-compatible facade delegating to split services.

This module preserves the ``RunService`` class interface used by API routes.
Actual logic lives in:
  - ``task_service.TaskService`` — Task CRUD and status management
  - ``run_query_service.RunQueryService`` — Read-only run/event/result queries
  - ``run_execution_service.RunExecutionService`` — Async execution orchestration
  - ``mappers`` — Pure data-mapping functions
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from llm_spec_web.models.run import RunEvent, RunJob, Task
from llm_spec_web.services.run_execution_service import (
    RunExecutionContext,
    RunExecutionService,
    create_provider_client,
)
from llm_spec_web.services.run_query_service import RunQueryService
from llm_spec_web.services.task_service import TaskService


class RunService:
    """Backward-compatible facade over TaskService, RunQueryService, and RunExecutionService."""

    def __init__(self) -> None:
        self._task = TaskService()
        self._query = RunQueryService()
        self._exec = RunExecutionService()

    # ── Task CRUD (delegates to TaskService) ──────────────

    def create_task(
        self,
        db: Session,
        suite_ids: list[str],
        mode: str | None = None,
        selected_tests_by_suite: dict[str, list[str]] | None = None,
        name: str | None = None,
    ) -> tuple[Task, list[RunJob]]:
        return self._task.create_task(db, suite_ids, mode, selected_tests_by_suite, name)

    def get_task(self, db: Session, task_id: str) -> Task:
        return self._task.get_task(db, task_id)

    def get_task_with_runs(self, db: Session, task_id: str) -> tuple[Task, Sequence[RunJob]]:
        return self._task.get_task_with_runs(db, task_id)

    def list_tasks(
        self,
        db: Session,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Task], int]:
        return self._task.list_tasks(db, status_filter, limit, offset)

    def update_task(self, db: Session, task_id: str, name: str) -> Task:
        return self._task.update_task(db, task_id, name)

    def delete_task(self, db: Session, task_id: str) -> bool:
        return self._task.delete_task(db, task_id)

    def update_task_status(self, db: Session, task_id: str) -> Task:
        return self._task.update_task_status(db, task_id)

    def cancel_task_execution(self, db: Session, task_id: str) -> Task:
        return self._task.cancel_task_execution(db, task_id)

    # ── Run queries (delegates to RunQueryService) ────────

    def get_run(self, db: Session, run_id: str) -> RunJob:
        return self._query.get_run(db, run_id)

    def list_events(self, db: Session, run_id: str, after_seq: int = 0) -> Sequence[RunEvent]:
        return self._query.list_events(db, run_id, after_seq)

    def get_task_result(self, db: Session, run_id: str) -> dict[str, Any]:
        return self._query.get_task_result(db, run_id)

    def list_test_results(self, db: Session, run_id: str) -> list[dict]:
        return self._query.list_test_results(db, run_id)

    # ── Execution (delegates to RunExecutionService) ──────

    def retry_test_in_run(self, db: Session, run_id: str, run_case_id: str) -> RunJob:
        return self._exec.retry_test_in_run(db, run_id, run_case_id)

    def execute_run(self, db: Session, run_id: str, max_concurrent: int = 5) -> None:
        return self._exec.execute_run(db, run_id, max_concurrent)

    def execute_task(
        self,
        db: Session,
        task_id: str,
        *,
        max_concurrent: int = 5,
        run_concurrency: int = 2,
    ) -> None:
        return self._exec.execute_task(
            db, task_id, max_concurrent=max_concurrent, run_concurrency=run_concurrency
        )

    async def run_by_context(self, context: RunExecutionContext) -> None:
        return await self._exec.run_by_context(context)


# Re-export for backward compatibility
__all__ = ["RunService", "RunExecutionContext", "create_provider_client"]
