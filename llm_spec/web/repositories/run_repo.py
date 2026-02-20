"""Run repository for data access."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from llm_spec.web.models.run import RunEvent, RunJob, RunResult, RunTestResult


class RunRepository:
    """Repository for Run-related data access.

    This class encapsulates all database operations related to runs.
    It does not manage transactions - the caller is responsible for commit/rollback.

    Attributes:
        db: SQLAlchemy session instance.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

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

    # ==================== RunResult Operations ====================

    def get_result(self, run_id: str) -> RunResult | None:
        """Get the result for a run.

        Args:
            run_id: Run job ID.

        Returns:
            RunResult instance or None if not found.
        """
        return self.db.get(RunResult, run_id)

    def save_result(self, result: RunResult) -> RunResult:
        """Save a run result.

        Args:
            result: RunResult instance to save.

        Returns:
            Saved RunResult instance.
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
