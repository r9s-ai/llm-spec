"""Pytest fixtures for testing"""

import pytest
from pathlib import Path
import json

from llm_spec.client.http_client import HTTPClient
from llm_spec.client.logger import RequestLogger
from llm_spec.config.loader import load_config
from llm_spec.providers.anthropic import AnthropicAdapter
from llm_spec.providers.gemini import GeminiAdapter
from llm_spec.providers.openai import OpenAIAdapter
from llm_spec.providers.xai import XAIAdapter
from llm_spec.reporting.collector import ReportCollector
from llm_spec.reporting.aggregator import AggregatedReportCollector


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


# 聚合报告跟踪
_aggregated_reports = {}


def pytest_configure(config):
    """Pytest 配置钩子 - 初始化聚合报告收集器"""
    # 在session开始时初始化聚合报告收集器
    pass


def pytest_sessionfinish(session, exitstatus):
    """Pytest session结束时的钩子 - 生成聚合报告

    使用方法：
    1. 运行整个厂商的测试: pytest tests/openai/
    2. 自动生成聚合报告在 reports/ 目录下
    """
    # 扫描 reports 目录下的所有 report.json
    reports_dir = Path("./reports")

    if not reports_dir.exists():
        return

    # 按 provider 分组报告
    provider_reports = {}

    for report_subdir in reports_dir.iterdir():
        if not report_subdir.is_dir():
            continue

        # 跳过已有的聚合报告
        if "aggregated" in report_subdir.name:
            continue

        report_json = report_subdir / "report.json"
        if not report_json.exists():
            continue

        try:
            with open(report_json, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
                provider = report_data.get('provider', 'unknown')

                if provider not in provider_reports:
                    provider_reports[provider] = []

                provider_reports[provider].append(report_json)
        except (json.JSONDecodeError, IOError):
            continue

    # 为每个 provider 生成聚合报告
    for provider, report_files in provider_reports.items():
        if len(report_files) <= 1:
            # 只有一个报告时，不生成聚合报告
            continue

        try:
            aggregator = AggregatedReportCollector(provider)
            aggregator.merge_reports(report_files)

            output_paths = aggregator.finalize("./reports")

            print(f"\n{'='*60}")
            print(f"✅ {provider.upper()} 聚合报告已生成:")
            print(f"  - JSON:     {output_paths['json']}")
            print(f"  - Markdown: {output_paths['markdown']}")
            print(f"  - HTML:     {output_paths['html']}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"⚠️  生成 {provider} 聚合报告失败: {e}")

