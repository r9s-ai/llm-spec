"""Provider configuration repository for data access."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_spec_web.models.provider import ProviderConfigModel


class ProviderRepository:
    """Repository for ProviderConfig data access.

    This class encapsulates all database operations related to provider configurations.
    It does not manage transactions - the caller is responsible for commit/rollback.

    Attributes:
        db: SQLAlchemy session instance.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_provider(self, provider: str) -> ProviderConfigModel | None:
        """Get a provider configuration by provider name.

        Args:
            provider: Provider name.

        Returns:
            ProviderConfigModel instance or None if not found.
        """
        return self.db.get(ProviderConfigModel, provider)

    def list_all(self) -> Sequence[ProviderConfigModel]:
        """List all provider configurations.

        Returns:
            List of ProviderConfigModel instances, ordered by provider name.
        """
        stmt = select(ProviderConfigModel).order_by(ProviderConfigModel.provider.asc())
        return self.db.execute(stmt).scalars().all()

    def upsert(self, config: ProviderConfigModel) -> ProviderConfigModel:
        """Create or update a provider configuration.

        Args:
            config: ProviderConfigModel instance to create or update.

        Returns:
            Created or updated ProviderConfigModel instance.
        """
        self.db.add(config)
        self.db.flush()
        return config

    def delete(self, config: ProviderConfigModel) -> None:
        """Delete a provider configuration.

        Args:
            config: ProviderConfigModel instance to delete.
        """
        self.db.delete(config)
