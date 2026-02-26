"""Settings Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TomlSettingsRequest(BaseModel):
    """Request body for updating TOML settings.

    Attributes:
        content: TOML file content.
    """

    content: str = Field(..., description="TOML file content")


class TomlSettingsResponse(BaseModel):
    """Response model for TOML settings.

    Attributes:
        path: Path to the TOML file.
        content: TOML file content.
        exists: Whether the file exists.
    """

    path: str
    content: str
    exists: bool
