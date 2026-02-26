"""Suite CRUD and version APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from llm_spec_web.api.deps import get_db, get_suite_service
from llm_spec_web.schemas.suite import (
    SuiteCreateRequest,
    SuiteResponse,
    SuiteUpdateRequest,
    SuiteVersionCreateRequest,
    SuiteVersionResponse,
)
from llm_spec_web.services.suite_service import SuiteService

router = APIRouter(prefix="/api/suites", tags=["suites"])
version_router = APIRouter(prefix="/api/suite-versions", tags=["suite-versions"])


@router.get("", response_model=list[SuiteResponse])
def list_suites(
    provider: str | None = None,
    endpoint: str | None = None,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteResponse]:
    """List all suites with optional filters.

    Args:
        provider: Filter by provider name.
        endpoint: Filter by endpoint path.
        db: Database session.
        service: Suite service.

    Returns:
        List of suites.
    """
    suites = service.list_suites(db, provider=provider, endpoint=endpoint)
    return [SuiteResponse.model_validate(s) for s in suites]


@router.post("", response_model=SuiteResponse, status_code=status.HTTP_201_CREATED)
def create_suite(
    payload: SuiteCreateRequest,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteResponse:
    """Create a new suite.

    Args:
        payload: Suite creation request.
        db: Database session.
        service: Suite service.

    Returns:
        Created suite.
    """
    suite = service.create_suite(
        db,
        provider=payload.provider,
        endpoint=payload.endpoint,
        name=payload.name,
        raw_json5=payload.raw_json5,
        created_by=payload.created_by,
    )
    return SuiteResponse.model_validate(suite)


@router.get("/{suite_id}", response_model=SuiteResponse)
def get_suite(
    suite_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteResponse:
    """Get a suite by ID.

    Args:
        suite_id: Suite ID.
        db: Database session.
        service: Suite service.

    Returns:
        Suite details.
    """
    suite = service.get_suite(db, suite_id)
    return SuiteResponse.model_validate(suite)


@router.put("/{suite_id}", response_model=SuiteResponse)
def update_suite(
    suite_id: str,
    payload: SuiteUpdateRequest,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteResponse:
    """Update a suite.

    Args:
        suite_id: Suite ID.
        payload: Suite update request.
        db: Database session.
        service: Suite service.

    Returns:
        Updated suite.
    """
    suite = service.update_suite(
        db,
        suite_id,
        name=payload.name,
        status=payload.status,
    )
    return SuiteResponse.model_validate(suite)


@router.delete("/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(
    suite_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> None:
    """Delete a suite.

    Args:
        suite_id: Suite ID.
        db: Database session.
        service: Suite service.
    """
    service.delete_suite(db, suite_id)


@router.get("/{suite_id}/versions", response_model=list[SuiteVersionResponse])
def list_versions(
    suite_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteVersionResponse]:
    """List all versions for a suite.

    Args:
        suite_id: Suite ID.
        db: Database session.
        service: Suite service.

    Returns:
        List of suite versions.
    """
    versions = service.list_versions(db, suite_id)
    return [SuiteVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/{suite_id}/versions",
    response_model=SuiteVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    suite_id: str,
    payload: SuiteVersionCreateRequest,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteVersionResponse:
    """Create a new version for a suite.

    Args:
        suite_id: Suite ID.
        payload: Version creation request.
        db: Database session.
        service: Suite service.

    Returns:
        Created suite version.
    """
    version = service.create_version(
        db,
        suite_id,
        raw_json5=payload.raw_json5,
        created_by=payload.created_by,
    )
    return SuiteVersionResponse.model_validate(version)


@version_router.get("/{version_id}", response_model=SuiteVersionResponse)
def get_version(
    version_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteVersionResponse:
    """Get a suite version by ID.

    Args:
        version_id: Suite version ID.
        db: Database session.
        service: Suite service.

    Returns:
        Suite version details.
    """
    version = service.get_version(db, version_id)
    return SuiteVersionResponse.model_validate(version)
