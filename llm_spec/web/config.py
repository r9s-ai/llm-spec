"""Runtime settings for llm-spec web service."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    """Environment-driven web settings."""

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec"
    app_toml_path: str = "llm-spec.toml"
    mock_base_dir: str = "tests/integration/mocks"
    mock_mode: bool = False
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_prefix="LLM_SPEC_WEB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = WebSettings()
