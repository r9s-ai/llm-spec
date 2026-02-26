"""Dependency injection for API routes."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from llm_spec_web.config import settings
from llm_spec_web.core.db import SessionLocal
from llm_spec_web.services.provider_service import ProviderService
from llm_spec_web.services.run_service import RunService
from llm_spec_web.services.suite_service import SuiteService


def get_db() -> Generator[Session, None, None]:
    """Get database session.

    Yields:
        Session: SQLAlchemy session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache(maxsize=1)
def get_suite_service() -> SuiteService:
    """Get suite service instance.

    Returns:
        SuiteService: Suite service instance.
    """
    return SuiteService(cache_ttl_seconds=settings.suite_registry_cache_ttl_seconds)


def get_run_service() -> RunService:
    """Get run service instance.

    Returns:
        RunService: Run service instance.
    """
    return RunService()


def get_provider_service() -> ProviderService:
    """Get provider service instance.

    Returns:
        ProviderService: Provider service instance.
    """
    return ProviderService()
