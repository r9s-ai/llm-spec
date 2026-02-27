"""Provider configuration Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
