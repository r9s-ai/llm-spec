"""Run-related ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from llm_spec_web.models.base import Base, new_id, now_utc


class RunBatch(Base):
    """Run batch model.

    Represents a test task containing multiple runs.

    Attributes:
        id: Unique identifier (UUID).
        name: User-defined name for the batch.
        status: Batch status ("running", "completed", "cancelled").
        mode: Execution mode ("real" or "mock").
        total_runs: Total number of runs in this batch.
        completed_runs: Number of completed runs.
        passed_runs: Number of runs that passed all tests.
        failed_runs: Number of runs that had failures.
        started_at: Execution start timestamp.
        finished_at: Execution finish timestamp.
        created_at: Creation timestamp.
    """

    __tablename__ = "run_batch"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Task")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="real")
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    def __repr__(self) -> str:
        return f"<RunBatch {self.id}:{self.status}>"


class RunJob(Base):
    """Run job model.

    Represents a test execution job.

    Attributes:
        id: Unique identifier (UUID).
        status: Job status ("queued", "running", "success", "failed", "cancelled").
        mode: Execution mode ("real" or "mock").
        provider: Provider name.
        route: Route name (registry route key).
        model: Model ID.
        endpoint: API endpoint path.
        suite_version_id: Synthetic suite version ID from registry.
        config_snapshot: Configuration snapshot at run time.
        started_at: Execution start timestamp.
        finished_at: Execution finish timestamp.
        progress_total: Total number of tests.
        progress_done: Number of completed tests.
        progress_passed: Number of passed tests.
        progress_failed: Number of failed tests.
        error_message: Error message if failed.
    """

    __tablename__ = "run_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="real")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("run_batch.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    suite_version_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<RunJob {self.id}:{self.status}>"


class RunEvent(Base):
    """Run event model.

    Represents an event during test execution (e.g., test started, test finished).

    Attributes:
        id: Auto-increment event ID.
        run_id: Parent run job ID.
        seq: Sequence number within the run.
        event_type: Event type (e.g., "test_started", "test_finished").
        payload: Event data.
        created_at: Event timestamp.
    """

    __tablename__ = "run_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (Index("uq_run_event_seq", "run_id", "seq", unique=True),)

    def __repr__(self) -> str:
        return f"<RunEvent {self.run_id}:{self.seq} {self.event_type}>"


class RunResult(Base):
    """Run result model.

    Stores the final result of a completed run.

    Attributes:
        run_id: Run job ID (primary key).
        run_result_json: Full result data as JSON.
        created_at: Creation timestamp.
    """

    __tablename__ = "run_result"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        primary_key=True,
    )
    run_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    def __repr__(self) -> str:
        return f"<RunResult {self.run_id}>"


class RunTestResult(Base):
    """Individual test result model.

    Stores the result of a single test within a run.

    Attributes:
        id: Unique identifier (UUID).
        run_id: Parent run job ID.
        test_id: Test identifier.
        test_name: Test name.
        parameter_name: Parameter name being tested.
        parameter_value: Parameter value.
        status: Test status ("pass" or "fail").
        fail_stage: Stage where failure occurred (if any).
        reason_code: Failure reason code (if any).
        latency_ms: Request latency in milliseconds.
        raw_record: Full test record as JSON.
    """

    __tablename__ = "run_test_result"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_id: Mapped[str] = mapped_column(String(512), nullable=False)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parameter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parameter_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    fail_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_record: Mapped[dict] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"<RunTestResult {self.run_id}:{self.test_name}>"


# Additional indexes for common queries
Index("ix_run_job_provider_status", RunJob.provider, RunJob.status)
Index("ix_run_job_provider_model_route", RunJob.provider, RunJob.model, RunJob.route)
Index("ix_run_test_result_run_status", RunTestResult.run_id, RunTestResult.status)
