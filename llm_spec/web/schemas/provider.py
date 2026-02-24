"""Provider configuration Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Supported API types
ApiType = Literal["openai", "anthropic", "gemini", "xai"]


class ProviderConfigUpsertRequest(BaseModel):
    """Request body for upserting provider configuration.

    Attributes:
        api_type: API type (openai, anthropic, gemini, xai).
        base_url: API base URL.
        timeout: Request timeout in seconds.
        api_key: API key for authentication (optional for updates).
        extra_config: Additional configuration.
    """

    api_type: ApiType = Field(default="openai", description="API type")
    base_url: str = Field(..., min_length=1, max_length=512)
    timeout: float = Field(default=30.0, ge=0.0, le=600.0)
    api_key: str | None = Field(default=None, min_length=1)
    extra_config: dict[str, Any] = Field(default_factory=dict)


class ProviderConfigResponse(BaseModel):
    """Response model for provider configuration.

    Note: API key is intentionally excluded from response for security.

    Attributes:
        provider: Provider name.
        api_type: API type (openai, anthropic, gemini, xai).
        base_url: API base URL.
        timeout: Request timeout in seconds.
        extra_config: Additional configuration.
        updated_at: Last update timestamp.
    """

    provider: str
    api_type: str
    base_url: str
    timeout: float
    extra_config: dict[str, Any]
    updated_at: datetime

    model_config = {"from_attributes": True}
