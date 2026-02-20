"""Suite service for business logic."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import json5
from sqlalchemy.orm import Session

from llm_spec.runners import load_test_suite
from llm_spec.web.core.exceptions import DuplicateError, NotFoundError, ValidationError
from llm_spec.web.models.suite import Suite, SuiteVersion
from llm_spec.web.repositories.suite_repo import SuiteRepository


def parse_suite_json5(raw_json5: str) -> dict[str, Any]:
    """Parse JSON5 content and perform minimum shape checks.

    Args:
        raw_json5: Raw JSON5 content.

    Returns:
        Parsed JSON dictionary.

    Raises:
        ValidationError: If the JSON5 is invalid or missing required fields.
    """
    try:
        parsed = json5.loads(raw_json5)
    except Exception as exc:
        raise ValidationError(f"Invalid JSON5: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValidationError("Suite JSON5 must be an object")

    if "provider" not in parsed:
        raise ValidationError("Suite JSON5 missing required field: provider")

    if "endpoint" not in parsed:
        raise ValidationError("Suite JSON5 missing required field: endpoint")

    if not isinstance(parsed.get("tests"), list):
        raise ValidationError("Suite JSON5 missing required field: tests (list)")

    return parsed


def validate_suite_by_runner(raw_json5: str) -> None:
    """Validate suite using existing loader.

    Args:
        raw_json5: Raw JSON5 content.

    Raises:
        ValidationError: If the suite is invalid.
    """
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json5", encoding="utf-8", delete=False) as f:
            f.write(raw_json5)
            tmp_path = Path(f.name)
        load_test_suite(tmp_path)
    except Exception as exc:
        raise ValidationError(f"Suite validation failed: {exc}") from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


class SuiteService:
    """Service for suite-related business logic.

    This class orchestrates suite operations and manages transactions.
    """

    def create_suite(
        self,
        db: Session,
        *,
        provider: str,
        endpoint: str,
        name: str,
        raw_json5: str,
        created_by: str,
    ) -> Suite:
        """Create a suite with initial version.

        Args:
            db: Database session.
            provider: Provider name.
            endpoint: API endpoint path.
            name: Suite name.
            raw_json5: Raw JSON5 content.
            created_by: Creator identifier.

        Returns:
            Created Suite instance.

        Raises:
            DuplicateError: If suite already exists.
            ValidationError: If JSON5 is invalid.
        """
        repo = SuiteRepository(db)

        # Check if suite already exists
        existing = repo.get_by_provider_endpoint(provider, endpoint)
        if existing is not None:
            raise DuplicateError("Suite", f"{provider}/{endpoint}")

        # Parse and validate
        parsed = parse_suite_json5(raw_json5)
        validate_suite_by_runner(raw_json5)

        # Create suite
        suite = Suite(
            provider=provider,
            endpoint=endpoint,
            name=name,
            latest_version=1,
        )
        repo.create(suite)

        # Create initial version
        version = SuiteVersion(
            suite_id=suite.id,
            version=1,
            raw_json5=raw_json5,
            parsed_json=parsed,
            created_by=created_by,
        )
        repo.create_version(version)

        db.commit()
        db.refresh(suite)
        return suite

    def get_suite(self, db: Session, suite_id: str) -> Suite:
        """Get a suite by ID.

        Args:
            db: Database session.
            suite_id: Suite ID.

        Returns:
            Suite instance.

        Raises:
            NotFoundError: If suite not found.
        """
        repo = SuiteRepository(db)
        suite = repo.get_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Suite", suite_id)
        return suite

    def list_suites(
        self,
        db: Session,
        provider: str | None = None,
        endpoint: str | None = None,
    ) -> Sequence[Suite]:
        """List all suites with optional filters.

        Args:
            db: Database session.
            provider: Filter by provider name.
            endpoint: Filter by endpoint path.

        Returns:
            List of Suite instances.
        """
        repo = SuiteRepository(db)
        return repo.list_all(provider=provider, endpoint=endpoint)

    def update_suite(
        self,
        db: Session,
        suite_id: str,
        name: str | None = None,
        status: str | None = None,
    ) -> Suite:
        """Update a suite.

        Args:
            db: Database session.
            suite_id: Suite ID.
            name: New suite name.
            status: New suite status.

        Returns:
            Updated Suite instance.

        Raises:
            NotFoundError: If suite not found.
        """
        repo = SuiteRepository(db)
        suite = repo.get_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Suite", suite_id)

        if name is not None:
            suite.name = name
        if status is not None:
            suite.status = status

        repo.update(suite)
        db.commit()
        db.refresh(suite)
        return suite

    def delete_suite(self, db: Session, suite_id: str) -> None:
        """Delete a suite.

        Args:
            db: Database session.
            suite_id: Suite ID.

        Raises:
            NotFoundError: If suite not found.
        """
        repo = SuiteRepository(db)
        suite = repo.get_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Suite", suite_id)

        repo.delete(suite)
        db.commit()

    def create_version(
        self,
        db: Session,
        suite_id: str,
        raw_json5: str,
        created_by: str,
    ) -> SuiteVersion:
        """Create a new version for a suite.

        Args:
            db: Database session.
            suite_id: Suite ID.
            raw_json5: Raw JSON5 content.
            created_by: Creator identifier.

        Returns:
            Created SuiteVersion instance.

        Raises:
            NotFoundError: If suite not found.
            ValidationError: If JSON5 is invalid.
        """
        repo = SuiteRepository(db)
        suite = repo.get_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Suite", suite_id)

        # Parse and validate
        parsed = parse_suite_json5(raw_json5)
        validate_suite_by_runner(raw_json5)

        # Create new version
        next_version = suite.latest_version + 1
        version = SuiteVersion(
            suite_id=suite.id,
            version=next_version,
            raw_json5=raw_json5,
            parsed_json=parsed,
            created_by=created_by,
        )
        repo.create_version(version)

        # Update suite's latest_version
        suite.latest_version = next_version
        repo.update(suite)

        db.commit()
        db.refresh(version)
        return version

    def get_version(self, db: Session, version_id: str) -> SuiteVersion:
        """Get a suite version by ID.

        Args:
            db: Database session.
            version_id: Suite version ID.

        Returns:
            SuiteVersion instance.

        Raises:
            NotFoundError: If version not found.
        """
        repo = SuiteRepository(db)
        version = repo.get_version_by_id(version_id)
        if version is None:
            raise NotFoundError("SuiteVersion", version_id)
        return version

    def list_versions(self, db: Session, suite_id: str) -> Sequence[SuiteVersion]:
        """List all versions for a suite.

        Args:
            db: Database session.
            suite_id: Suite ID.

        Returns:
            List of SuiteVersion instances.

        Raises:
            NotFoundError: If suite not found.
        """
        repo = SuiteRepository(db)
        suite = repo.get_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Suite", suite_id)
        return repo.list_versions(suite_id)
