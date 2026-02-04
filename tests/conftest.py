"""Pytest fixtures for testing"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.client.logger import RequestLogger
from llm_spec.config.loader import load_config
from llm_spec.reporting.aggregator import AggregatedReportCollector
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
    adapter = OpenAIAdapter(provider_config, http_client)

    yield adapter

    # session 结束时关闭连接池
    http_client.close()


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
    adapter = AnthropicAdapter(provider_config, http_client)

    yield adapter

    # session 结束时关闭连接池
    http_client.close()


@pytest.fixture(scope="session")
def gemini_client(config):
    """创建 Gemini 客户端"""
    provider_config = config.get_provider_config("gemini")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    adapter = GeminiAdapter(provider_config, http_client)

    yield adapter

    # session 结束时关闭连接池
    http_client.close()


@pytest.fixture(scope="session")
def xai_client(config):
    """创建 xAI 客户端"""
    provider_config = config.get_provider_config("xai")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    adapter = XAIAdapter(provider_config, http_client)

    yield adapter

    # session 结束时关闭连接池
    http_client.close()


# 聚合报告跟踪
_aggregated_reports: dict[str, list[Path]] = {}

# 本次 pytest run 的报告根目录（隔离历史 run，避免统计混入旧报告）
_RUN_REPORTS_DIR: Path | None = None


def pytest_configure(config):
    """Pytest 配置钩子 - 初始化聚合报告收集器"""
    # 在session开始时初始化聚合报告收集器
    global _RUN_REPORTS_DIR

    # 以时间戳作为 run_id；所有报告统一写入 reports/<run_id>/
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 报告根目录优先使用 llm-spec.toml 的 [report].output_dir（由 AppConfig.report.output_dir 提供）
    # 若未配置则回退到 ./reports
    try:
        from llm_spec.config.loader import get_config

        report_root = Path(get_config().report.output_dir)
    except Exception:
        report_root = Path("./reports")

    _RUN_REPORTS_DIR = report_root / run_id
    _RUN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 让测试用例/collector 能拿到本次 run 的输出目录
    config.run_reports_dir = str(_RUN_REPORTS_DIR)  # type: ignore[attr-defined]


def pytest_sessionfinish(session, exitstatus):
    """Pytest session结束时的钩子 - 处理单个报告和聚合报告

    使用方法：
    1. 运行单个测试文件: pytest tests/openai/test_chat_completions.py
       → 生成单个 endpoint 报告

    2. 运行整个厂商目录: pytest tests/openai/
       → 生成单个 endpoint 报告 + 聚合报告（若有多个endpoint）
    """
    global _RUN_REPORTS_DIR
    # 只扫描本次 run 产生的报告，避免与历史 run 混淆
    reports_dir = _RUN_REPORTS_DIR or Path("./reports")

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
            with open(report_json, encoding="utf-8") as f:
                report_data = json.load(f)
                provider = report_data.get("provider", "unknown")

                if provider not in provider_reports:
                    provider_reports[provider] = []

                provider_reports[provider].append(report_json)
        except (OSError, json.JSONDecodeError):
            continue

    # 处理每个 provider 的报告
    for provider, report_files in provider_reports.items():
        if len(report_files) == 1:
            # 单个报告 - 只打印单个报告信息
            _print_single_report_info(report_files[0])

        elif len(report_files) > 1:
            # 多个报告 - 生成聚合报告并打印信息
            try:
                aggregator = AggregatedReportCollector(provider)
                aggregator.merge_reports(report_files)

                output_dir = getattr(session.config, "run_reports_dir", "./reports")
                output_paths = aggregator.finalize(output_dir)

                _print_aggregated_report_info(provider, report_files, output_paths)
            except Exception as e:
                print(f"⚠️  生成 {provider} 聚合报告失败: {e}")


def _print_single_report_info(report_json: Path) -> None:
    """打印单个报告信息"""
    try:
        with open(report_json, encoding="utf-8") as f:
            report = json.load(f)

        endpoint = report.get("endpoint", "unknown")
        provider = report.get("provider", "unknown")
        summary = report.get("test_summary", {})

        print(f"\n{'=' * 60}")
        print(f"✅ {provider.upper()} - {endpoint} 报告已生成:")
        print(f"  - 总测试数: {summary.get('total_tests', 0)}")
        print(f"  - 通过: {summary.get('passed', 0)} ✅")
        print(f"  - 失败: {summary.get('failed', 0)} ❌")
        print(f"  - 报告路径: {report_json.parent.name}/")
        print("    - JSON:     report.json")
        print("    - Markdown: report.md")
        print("    - HTML:     report.html")
        print(f"{'=' * 60}\n")
    except Exception as e:
        print(f"⚠️  读取报告失败: {e}")


def _print_aggregated_report_info(provider: str, report_files: list, output_paths: dict) -> None:
    """打印聚合报告信息"""
    try:
        with open(output_paths["json"], encoding="utf-8") as f:
            aggregated = json.load(f)

        summary = aggregated.get("summary", {})

        print(f"\n{'=' * 70}")
        print(f"📊 {provider.upper()} 聚合报告已生成 (汇总 {len(report_files)} 个 endpoint)")
        print(f"{'=' * 70}")
        print("")
        print("📈 统计摘要:")
        print(f"  - 总测试数: {summary.get('test_summary', {}).get('total_tests', 0)}")
        print(f"  - 通过: {summary.get('test_summary', {}).get('passed', 0)} ✅")
        print(f"  - 失败: {summary.get('test_summary', {}).get('failed', 0)} ❌")
        print(f"  - 通过率: {summary.get('test_summary', {}).get('pass_rate', 'N/A')}")
        print("")
        print(f"🔗 Endpoint ({len(report_files)}):")
        for endpoint in summary.get("endpoints", []):
            print(f"  - {endpoint}")
        print("")
        print("📋 参数统计:")
        params = summary.get("parameters", {})
        print(f"  - 总参数数: {params.get('total_unique', 0)}")
        print(f"  - 完全支持: {params.get('fully_supported', 0)}")
        print(f"  - 部分支持: {params.get('partially_supported', 0)}")
        print(f"  - 完全不支持: {params.get('unsupported', 0)}")
        print("")
        print("📄 生成的文件:")
        print(f"  - JSON:     {output_paths['json']}")
        print(f"  - Markdown: {output_paths['markdown']}")
        print(f"  - HTML:     {output_paths['html']}")
        print(f"{'=' * 70}\n")
    except Exception as e:
        print(f"⚠️  打印聚合报告信息失败: {e}")
