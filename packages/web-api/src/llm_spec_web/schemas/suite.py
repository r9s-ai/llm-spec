"""Suite Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TestDefResponse(BaseModel):
    """One test definition within a suite."""

    name: str
    description: str = ""
    baseline: bool = False
    check_stream: bool = False
    focus_name: str | None = None
    focus_value: Any = None
    tags: list[str] = []


class SuiteSpecResponse(BaseModel):
    """Response model for one expanded suite."""

    suite_id: str
    suite_name: str
    provider_id: str
    model_id: str
    route_id: str
    api_family: str
    endpoint: str
    method: str = "POST"
    tests: list[TestDefResponse] = []

    model_config = {"from_attributes": True}
