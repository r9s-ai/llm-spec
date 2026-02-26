"""Runtime settings for llm-spec web service."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    """Environment-driven web settings."""

    database_url: str = "sqlite:///./packages/web-api/src/llm_spec_web/.data/llm_spec_web.db"
    app_toml_path: str = "llm-spec.toml"
    auto_init_db: bool = True
    suite_registry_cache_ttl_seconds: float = 2.0
    mock_base_dir: str = "packages/core/tests/integration/mocks"
    mock_mode: bool = False
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_prefix="LLM_SPEC_WEB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = WebSettings()
