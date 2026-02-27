"""Suite-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
