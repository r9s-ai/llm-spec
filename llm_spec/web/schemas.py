"""Pydantic schemas for web API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuiteCreateRequest(BaseModel):
    provider: str
    endpoint: str
    name: str
    raw_json5: str = Field(..., description="Full suite JSON5 content")
    created_by: str = "ui"


class SuiteUpdateRequest(BaseModel):
    name: str | None = None
    status: Literal["active", "archived"] | None = None


class SuiteVersionCreateRequest(BaseModel):
    raw_json5: str
    created_by: str = "ui"


class SuiteVersionResponse(BaseModel):
    id: str
    suite_id: str
    version: int
    created_by: str
    created_at: datetime
    raw_json5: str
    parsed_json: dict[str, Any]


class SuiteResponse(BaseModel):
    id: str
    provider: str
    endpoint: str
    name: str
    status: str
    latest_version: int
    created_at: datetime
    updated_at: datetime


class ProviderConfigUpsertRequest(BaseModel):
    base_url: str
    timeout: float = 30.0
    api_key: str
    extra_config: dict[str, Any] = Field(default_factory=dict)


class ProviderConfigResponse(BaseModel):
    provider: str
    base_url: str
    timeout: float
    extra_config: dict[str, Any]
    updated_at: datetime


class RunCreateRequest(BaseModel):
    suite_version_id: str
    mode: Literal["real", "mock"] | None = None
    selected_tests: list[str] | None = None


class RunJobResponse(BaseModel):
    id: str
    status: str
    mode: str
    provider: str
    endpoint: str
    suite_version_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    progress_total: int
    progress_done: int
    progress_passed: int
    progress_failed: int
    error_message: str | None


class RunEventResponse(BaseModel):
    id: int
    run_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class TomlSettingsRequest(BaseModel):
    content: str


class TomlSettingsResponse(BaseModel):
    path: str
    content: str
    exists: bool
