"""Provider configuration ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from llm_spec.web.models.base import Base, now_utc


class ProviderConfigModel(Base):
    """Provider configuration model.

    Stores API configuration for a specific provider.

    Attributes:
        provider: Provider name (primary key).
        base_url: API base URL.
        timeout: Request timeout in seconds.
        api_key: API key for authentication.
        extra_config: Additional configuration as JSON.
        updated_at: Last update timestamp.
    """

    __tablename__ = "provider_config"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    timeout: Mapped[float] = mapped_column(nullable=False, default=30.0)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    extra_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    def __repr__(self) -> str:
        return f"<ProviderConfig {self.provider}>"
