"""Settings APIs."""

from __future__ import annotations

import tomllib
from pathlib import Path

from fastapi import APIRouter, HTTPException

from llm_spec.web.config import settings
from llm_spec.web.schemas import TomlSettingsRequest, TomlSettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _toml_path() -> Path:
    return Path(settings.app_toml_path)


@router.get("/toml", response_model=TomlSettingsResponse)
def get_toml_settings() -> TomlSettingsResponse:
    path = _toml_path()
    if not path.exists():
        return TomlSettingsResponse(path=str(path), content="", exists=False)
    return TomlSettingsResponse(
        path=str(path), content=path.read_text(encoding="utf-8"), exists=True
    )


@router.put("/toml", response_model=TomlSettingsResponse)
def update_toml_settings(payload: TomlSettingsRequest) -> TomlSettingsResponse:
    # Validate TOML first to avoid writing broken config.
    try:
        tomllib.loads(payload.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid TOML: {exc}") from exc

    path = _toml_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.content, encoding="utf-8")
    return TomlSettingsResponse(path=str(path), content=payload.content, exists=True)
