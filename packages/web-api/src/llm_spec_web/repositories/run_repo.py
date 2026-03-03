"""Run repository for data access."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from llm_spec_web.models.run import RunCase, RunEvent, RunJob, RunTestResult, Task, TaskResultRecord


class RunRepository:
    """Repository for Run-related data access.

    This class encapsulates all database operations related to runs.
    It does not manage transactions - the caller is responsible for commit/rollback.

    Attributes:
        db: SQLAlchemy session instance.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ==================== Task Operations ====================

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: Task ID.

        Returns:
            Task instance or None if not found.
        """
        return self.db.get(Task, task_id)

    def create_task(self, task: Task) -> Task:
        """Create a new task.

        Args:
            task: Task instance to create.

        Returns:
            Created Task instance.
        """
        self.db.add(task)
        self.db.flush()
        return task

    def create_task_with_runs(
        self, task: Task, run_jobs: list[RunJob]
    ) -> tuple[Task, list[RunJob]]:
        """Create one task and its child runs in a single repository operation."""
        self.db.add(task)
        self.db.flush()
        for run_job in run_jobs:
            run_job.task_id = task.id
            self.db.add(run_job)
        self.db.flush()
        self.db.commit()
        self.db.refresh(task)
        for run_job in run_jobs:
            self.db.refresh(run_job)
        return task, run_jobs

    def update_task(self, task: Task) -> Task:
        """Update an existing task.

        Args:
            task: Task instance to update.

        Returns:
            Updated Task instance.
        """
        self.db.add(task)
        self.db.flush()
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and all associated runs.

        Args:
            task_id: Task ID.

        Returns:
            True if deleted, False if not found.
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            return False
        self.db.delete(task)
        self.db.flush()
        return True

    def list_tasks(
        self,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Task], int]:
        """List tasks with pagination.

        Args:
            status_filter: Filter by status.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            Tuple of (list of Task instances, total count).
        """
        stmt = select(Task).order_by(Task.created_at.desc())
        if status_filter:
            stmt = stmt.where(Task.status == status_filter)

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        # Get paginated results
        stmt = stmt.limit(limit).offset(offset)
        tasks = self.db.execute(stmt).scalars().all()
        return tasks, total

    def list_runs_by_task(self, task_id: str) -> Sequence[RunJob]:
        """List all runs in a task.

        Args:
            task_id: Task ID.

        Returns:
            List of RunJob instances.
        """
        stmt = (
            select(RunJob)
            .where(RunJob.task_id == task_id)
            .order_by(RunJob.started_at.desc().nulls_last())
        )
        return self.db.execute(stmt).scalars().all()

    # ==================== RunJob Operations ====================

    def get_by_id(self, run_id: str) -> RunJob | None:
        """Get a run job by ID.

        Args:
            run_id: Run job ID.

        Returns:
            RunJob instance or None if not found.
        """
        return self.db.get(RunJob, run_id)

    def list_all(self, status_filter: str | None = None) -> Sequence[RunJob]:
        """List all run jobs with optional status filter.

        Args:
            status_filter: Filter by status.

        Returns:
            List of RunJob instances.
        """
        stmt = select(RunJob).order_by(
            RunJob.started_at.desc().nulls_last(),
            RunJob.id.desc(),
        )
        if status_filter:
            stmt = stmt.where(RunJob.status == status_filter)
        return self.db.execute(stmt).scalars().all()

    def create(self, run_job: RunJob) -> RunJob:
        """Create a new run job.

        Args:
            run_job: RunJob instance to create.

        Returns:
            Created RunJob instance.
        """
        self.db.add(run_job)
        self.db.flush()
        return run_job

    def update(self, run_job: RunJob) -> RunJob:
        """Update an existing run job.

        Args:
            run_job: RunJob instance to update.

        Returns:
            Updated RunJob instance.
        """
        self.db.add(run_job)
        self.db.flush()
        return run_job

    def refresh(self, entity: object) -> None:
        """Refresh one ORM entity from database."""
        self.db.refresh(entity)

    def mark_run_running(self, run_job: RunJob, progress_total: int) -> RunJob:
        """Mark run as running and persist initial progress in one transaction."""
        run_job.status = "running"
        run_job.started_at = datetime.now(UTC)
        run_job.finished_at = None
        run_job.error_message = None
        run_job.progress_total = progress_total
        run_job.progress_done = 0
        run_job.progress_passed = 0
        run_job.progress_failed = 0
        self.update(run_job)
        self.db.commit()
        self.db.refresh(run_job)
        return run_job

    def fail_run_with_event(self, run_job: RunJob, error: str) -> RunJob:
        """Mark run as failed, append failure event, and commit."""
        run_job.status = "failed"
        run_job.error_message = error
        run_job.finished_at = datetime.now(UTC)
        self.update(run_job)
        self.append_event(run_job.id, "run_failed", {"error": error})
        self.db.commit()
        self.db.refresh(run_job)
        return run_job

    # ==================== RunEvent Operations ====================

    def get_next_seq(self, run_id: str) -> int:
        """Get the next sequence number for a run.

        Args:
            run_id: Run job ID.

        Returns:
            Next sequence number.
        """
        stmt = select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id)
        max_seq = self.db.execute(stmt).scalar_one()
        return int(max_seq or 0) + 1

    def append_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
    ) -> RunEvent:
        """Append an event to a run.

        Args:
            run_id: Run job ID.
            event_type: Event type.
            payload: Event payload.

        Returns:
            Created RunEvent instance.
        """
        seq = self.get_next_seq(run_id)
        event = RunEvent(
            run_id=run_id,
            seq=seq,
            event_type=event_type,
            payload=payload,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def append_event_and_commit(
        self,
        run_id: str,
        event_type: str,
        payload: dict,
    ) -> RunEvent:
        """Append one event and commit immediately."""
        event = self.append_event(run_id, event_type, payload)
        self.db.commit()
        return event

    def list_events(
        self,
        run_id: str,
        after_seq: int = 0,
    ) -> Sequence[RunEvent]:
        """List events for a run.

        Args:
            run_id: Run job ID.
            after_seq: Only return events with seq > after_seq.

        Returns:
            List of RunEvent instances.
        """
        stmt = (
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq.asc())
        )
        return self.db.execute(stmt).scalars().all()

    # ==================== TaskResult Operations ====================

    def get_task_result(self, run_id: str) -> TaskResultRecord | None:
        """Get the task result for a run.

        Args:
            run_id: Run job ID.

        Returns:
            TaskResultRecord instance or None if not found.
        """
        return self.db.get(TaskResultRecord, run_id)

    def save_task_result(self, result: TaskResultRecord) -> TaskResultRecord:
        """Save a task result.

        Args:
            result: TaskResultRecord instance to save.

        Returns:
            Saved TaskResultRecord instance.
        """
        self.db.merge(result)
        self.db.flush()
        return result

    # ==================== RunTestResult Operations ====================

    def add_test_result(self, test_result: RunTestResult) -> RunTestResult:
        """Add a test result.

        Args:
            test_result: RunTestResult instance to add.

        Returns:
            Created RunTestResult instance.
        """
        self.db.add(test_result)
        self.db.flush()
        return test_result

    def get_run_case(self, run_case_id: str) -> RunCase | None:
        """Get one run-case snapshot by ID."""
        return self.db.get(RunCase, run_case_id)

    def list_run_cases(self, run_id: str) -> Sequence[RunCase]:
        """List all run-case snapshots under one run."""
        stmt = select(RunCase).where(RunCase.run_id == run_id).order_by(RunCase.test_name.asc())
        return self.db.execute(stmt).scalars().all()

    def replace_run_cases(self, run_id: str, cases: list[RunCase]) -> list[RunCase]:
        """Replace run-case snapshots for one run in current transaction."""
        self.db.execute(delete(RunCase).where(RunCase.run_id == run_id))
        for case in cases:
            self.db.add(case)
        self.db.flush()
        return cases

    def upsert_test_result_by_run_case_id(
        self,
        *,
        run_id: str,
        run_case_id: str,
        test_id: str,
        test_name: str,
        parameter_value: dict | list | str | int | float | bool | None,
        status: str,
        fail_stage: str | None,
        reason_code: str | None,
        latency_ms: int | None,
        raw_record: dict,
    ) -> RunTestResult:
        """Insert or update a test result identified by ``run_case_id``."""
        stmt = select(RunTestResult).where(RunTestResult.run_case_id == run_case_id)
        row = self.db.execute(stmt).scalars().first()
        if row is None:
            row = RunTestResult(
                run_id=run_id,
                run_case_id=run_case_id,
                test_id=test_id,
                test_name=test_name,
                parameter_value=parameter_value,
                status=status,
                fail_stage=fail_stage,
                reason_code=reason_code,
                latency_ms=latency_ms,
                raw_record=raw_record,
            )
            self.db.add(row)
        else:
            row.run_id = run_id
            row.run_case_id = run_case_id
            row.test_id = test_id
            row.test_name = test_name
            row.parameter_value = parameter_value
            row.status = status
            row.fail_stage = fail_stage
            row.reason_code = reason_code
            row.latency_ms = latency_ms
            row.raw_record = raw_record
            self.db.add(row)
        self.db.flush()
        return row

    def list_test_results(self, run_id: str) -> Sequence[RunTestResult]:
        """List test results for a run.

        Args:
            run_id: Run job ID.

        Returns:
            List of RunTestResult instances.
        """
        stmt = (
            select(RunTestResult)
            .where(RunTestResult.run_id == run_id)
            .order_by(RunTestResult.test_name.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def complete_run_with_results(
        self,
        *,
        run_job: RunJob,
        progress_done: int,
        progress_passed: int,
        progress_failed: int,
        test_results: list[RunTestResult],
        task_result_json: dict,
    ) -> RunJob:
        """Persist run test rows + task result, mark final run status, and commit."""
        for row in test_results:
            self.add_test_result(row)

        self.save_task_result(
            TaskResultRecord(
                run_id=run_job.id,
                task_result_json=task_result_json,
            )
        )

        run_job.progress_done = progress_done
        run_job.progress_passed = progress_passed
        run_job.progress_failed = progress_failed
        run_job.finished_at = datetime.now(UTC)
        run_job.status = "success" if progress_failed == 0 else "failed"
        self.update(run_job)
        self.append_event(
            run_job.id,
            "run_finished",
            {
                "status": run_job.status,
                "passed": run_job.progress_passed,
                "failed": run_job.progress_failed,
            },
        )
        self.db.commit()
        self.db.refresh(run_job)
        return run_job
