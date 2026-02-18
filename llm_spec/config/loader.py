"""Config loader for llm-spec.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class LogConfig(BaseModel):
    """Logging configuration."""

    enabled: bool = True
    level: str = "INFO"
    console: bool = False
    file: str = "./logs/llm-spec.log"
    log_request_body: bool = True
    log_response_body: bool = False
    max_body_length: int = 1000


class ReportConfig(BaseModel):
    """Report configuration."""

    format: str = "both"  # terminal, json, both
    output_dir: str = "./reports"


class ProviderConfig(BaseModel):
    """Provider configuration."""

    api_key: str
    base_url: str
    timeout: float = 30.0


class AppConfig(BaseModel):
    """App configuration."""

    log: LogConfig = Field(default_factory=LogConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)

    # Dynamically loaded provider configs (Pydantic v2 disallows leading-underscore field names)
    provider_configs: dict[str, ProviderConfig] = Field(default_factory=dict, exclude=True)

    @classmethod
    def from_toml(cls, config_path: Path | str = "llm-spec.toml") -> AppConfig:
        """Load configuration from a TOML file.

        Args:
            config_path: config file path

        Returns:
            AppConfig instance
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Parse log/report sections
        log_config = LogConfig(**data.get("log", {}))
        report_config = ReportConfig(**data.get("report", {}))

        # Parse provider sections
        provider_configs = {}
        known_sections = {"log", "report"}
        for key, value in data.items():
            if key not in known_sections and isinstance(value, dict):
                # This is a provider config section
                provider_configs[key] = ProviderConfig(**value)

        config = cls(log=log_config, report=report_config)
        config.provider_configs = provider_configs

        return config

    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        """Get configuration for a provider.

        Args:
            provider_name: provider name (e.g. 'openai', 'anthropic')

        Returns:
            ProviderConfig instance

        Raises:
            KeyError: if provider config is missing
        """
        if provider_name not in self.provider_configs:
            raise KeyError(f"Provider config not found for '{provider_name}'")
        return self.provider_configs[provider_name]

    def list_providers(self) -> list[str]:
        """List all configured providers.

        Returns:
            Provider name list
        """
        return list(self.provider_configs.keys())


def load_config(config_path: Path | str = "llm-spec.toml") -> AppConfig:
    """Load global configuration.

    Args:
        config_path: config file path

    Returns:
        AppConfig instance
    """
    return AppConfig.from_toml(config_path)
