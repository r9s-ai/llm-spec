"""Model-suite Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ModelSuiteResponse(BaseModel):
    """Response model for one model-centered executable suite."""

    id: str
    model_name: str
    provider: str
    route_suite: dict[str, Any]

    model_config = {"from_attributes": True}
