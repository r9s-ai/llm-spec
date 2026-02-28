"""Config loader for llm-spec.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Provider configuration."""

    api_key: str
    base_url: str
    timeout: float = 30.0
    api_family: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    channel: str | None = None


class ChannelProviderConfig(BaseModel):
    """Per-provider selection inside a channel."""

    name: str
    routes: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)


class ChannelConfig(BaseModel):
    """Channel configuration (one API credential set shared by multiple providers)."""

    name: str
    description: str | None = None
    api_key: str
    base_url: str
    timeout: float = 30.0
    providers: list[ChannelProviderConfig] = Field(default_factory=list)


class AppConfig(BaseModel):
    """App configuration."""

    # Dynamically loaded provider configs (Pydantic v2 disallows leading-underscore field names)
    provider_configs: dict[str, ProviderConfig] = Field(default_factory=dict, exclude=True)
    channels: list[ChannelConfig] = Field(default_factory=list, exclude=True)

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

        # Parse provider sections (old style: [openai], [anthropic], ...)
        provider_configs = {}
        known_sections = {"log", "providers", "channels"}

        # New style: [providers.<name>]
        providers_section = data.get("providers", {})
        if isinstance(providers_section, dict):
            for provider, value in providers_section.items():
                if not isinstance(value, dict):
                    continue
                provider_configs[str(provider)] = ProviderConfig(**value)

        # Old style top-level provider sections
        for key, value in data.items():
            if key not in known_sections and isinstance(value, dict):
                # This is a provider config section
                provider_configs[key] = ProviderConfig(**value)

        # Channel mode
        channels: list[ChannelConfig] = []
        raw_channels = data.get("channels", [])
        if isinstance(raw_channels, list):
            for item in raw_channels:
                if not isinstance(item, dict):
                    continue
                channels.append(ChannelConfig(**item))

        config = cls(channels=channels)
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

    def get_channel(self, name: str) -> ChannelConfig:
        """Get one configured channel by name."""
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise KeyError(f"Channel config not found for '{name}'")

    def list_channels(self) -> list[str]:
        """List all configured channel names."""
        return [c.name for c in self.channels]


def load_config(config_path: Path | str = "llm-spec.toml") -> AppConfig:
    """Load global configuration.

    Args:
        config_path: config file path

    Returns:
        AppConfig instance
    """
    return AppConfig.from_toml(config_path)
