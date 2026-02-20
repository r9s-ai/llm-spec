"""Provider config APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from llm_spec.web.api.deps import get_db, get_provider_service
from llm_spec.web.schemas.provider import ProviderConfigResponse, ProviderConfigUpsertRequest
from llm_spec.web.services.provider_service import ProviderService

router = APIRouter(prefix="/api/provider-configs", tags=["provider-configs"])


@router.get("", response_model=list[ProviderConfigResponse])
def list_provider_configs(
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service),
) -> list[ProviderConfigResponse]:
    """List all provider configurations.

    Args:
        db: Database session.
        service: Provider service.

    Returns:
        List of provider configurations.
    """
    configs = service.list_providers(db)
    return [ProviderConfigResponse.model_validate(c) for c in configs]


@router.get("/{provider}", response_model=ProviderConfigResponse)
def get_provider_config(
    provider: str,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service),
) -> ProviderConfigResponse:
    """Get a provider configuration.

    Args:
        provider: Provider name.
        db: Database session.
        service: Provider service.

    Returns:
        Provider configuration.
    """
    config = service.get_provider(db, provider)
    return ProviderConfigResponse.model_validate(config)


@router.put("/{provider}", response_model=ProviderConfigResponse)
def upsert_provider_config(
    provider: str,
    payload: ProviderConfigUpsertRequest,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service),
) -> ProviderConfigResponse:
    """Create or update a provider configuration.

    Args:
        provider: Provider name.
        payload: Provider configuration request.
        db: Database session.
        service: Provider service.

    Returns:
        Created or updated provider configuration.
    """
    config = service.upsert_provider(
        db,
        provider=provider,
        base_url=payload.base_url,
        timeout=payload.timeout,
        api_key=payload.api_key,
        extra_config=payload.extra_config,
    )
    return ProviderConfigResponse.model_validate(config)
