"""Suite-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuiteCreateRequest(BaseModel):
    """Request body for creating a new suite.

    Attributes:
        provider: Provider name (e.g., "openai", "anthropic").
        route: Route key (e.g., "chat_completions").
        model: Model ID (e.g., "gpt-4o-mini").
        endpoint: API endpoint path.
        name: Human-readable suite name.
        raw_json5: Full suite JSON5 content.
        created_by: Creator identifier.
    """

    provider: str = Field(..., min_length=1, max_length=32)
    route: str = Field(..., min_length=1, max_length=128)
    model: str = Field(..., min_length=1, max_length=128)
    endpoint: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    raw_json5: str = Field(..., description="Full suite JSON5 content")
    created_by: str = Field(default="ui", max_length=128)


class SuiteUpdateRequest(BaseModel):
    """Request body for updating a suite.

    Attributes:
        name: New suite name.
        status: New suite status.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["active", "archived"] | None = None


class SuiteVersionCreateRequest(BaseModel):
    """Request body for creating a new suite version.

    Attributes:
        raw_json5: Full suite JSON5 content.
        created_by: Creator identifier.
    """

    raw_json5: str = Field(..., description="Full suite JSON5 content")
    created_by: str = Field(default="ui", max_length=128)


class SuiteVersionResponse(BaseModel):
    """Response model for suite version.

    Attributes:
        id: Version ID.
        suite_id: Parent suite ID.
        version: Version number.
        created_by: Creator identifier.
        created_at: Creation timestamp.
        raw_json5: Original JSON5 content.
        parsed_json: Parsed JSON representation.
    """

    id: str
    suite_id: str
    version: int
    created_by: str
    created_at: datetime
    raw_json5: str
    parsed_json: dict[str, Any]

    model_config = {"from_attributes": True}


class SuiteResponse(BaseModel):
    """Response model for suite.

    Attributes:
        id: Suite ID.
        provider: Provider name.
        route: Route key.
        model: Model ID.
        endpoint: API endpoint path.
        name: Suite name.
        status: Suite status.
        latest_version: Current version number.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    provider: str
    route: str
    model: str
    endpoint: str
    name: str
    status: str
    latest_version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
