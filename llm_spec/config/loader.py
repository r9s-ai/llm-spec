"""配置加载器模块，解析 llm-spec.toml 配置文件"""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogConfig(BaseModel):
    """日志配置"""

    enabled: bool = True
    level: str = "INFO"
    console: bool = False
    file: str = "./logs/llm-spec.log"
    log_request_body: bool = True
    log_response_body: bool = False
    max_body_length: int = 1000


class ReportConfig(BaseModel):
    """报告配置"""

    format: str = "both"  # terminal, json, both
    output_dir: str = "./reports"


class ProviderConfig(BaseModel):
    """Provider 配置"""

    api_key: str
    base_url: str
    timeout: float = 30.0


class AppConfig(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        extra="allow",  # 允许额外字段（provider configs）
    )

    log: LogConfig = Field(default_factory=LogConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)

    # Provider configs 动态加载
    _provider_configs: dict[str, ProviderConfig] = {}

    @classmethod
    def from_toml(cls, config_path: Path | str = "llm-spec.toml") -> "AppConfig":
        """从 TOML 文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            AppConfig 实例
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # 提取日志和报告配置
        log_config = LogConfig(**data.get("log", {}))
        report_config = ReportConfig(**data.get("report", {}))

        # 提取 provider 配置
        provider_configs = {}
        known_sections = {"log", "report"}
        for key, value in data.items():
            if key not in known_sections and isinstance(value, dict):
                # 这是一个 provider 配置
                provider_configs[key] = ProviderConfig(**value)

        config = cls(log=log_config, report=report_config)
        config._provider_configs = provider_configs

        return config

    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        """获取指定 provider 的配置

        Args:
            provider_name: Provider 名称（如 'openai', 'anthropic'）

        Returns:
            ProviderConfig 实例

        Raises:
            KeyError: 如果 provider 配置不存在
        """
        if provider_name not in self._provider_configs:
            raise KeyError(f"未找到 provider '{provider_name}' 的配置")
        return self._provider_configs[provider_name]

    def list_providers(self) -> list[str]:
        """列出所有配置的 providers

        Returns:
            Provider 名称列表
        """
        return list(self._provider_configs.keys())


# 全局配置实例（懒加载）
_global_config: AppConfig | None = None


def load_config(config_path: Path | str = "llm-spec.toml") -> AppConfig:
    """加载全局配置

    Args:
        config_path: 配置文件路径

    Returns:
        AppConfig 实例
    """
    global _global_config
    _global_config = AppConfig.from_toml(config_path)
    return _global_config


def get_config() -> AppConfig:
    """获取全局配置实例

    Returns:
        AppConfig 实例

    Raises:
        RuntimeError: 如果配置未加载
    """
    if _global_config is None:
        raise RuntimeError("配置未加载，请先调用 load_config()")
    return _global_config
