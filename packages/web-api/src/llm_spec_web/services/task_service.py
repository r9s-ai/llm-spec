"""Task CRUD service — create, read, update, delete, and status management."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from llm_spec.executor import cancel_task_execution as cancel_core_task_execution
from llm_spec_web.core.event_bus import event_bus
from llm_spec_web.core.exceptions import NotFoundError
from llm_spec_web.models.run import RunJob, Task
from llm_spec_web.repositories.run_repo import RunRepository
from llm_spec_web.services.suite_service import SuiteService

from ..config import settings


class TaskService:
    """Service for task-level CRUD and status management."""

    def create_task(
        self,
        db: Session,
        suite_ids: list[str],
        mode: str | None = None,
        selected_tests_by_suite: dict[str, list[str]] | None = None,
        name: str | None = None,
    ) -> tuple[Task, list[RunJob]]:
        run_repo = RunRepository(db)
        suite_service = SuiteService()
        registry = suite_service.get_registry()

        resolved_mode = mode or ("mock" if settings.mock_mode else "real")

        task = Task(
            name=name or "Task",
            status="running",
            mode=resolved_mode,
            total_runs=len(suite_ids),
            started_at=datetime.now(UTC),
        )

        run_jobs: list[RunJob] = []
        for suite_id in suite_ids:
            suite = suite_service.get_suite(suite_id)

            selected_tests = None
            if selected_tests_by_suite and suite_id in selected_tests_by_suite:
                selected_tests = selected_tests_by_suite[suite_id]

            selected_set = set(selected_tests) if selected_tests else None
            planned_cases = registry.get_execution_plan(suite_id, selected_tests=selected_set)

            run_job = RunJob(
                status="queued",
                mode=resolved_mode,
                provider=suite.provider_id,
                route=suite.route_id,
                model=suite.model_id,
                endpoint=suite.endpoint,
                suite_id=suite.suite_id,
                suite_name=suite.suite_name,
                selected_tests=selected_tests or [],
                progress_total=len(planned_cases),
                progress_done=0,
                progress_passed=0,
                progress_failed=0,
            )
            run_jobs.append(run_job)

        task, run_jobs = run_repo.create_task_with_runs(task, run_jobs)
        return task, run_jobs

    def get_task(self, db: Session, task_id: str) -> Task:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        return task

    def get_task_with_runs(self, db: Session, task_id: str) -> tuple[Task, Sequence[RunJob]]:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        runs = run_repo.list_runs_by_task(task_id)
        return task, runs

    def list_tasks(
        self,
        db: Session,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Task], int]:
        run_repo = RunRepository(db)
        return run_repo.list_tasks(status_filter=status_filter, limit=limit, offset=offset)

    def update_task(self, db: Session, task_id: str, name: str) -> Task:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        task.name = name
        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task

    def delete_task(self, db: Session, task_id: str) -> bool:
        run_repo = RunRepository(db)
        result = run_repo.delete_task(task_id)
        if result:
            db.commit()
        return result

    def update_task_status(self, db: Session, task_id: str) -> Task:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        if task.status == "cancelled":
            return task

        runs = run_repo.list_runs_by_task(task_id)

        completed = 0
        passed = 0
        failed = 0
        for run in runs:
            if run.status in {"success", "failed", "cancelled"}:
                completed += 1
                if run.status == "success":
                    passed += 1
                elif run.status == "failed":
                    failed += 1

        task.completed_runs = completed
        task.passed_runs = passed
        task.failed_runs = failed

        if completed >= task.total_runs:
            task.status = "completed"
            task.finished_at = datetime.now(UTC)

        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task

    def cancel_task_execution(self, db: Session, task_id: str) -> Task:
        """Cancel an in-progress task."""
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)

        cancel_core_task_execution(task_id)
        runs = run_repo.list_runs_by_task(task_id)
        now = datetime.now(UTC)
        for run in runs:
            if run.status in {"queued", "running"}:
                run.status = "cancelled"
                run.finished_at = now
                run_repo.update(run)
                run_repo.append_event(run.id, "run_cancelled", {"reason": "task_cancelled"})
                event_bus.push(run.id, "run_cancelled", {"reason": "task_cancelled"})
                event_bus.end_run(run.id)
                event_bus.cleanup(run.id)

        task.status = "cancelled"
        task.finished_at = now
        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task
