"""Suite repository for data access."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_spec_web.models.suite import Suite, SuiteVersion


class SuiteRepository:
    """Repository for Suite and SuiteVersion data access.

    This class encapsulates all database operations related to suites.
    It does not manage transactions - the caller is responsible for commit/rollback.

    Attributes:
        db: SQLAlchemy session instance.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ==================== Suite Operations ====================

    def get_by_id(self, suite_id: str) -> Suite | None:
        """Get a suite by ID.

        Args:
            suite_id: Suite ID.

        Returns:
            Suite instance or None if not found.
        """
        return self.db.get(Suite, suite_id)

    def get_by_provider_endpoint(self, provider: str, endpoint: str) -> Suite | None:
        """Get a suite by provider and endpoint.

        Args:
            provider: Provider name.
            endpoint: API endpoint path.

        Returns:
            Suite instance or None if not found.
        """
        stmt = select(Suite).where(
            Suite.provider == provider,
            Suite.endpoint == endpoint,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        provider: str | None = None,
        endpoint: str | None = None,
    ) -> Sequence[Suite]:
        """List all suites with optional filters.

        Args:
            provider: Filter by provider name.
            endpoint: Filter by endpoint path.

        Returns:
            List of Suite instances.
        """
        stmt = select(Suite)
        if provider:
            stmt = stmt.where(Suite.provider == provider)
        if endpoint:
            stmt = stmt.where(Suite.endpoint == endpoint)
        stmt = stmt.order_by(Suite.provider, Suite.endpoint)
        return self.db.execute(stmt).scalars().all()

    def create(self, suite: Suite) -> Suite:
        """Create a new suite.

        Args:
            suite: Suite instance to create.

        Returns:
            Created Suite instance (with ID populated).
        """
        self.db.add(suite)
        self.db.flush()
        return suite

    def update(self, suite: Suite) -> Suite:
        """Update an existing suite.

        Args:
            suite: Suite instance to update.

        Returns:
            Updated Suite instance.
        """
        self.db.add(suite)
        self.db.flush()
        return suite

    def delete(self, suite: Suite) -> None:
        """Delete a suite.

        Args:
            suite: Suite instance to delete.
        """
        self.db.delete(suite)

    # ==================== SuiteVersion Operations ====================

    def get_version_by_id(self, version_id: str) -> SuiteVersion | None:
        """Get a suite version by ID.

        Args:
            version_id: Suite version ID.

        Returns:
            SuiteVersion instance or None if not found.
        """
        return self.db.get(SuiteVersion, version_id)

    def list_versions(self, suite_id: str) -> Sequence[SuiteVersion]:
        """List all versions for a suite.

        Args:
            suite_id: Suite ID.

        Returns:
            List of SuiteVersion instances, ordered by version descending.
        """
        stmt = (
            select(SuiteVersion)
            .where(SuiteVersion.suite_id == suite_id)
            .order_by(SuiteVersion.version.desc())
        )
        return self.db.execute(stmt).scalars().all()

    def create_version(self, version: SuiteVersion) -> SuiteVersion:
        """Create a new suite version.

        Args:
            version: SuiteVersion instance to create.

        Returns:
            Created SuiteVersion instance.
        """
        self.db.add(version)
        self.db.flush()
        return version

    def get_latest_version(self, suite_id: str) -> SuiteVersion | None:
        """Get the latest version for a suite.

        Args:
            suite_id: Suite ID.

        Returns:
            Latest SuiteVersion instance or None if not found.
        """
        stmt = (
            select(SuiteVersion)
            .where(SuiteVersion.suite_id == suite_id)
            .order_by(SuiteVersion.version.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()
