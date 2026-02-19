"""ORM models for llm-spec web service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from llm_spec.web.db import Base


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


class Suite(Base):
    __tablename__ = "suite"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now_utc,
        onupdate=_now_utc,
    )

    versions: Mapped[list[SuiteVersion]] = relationship(
        "SuiteVersion",
        back_populates="suite",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("provider", "endpoint", name="uq_suite_provider_endpoint"),)


class SuiteVersion(Base):
    __tablename__ = "suite_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    suite_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suite.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_json5: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)

    suite: Mapped[Suite] = relationship("Suite", back_populates="versions")

    __table_args__ = (UniqueConstraint("suite_id", "version", name="uq_suite_version"),)


class ProviderConfigModel(Base):
    __tablename__ = "provider_config"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    timeout: Mapped[float] = mapped_column(nullable=False, default=30.0)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    extra_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now_utc,
        onupdate=_now_utc,
    )


class RunJob(Base):
    __tablename__ = "run_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="real")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    suite_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suite_version.id", ondelete="SET NULL"),
        nullable=True,
    )
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunEvent(Base):
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)

    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_event_seq"),)


class RunResult(Base):
    __tablename__ = "run_result"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_job.id", ondelete="CASCADE"),
        primary_key=True,
    )
    run_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    report_md: Mapped[str] = mapped_column(Text, nullable=False)
    report_html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)


class RunTestResult(Base):
    __tablename__ = "run_test_result"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
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


Index("ix_run_job_provider_status", RunJob.provider, RunJob.status)
Index("ix_run_test_result_run_status", RunTestResult.run_id, RunTestResult.status)
