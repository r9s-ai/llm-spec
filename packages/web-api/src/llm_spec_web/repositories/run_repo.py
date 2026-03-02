"""Run repository for data access."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from llm_spec_web.models.run import RunEvent, RunJob, RunTestResult, Task, TaskResultRecord


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

    def create(self, run: RunJob) -> RunJob:
        """Create a new run job.

        Args:
            run: RunJob instance to create.

        Returns:
            Created RunJob instance.
        """
        self.db.add(run)
        self.db.flush()
        return run

    def update(self, run: RunJob) -> RunJob:
        """Update an existing run job.

        Args:
            run: RunJob instance to update.

        Returns:
            Updated RunJob instance.
        """
        self.db.add(run)
        self.db.flush()
        return run

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

    def get_test_result_by_name(self, run_id: str, test_name: str) -> RunTestResult | None:
        """Get one test result by run ID and test name."""
        stmt = select(RunTestResult).where(
            RunTestResult.run_id == run_id,
            RunTestResult.test_name == test_name,
        )
        return self.db.execute(stmt).scalars().first()

    def upsert_test_result_by_name(
        self,
        *,
        run_id: str,
        test_name: str,
        test_id: str,
        parameter_value: dict | list | str | int | float | bool | None,
        status: str,
        fail_stage: str | None,
        reason_code: str | None,
        latency_ms: int | None,
        raw_record: dict,
    ) -> RunTestResult:
        """Insert or update a test result identified by ``run_id + test_name``."""
        row = self.get_test_result_by_name(run_id, test_name)
        if row is None:
            row = RunTestResult(
                run_id=run_id,
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
            row.test_id = test_id
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
