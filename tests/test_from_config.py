"""配置驱动的测试入口

从 testcases/ 目录下的 JSON5 配置文件加载测试用例，
使用 pytest 参数化动态生成测试。

用法:
    # 运行所有配置驱动的测试
    pytest tests/test_from_config.py -v

    # 运行特定厂商的测试
    pytest tests/test_from_config.py -k "openai" -v

    # 运行特定测试
    pytest tests/test_from_config.py -k "test_param_temperature" -v
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from llm_spec.reporting.collector import ReportCollector

from tests.runners import ConfigDrivenTestRunner, SpecTestCase, SpecTestSuite, load_test_suite

if TYPE_CHECKING:
    pass


# 测试配置目录
TESTCASE_DIR = Path(__file__).parent / "testcases"

# 缓存已加载的 suite 和 collector
_SUITE_CACHE: dict[Path, SpecTestSuite] = {}
_COLLECTORS: dict[Path, ReportCollector] = {}


def _get_suite(config_path: Path) -> SpecTestSuite:
    """获取或加载 TestSuite（带缓存）"""
    if config_path not in _SUITE_CACHE:
        _SUITE_CACHE[config_path] = load_test_suite(config_path)
    return _SUITE_CACHE[config_path]


def _get_collector(config_path: Path, client: Any) -> ReportCollector:
    """获取或创建 ReportCollector（按配置路径缓存）"""
    if config_path not in _COLLECTORS:
        suite = _get_suite(config_path)
        _COLLECTORS[config_path] = ReportCollector(
            provider=suite.provider,
            endpoint=suite.endpoint,
            base_url=client.get_base_url(),
        )
    return _COLLECTORS[config_path]


def discover_test_configs() -> list[tuple[Path, str, str]]:
    """发现所有测试配置

    Returns:
        列表，每项为 (config_path, test_name, test_id)
    """
    configs: list[tuple[Path, str, str]] = []

    if not TESTCASE_DIR.exists():
        return configs

    for config_file in sorted(TESTCASE_DIR.rglob("*.json5")):
        try:
            suite = _get_suite(config_file)

            for test in suite.tests:
                # 生成可读的测试 ID
                # 例如: openai/chat_completions::test_param_temperature
                relative_path = config_file.relative_to(TESTCASE_DIR)
                test_id = f"{relative_path.with_suffix('')}::{test.name}"
                configs.append((config_file, test.name, test_id))

        except Exception as e:
            # 配置加载失败时跳过但打印警告
            print(f"Warning: Failed to load {config_file}: {e}")

    return configs


# 收集测试配置
_TEST_CONFIGS = discover_test_configs()


@pytest.mark.parametrize(
    "config_path,test_name",
    [(c[0], c[1]) for c in _TEST_CONFIGS],
    ids=[c[2] for c in _TEST_CONFIGS],
)
def test_from_config(config_path: Path, test_name: str, request: pytest.FixtureRequest):
    """从配置文件运行测试

    Args:
        config_path: JSON5 配置文件路径
        test_name: 测试名称
        request: pytest fixture request
    """
    suite = _get_suite(config_path)

    # 根据 provider 获取对应的 client fixture
    client_fixture_name = f"{suite.provider}_client"
    try:
        client = request.getfixturevalue(client_fixture_name)
    except pytest.FixtureLookupError:
        pytest.skip(f"Client fixture '{client_fixture_name}' not found")
        return

    # 获取共享的 ReportCollector
    collector = _get_collector(config_path, client)

    # 查找要运行的测试用例
    test_case: SpecTestCase | None = None
    for t in suite.tests:
        if t.name == test_name:
            test_case = t
            break

    if test_case is None:
        pytest.fail(f"Test '{test_name}' not found in config")
        return

    # 创建运行器并执行测试
    runner = ConfigDrivenTestRunner(suite, client, collector)
    success = runner.run_test(test_case)

    # 生成报告（可选，在 conftest.py 的 session 级别处理更合适）
    # output_dir = getattr(request.config, "run_reports_dir", "./reports")
    # collector.finalize(output_dir)

    # 断言测试通过
    assert success, f"Test '{test_name}' failed"


# ============================================================================
# 按 provider 分组的测试类（可选，用于更清晰的报告结构）
# ============================================================================


class TestOpenAIFromConfig:
    """OpenAI 配置驱动测试"""

    # 可以在这里添加 provider 特定的 fixture 或设置
    pass


class TestGeminiFromConfig:
    """Gemini 配置驱动测试"""

    pass


@pytest.fixture(scope="session", autouse=True)
def finalize_config_reports(request: pytest.FixtureRequest):
    """Session 结束时生成所有报告"""
    yield
    
    output_dir = getattr(request.config, "run_reports_dir", "./reports")
    
    if not _COLLECTORS:
        return

    print(f"\n生成配置驱动测试报告 (至 {output_dir})...")
    for collector in _COLLECTORS.values():
        try:
            report_path = collector.finalize(output_dir)
            print(f"✅ 报告已生成: {report_path}")
        except Exception as e:
            print(f"Warning: Failed to finalize report for {collector.endpoint}: {e}")
