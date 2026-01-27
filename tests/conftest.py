"""Pytest fixtures for testing"""

import pytest

from llm_spec.client.http_client import HTTPClient
from llm_spec.client.logger import RequestLogger
from llm_spec.config.loader import load_config
from llm_spec.providers.anthropic import AnthropicAdapter
from llm_spec.providers.gemini import GeminiAdapter
from llm_spec.providers.openai import OpenAIAdapter
from llm_spec.providers.xai import XAIAdapter
from llm_spec.reporting.collector import ReportCollector


@pytest.fixture(scope="session")
def config():
    """加载配置"""
    return load_config("llm-spec.toml")


@pytest.fixture(scope="session")
def openai_client(config):
    """创建 OpenAI 客户端"""
    provider_config = config.get_provider_config("openai")

    # 创建 logger
    logger = RequestLogger(config.log)

    # 创建 HTTP client
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)

    # 创建 OpenAI adapter
    return OpenAIAdapter(provider_config, http_client)


@pytest.fixture
def report_collector(openai_client):
    """创建报告收集器"""
    # 这个会在每个测试模块中被覆盖，提供特定的 endpoint
    return ReportCollector(
        provider="openai",
        endpoint="/placeholder",
        base_url=openai_client.get_base_url(),
    )


@pytest.fixture(scope="session")
def anthropic_client(config):
    """创建 Anthropic 客户端"""
    provider_config = config.get_provider_config("anthropic")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    return AnthropicAdapter(provider_config, http_client)


@pytest.fixture(scope="session")
def gemini_client(config):
    """创建 Gemini 客户端"""
    provider_config = config.get_provider_config("gemini")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    return GeminiAdapter(provider_config, http_client)


@pytest.fixture(scope="session")
def xai_client(config):
    """创建 xAI 客户端"""
    provider_config = config.get_provider_config("xai")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    return XAIAdapter(provider_config, http_client)
