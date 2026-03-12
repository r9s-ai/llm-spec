"""Run-related ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from llm_spec_web.models.base import Base, new_id, now_utc


class Task(Base):
    """User-initiated batch execution (1:N RunJob)."""

    __tablename__ = "task"

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
        return f"<Task {self.id}:{self.status}>"


class RunJob(Base):
    """Execution job for one SuiteSpec."""

    __tablename__ = "run_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="real")

    # Suite identity
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    suite_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    suite_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Selection
    selected_tests: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Progress
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<RunJob {self.id}:{self.status}>"


class RunCase(Base):
    """ExecutableCase snapshot for retry support."""

    __tablename__ = "run_case"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Test identity
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Focus parameter
    focus_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    focus_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON, nullable=True
    )

    # Request snapshot
    request_method: Mapped[str] = mapped_column(String(16), nullable=False)
    request_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    request_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Validation rules snapshot
    response_schema: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stream_chunk_schema: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    stream_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Provenance
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_family: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (Index("uq_run_case_run_case_id", "run_id", "case_id", unique=True),)

    def __repr__(self) -> str:
        return f"<RunCase {self.run_id}:{self.test_name}>"


class RunTestResult(Base):
    """TestVerdict persistence."""

    __tablename__ = "run_test_result"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("run_case.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Test identity
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Focus parameter
    focus_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    focus_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON, nullable=True
    )

    # Verdict
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Check results
    schema_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    required_fields_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stream_rules_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Failure details
    fail_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fail_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fail_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Timing
    started_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    finished_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    def __repr__(self) -> str:
        return f"<RunTestResult {self.run_id}:{self.test_name}>"


class RunResultRecord(Base):
    """RunResult JSON archive for one run."""

    __tablename__ = "run_result_record"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        primary_key=True,
    )
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    def __repr__(self) -> str:
        return f"<RunResultRecord {self.run_id}>"


class RunEvent(Base):
    """Real-time event stream (SSE replay)."""

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


# Additional indexes
Index("ix_run_job_provider_status", RunJob.provider, RunJob.status)
Index("ix_run_job_provider_model_route", RunJob.provider, RunJob.model, RunJob.route)
Index("ix_run_test_result_run_status", RunTestResult.run_id, RunTestResult.status)
Index("ix_run_case_run_test_name", RunCase.run_id, RunCase.test_name)
