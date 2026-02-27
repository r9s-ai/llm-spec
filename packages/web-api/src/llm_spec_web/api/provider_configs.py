"""Provider config APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from llm_spec_web.api.deps import get_provider_service
from llm_spec_web.schemas.provider import ProviderConfigResponse
from llm_spec_web.services.provider_service import ProviderService

router = APIRouter(prefix="/api/provider-configs", tags=["provider-configs"])


@router.get("", response_model=list[ProviderConfigResponse])
def list_provider_configs(
    service: ProviderService = Depends(get_provider_service),
) -> list[ProviderConfigResponse]:
    """List all provider configurations.

    Args:
        service: Provider service.

    Returns:
        List of provider configurations.
    """
    configs = service.list_providers()
    return [ProviderConfigResponse.model_validate(c) for c in configs]


@router.get("/{provider}", response_model=ProviderConfigResponse)
def get_provider_config(
    provider: str,
    service: ProviderService = Depends(get_provider_service),
) -> ProviderConfigResponse:
    """Get a provider configuration.

    Args:
        provider: Provider name.
        service: Provider service.

    Returns:
        Provider configuration.
    """
    config = service.get_provider(provider)
    return ProviderConfigResponse.model_validate(config)
