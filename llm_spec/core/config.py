"""Configuration management with file, environment, and local override support.

Configuration Priority (high to low):
1. Method parameters (local override)
2. Client instance parameters
3. Configuration file (llm-spec.toml / llm-spec.yaml)
4. Environment variables
5. Default values
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Log Configuration
# =============================================================================


class LogConfig(BaseSettings):
    """Configuration for request logging."""

    model_config = SettingsConfigDict(env_prefix="LLM_SPEC_LOG_", extra="ignore")

    enabled: bool = Field(default=False, description="Enable request logging")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Log level"
    )
    console: bool = Field(default=True, description="Output to console")
    file: Path | None = Field(default=None, description="Log file path")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )
    log_request_body: bool = Field(default=True, description="Log request body")
    log_response_body: bool = Field(
        default=False, description="Log response body (can be large)"
    )
    max_body_length: int = Field(default=1000, description="Max body length to log")


# =============================================================================
# Report Configuration
# =============================================================================


class ReportConfig(BaseSettings):
    """Configuration for validation report output."""

    model_config = SettingsConfigDict(env_prefix="LLM_SPEC_REPORT_", extra="ignore")

    format: Literal["terminal", "json", "both"] = Field(
        default="terminal", description="Output format: terminal, json, or both"
    )
    output_dir: Path | None = Field(
        default=None, description="Directory to save JSON reports"
    )
    show_valid: bool = Field(
        default=True, description="Show valid fields in terminal output"
    )
    verbose: bool = Field(default=False, description="Show verbose details")
    verbose_tests: bool = Field(
        default=False,
        description="Include all field details in test results (even for passed tests)",
    )
    include_raw_response: bool = Field(
        default=False, description="Include raw API response in reports"
    )


# =============================================================================
# Provider Configurations
# =============================================================================


class ProviderConfig(BaseSettings):
    """Configuration for a single provider."""

    model_config = SettingsConfigDict(extra="ignore")

    api_key: str | None = Field(default=None, description="API key for authentication")
    base_url: str | None = Field(default=None, description="Base URL override")
    timeout: float = Field(default=60.0, description="Request timeout in seconds")


class OpenAIConfig(ProviderConfig):
    """OpenAI specific configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_", extra="ignore")

    base_url: str | None = Field(default="https://api.openai.com/v1")


class AnthropicConfig(ProviderConfig):
    """Anthropic specific configuration."""

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", extra="ignore")

    base_url: str | None = Field(default="https://api.anthropic.com/v1")


class GeminiConfig(ProviderConfig):
    """Google Gemini specific configuration."""

    model_config = SettingsConfigDict(env_prefix="GEMINI_", extra="ignore")

    base_url: str | None = Field(
        default="https://generativelanguage.googleapis.com/v1beta"
    )


class XAIConfig(ProviderConfig):
    """xAI (Grok) specific configuration."""

    model_config = SettingsConfigDict(env_prefix="XAI_", extra="ignore")

    base_url: str | None = Field(default="https://api.x.ai/v1")


# =============================================================================
# Global Configuration
# =============================================================================


class GlobalConfig(BaseSettings):
    """Global configuration containing all provider configs and report settings."""

    model_config = SettingsConfigDict(extra="ignore")

    # Provider configurations
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    xai: XAIConfig = Field(default_factory=XAIConfig)

    # Report configuration
    report: ReportConfig = Field(default_factory=ReportConfig)

    # Log configuration
    log: LogConfig = Field(default_factory=LogConfig)


# =============================================================================
# Configuration File Loader
# =============================================================================


def _find_config_file() -> Path | None:
    """Find configuration file in current directory or parents.

    Looks for:
    - llm-spec.toml
    - llm-spec.yaml
    - llm-spec.yml
    - .llm-spec.toml
    - .llm-spec.yaml
    - .llm-spec.yml
    """
    config_names = [
        "llm-spec.toml",
        "llm-spec.yaml",
        "llm-spec.yml",
        ".llm-spec.toml",
        ".llm-spec.yaml",
        ".llm-spec.yml",
    ]

    # Start from current working directory
    current = Path.cwd()

    # Check current and parent directories
    for _ in range(10):  # Limit depth
        for name in config_names:
            config_path = current / name
            if config_path.is_file():
                return config_path

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _load_toml(path: Path) -> dict[str, Any]:
    """Load TOML configuration file."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore

    with open(path, "rb") as f:
        return tomllib.load(f)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    try:
        import yaml
    except ImportError as e:
        raise ImportError(
            "PyYAML is required for YAML config files: pip install pyyaml"
        ) from e

    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_config_file(path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration from file.

    Args:
        path: Optional explicit path to config file.
              If None, searches for config file automatically.

    Returns:
        Configuration dictionary
    """
    if path is None:
        path = _find_config_file()
        if path is None:
            return {}
    else:
        path = Path(path)

    if not path.exists():
        return {}

    suffix = path.suffix.lower()
    if suffix == ".toml":
        return _load_toml(path)
    elif suffix in (".yaml", ".yml"):
        return _load_yaml(path)
    else:
        raise ValueError(f"Unsupported config file format: {suffix}")


def create_config(config_file: Path | str | None = None) -> GlobalConfig:
    """Create GlobalConfig with file, environment, and default values.

    Args:
        config_file: Optional path to config file

    Returns:
        GlobalConfig instance
    """
    # Load from file
    file_config = load_config_file(config_file)

    # Build provider configs with file overrides
    openai_file = file_config.get("openai", {})
    anthropic_file = file_config.get("anthropic", {})
    gemini_file = file_config.get("gemini", {})
    xai_file = file_config.get("xai", {})
    report_file = file_config.get("report", {})
    log_file = file_config.get("log", {})

    return GlobalConfig(
        openai=OpenAIConfig(**openai_file),
        anthropic=AnthropicConfig(**anthropic_file),
        gemini=GeminiConfig(**gemini_file),
        xai=XAIConfig(**xai_file),
        report=ReportConfig(**report_file),
        log=LogConfig(**log_file),
    )


# =============================================================================
# Global Config Singleton
# =============================================================================

# Global config singleton - lazily loaded
_config: GlobalConfig | None = None


def get_config() -> GlobalConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = create_config()
    return _config


def reload_config(config_file: Path | str | None = None) -> GlobalConfig:
    """Reload configuration from file.

    Args:
        config_file: Optional path to config file

    Returns:
        New GlobalConfig instance
    """
    global _config
    _config = create_config(config_file)
    return _config


# =============================================================================
# Backward Compatibility - Lazy Config Accessor
# =============================================================================


class _ConfigProxy:
    """Proxy class that lazily loads the global config.

    This allows `from llm_spec.core.config import config` to work
    while still supporting lazy initialization.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_config(), name)

    def __repr__(self) -> str:
        return repr(get_config())


# Export a proxy instance for backward compatibility
config = _ConfigProxy()
