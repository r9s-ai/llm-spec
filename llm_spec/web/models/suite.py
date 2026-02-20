"""Suite and SuiteVersion ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from llm_spec.web.models.base import Base, new_id, now_utc


class Suite(Base):
    """Test suite model.

    A suite represents a collection of tests for a specific provider endpoint.

    Attributes:
        id: Unique identifier (UUID).
        provider: Provider name (e.g., "openai", "anthropic").
        endpoint: API endpoint path (e.g., "/v1/chat/completions").
        name: Human-readable suite name.
        status: Suite status ("active" or "archived").
        latest_version: Current version number.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        versions: List of suite versions.
    """

    __tablename__ = "suite"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    versions: Mapped[list[SuiteVersion]] = relationship(
        "SuiteVersion",
        back_populates="suite",
        cascade="all, delete-orphan",
        order_by="SuiteVersion.version.desc()",
    )

    __table_args__ = (UniqueConstraint("provider", "endpoint", name="uq_suite_provider_endpoint"),)

    def __repr__(self) -> str:
        return f"<Suite {self.provider}:{self.endpoint} v{self.latest_version}>"


class SuiteVersion(Base):
    """Suite version model.

    A version represents a snapshot of a suite's JSON5 content.

    Attributes:
        id: Unique identifier (UUID).
        suite_id: Parent suite ID.
        version: Version number.
        raw_json5: Original JSON5 content.
        parsed_json: Parsed JSON representation.
        created_by: Creator identifier.
        created_at: Creation timestamp.
        suite: Parent suite relationship.
    """

    __tablename__ = "suite_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    suite: Mapped[Suite] = relationship("Suite", back_populates="versions")

    __table_args__ = (UniqueConstraint("suite_id", "version", name="uq_suite_version"),)

    def __repr__(self) -> str:
        return f"<SuiteVersion {self.suite_id}:v{self.version}>"
