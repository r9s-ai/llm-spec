"""配置驱动的测试运行器"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Type

if TYPE_CHECKING:
    from pydantic import BaseModel

import json5

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.validator import ResponseValidator

from .parsers import StreamParser
from .schema_registry import get_schema


@dataclass
class SpecTestCase:
    """单个测试用例"""

    name: str
    """测试名称"""

    description: str = ""
    """测试描述"""

    params: dict[str, Any] = field(default_factory=dict)
    """测试参数（会与 base_params 合并）"""

    unsupported_param: str = ""
    """失败时标记为不支持的参数路径（最小粒度）"""

    stream: bool = False
    """是否是流式测试"""

    stream_validation: dict[str, Any] | None = None
    """流式测试的验证规则"""

    override_base: bool = False
    """是否完全覆盖 base_params"""

    no_wrapper: bool = False
    """是否跳过 param_wrapper"""

    endpoint_override: str | None = None
    """覆盖默认 endpoint"""

    files: dict[str, str] | None = None
    """文件上传配置 {"param_name": "file_path"}"""


@dataclass
class SpecTestSuite:
    """测试套件"""

    provider: str
    """厂商名称 (openai, gemini, anthropic, xai)"""

    endpoint: str
    """API 端点"""

    schemas: dict[str, str] = field(default_factory=dict)
    """Schema 引用映射，如 {"response": "openai.ChatCompletionResponse"}"""

    base_params: dict[str, Any] = field(default_factory=dict)
    """基线参数（必需参数）"""

    param_wrapper: str | None = None
    """参数包装器，如 Gemini 的 "generationConfig" """

    tests: list[SpecTestCase] = field(default_factory=list)
    """测试用例列表"""

    config_path: Path | None = None
    """配置文件路径"""


def _expand_parameterized_test(test_config: dict[str, Any]) -> Iterator[SpecTestCase]:
    """展开参数化测试

    配置示例:
        {
            "name": "test_stop_sequences",
            "parameterize": {
                "stop_value": [["END"], ["STOP", "DONE"], "###"]
            },
            "params": {"stop": "$stop_value"}
        }

    展开为:
        test_stop_sequences[END]
        test_stop_sequences[STOP,DONE]
        test_stop_sequences[###]
    """
    parameterize = test_config.get("parameterize", {})
    if not parameterize:
        return

    # 目前只支持单个参数化变量
    param_name, param_values = next(iter(parameterize.items()))

    for value in param_values:
        # 生成测试名称后缀
        if isinstance(value, list):
            suffix = ",".join(str(v) for v in value)
        else:
            suffix = str(value)

        # 替换 params 中的 $param_name 引用
        params = copy.deepcopy(test_config.get("params", {}))
        _replace_param_refs(params, param_name, value)

        # 构建测试变体名称
        variant_name = f"{test_config['name']}[{suffix}]"

        yield SpecTestCase(
            name=variant_name,
            description=test_config.get("description", ""),
            params=params,
            unsupported_param=test_config.get("unsupported_param", ""),
            stream=test_config.get("stream", False),
            stream_validation=test_config.get("stream_validation"),
            override_base=test_config.get("override_base", False),
            no_wrapper=test_config.get("no_wrapper", False),
            endpoint_override=test_config.get("endpoint_override"),
            files=test_config.get("files"),
        )


def _replace_param_refs(obj: Any, ref_name: str, ref_value: Any) -> None:
    """递归替换参数引用 $ref_name"""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            if isinstance(val, str) and val == f"${ref_name}":
                obj[key] = ref_value
            else:
                _replace_param_refs(val, ref_name, ref_value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and item == f"${ref_name}":
                obj[i] = ref_value
            else:
                _replace_param_refs(item, ref_name, ref_value)


def load_test_suite(config_path: Path) -> SpecTestSuite:
    """加载测试配置文件

    Args:
        config_path: JSON5 配置文件路径

    Returns:
        解析后的 TestSuite 对象
    """
    with open(config_path, "r", encoding="utf-8") as f:
        data = json5.load(f)

    tests: list[SpecTestCase] = []

    for t in data.get("tests", []):
        # 处理参数化测试
        if "parameterize" in t:
            tests.extend(_expand_parameterized_test(t))
        else:
            tests.append(
                SpecTestCase(
                    name=t["name"],
                    description=t.get("description", ""),
                    params=t.get("params", {}),
                    unsupported_param=t.get("unsupported_param", ""),
                    stream=t.get("stream", False),
                    stream_validation=t.get("stream_validation"),
                    override_base=t.get("override_base", False),
                    no_wrapper=t.get("no_wrapper", False),
                    endpoint_override=t.get("endpoint_override"),
                    files=t.get("files"),
                )
            )

    return SpecTestSuite(
        provider=data["provider"],
        endpoint=data["endpoint"],
        schemas=data.get("schemas", {}),
        base_params=data.get("base_params", {}),
        param_wrapper=data.get("param_wrapper"),
        tests=tests,
        config_path=config_path,
    )


def _get_nested(obj: dict[str, Any], path: str) -> Any:
    """获取嵌套路径的值

    Args:
        obj: 字典对象
        path: 点分隔路径，如 "response_format.type"

    Returns:
        路径对应的值，不存在则返回 None
    """
    parts = path.split(".")
    current = obj

    for part in parts:
        # 处理数组索引，如 "tools[0]"
        match = re.match(r"(\w+)\[(\d+)\]", part)
        if match:
            key, idx = match.groups()
            if isinstance(current, dict) and key in current:
                current = current[key]
                if isinstance(current, list) and int(idx) < len(current):
                    current = current[int(idx)]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


class ConfigDrivenTestRunner:
    """配置驱动的测试运行器

    负责：
    1. 构建请求参数（合并 base_params 和测试参数）
    2. 执行请求（普通或流式）
    3. 验证响应
    4. 记录测试结果到 ReportCollector
    """

    def __init__(
        self,
        suite: SpecTestSuite,
        client: Any,
        collector: ReportCollector,
    ):
        """初始化运行器

        Args:
            suite: 测试套件
            client: Provider 适配器（OpenAIAdapter, GeminiAdapter 等）
            collector: 报告收集器
        """
        self.suite = suite
        self.client = client
        self.collector = collector

        # 获取 schema 类
        self.response_schema: Type["BaseModel"] | None = get_schema(
            suite.schemas.get("response")
        )
        self.chunk_schema: Type["BaseModel"] | None = get_schema(
            suite.schemas.get("stream_chunk")
        )

    def build_params(self, test: SpecTestCase) -> dict[str, Any]:
        """构建完整请求参数

        Args:
            test: 测试用例

        Returns:
            合并后的请求参数
        """
        # 如果 override_base，不使用基线参数
        if test.override_base:
            base = {}
        else:
            base = copy.deepcopy(self.suite.base_params)

        test_params = copy.deepcopy(test.params)

        # 应用 param_wrapper（如 Gemini 的 generationConfig）
        if self.suite.param_wrapper and not test.no_wrapper and test_params:
            # 将测试参数包装到指定字段中
            wrapped = {self.suite.param_wrapper: test_params}
            base.update(wrapped)
        else:
            base.update(test_params)

        return base

    def run_test(self, test: SpecTestCase) -> bool:
        """运行单个测试

        Args:
            test: 测试用例

        Returns:
            测试是否通过
        """
        endpoint = test.endpoint_override or self.suite.endpoint
        params = self.build_params(test)

        if test.stream:
            return self._run_stream_test(test, endpoint, params)
        else:
            return self._run_normal_test(test, endpoint, params)

    def _run_normal_test(
        self, test: SpecTestCase, endpoint: str, params: dict[str, Any]
    ) -> bool:
        """运行普通（非流式）请求测试"""
        files = None
        opened_files = []

        try:
            # 准备文件上传
            if test.files:
                files = {}
                for param_name, file_path_str in test.files.items():
                    path = Path(file_path_str)
                    if not path.exists():
                        raise FileNotFoundError(f"Test file not found: {path}")
                    f = open(path, "rb")
                    opened_files.append(f)
                    # Use path.name as filename, but ensure MIME type if needed.
                    # Simple (filename, file) tuple for now.
                    files[param_name] = (path.name, f)

            response = self.client.request(endpoint=endpoint, params=params, files=files)
        finally:
            # 确保关闭文件
            for f in opened_files:
                f.close()

        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        # 验证响应结构
        if self.response_schema:
            result = ResponseValidator.validate_response(response, self.response_schema)
        else:
            # 没有 schema 时只检查 HTTP 状态
            result = type(
                "ValidationResult",
                (),
                {
                    "is_valid": 200 <= status_code < 300,
                    "error_message": None,
                    "missing_fields": [],
                    "expected_fields": [],
                },
            )()

        # 记录测试结果
        self.collector.record_test(
            test_name=test.name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        # 如果失败，记录不支持的参数（只记录最小粒度路径）
        if not (200 <= status_code < 300) and test.unsupported_param:
            self.collector.add_unsupported_param(
                param_name=test.unsupported_param,
                param_value=_get_nested(params, test.unsupported_param),
                test_name=test.name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        return 200 <= status_code < 300 and result.is_valid

    def _run_stream_test(
        self, test: TestCase, endpoint: str, params: dict[str, Any]
    ) -> bool:
        """运行流式请求测试"""
        parser = StreamParser(self.suite.provider, self.chunk_schema)

        try:
            for chunk_bytes in self.client.stream(endpoint=endpoint, params=params):
                parser.parse_chunk(chunk_bytes)

            # 验证流式规则
            if test.stream_validation:
                parser.validate_stream(test.stream_validation)

            # 获取完整内容
            content = parser.get_complete_content()

            # 记录成功
            self.collector.record_test(
                test_name=test.name,
                params=params,
                status_code=200,
                response_body={
                    "chunks_count": len(parser.all_chunks),
                    "content_length": len(content),
                },
                error=None,
            )

            # 基本验证：至少有一个 chunk 和一些内容
            if not parser.all_chunks:
                raise ValueError("No chunks received")

            return True

        except Exception as e:
            # 记录失败
            self.collector.record_test(
                test_name=test.name,
                params=params,
                status_code=500,
                response_body=None,
                error=str(e),
            )

            # 记录不支持的参数
            if test.unsupported_param:
                self.collector.add_unsupported_param(
                    param_name=test.unsupported_param,
                    param_value=_get_nested(params, test.unsupported_param),
                    test_name=test.name,
                    reason=f"Stream error: {e}",
                )

            return False

    def run_all(self) -> dict[str, bool]:
        """运行套件中的所有测试

        Returns:
            测试名称到结果的映射
        """
        results = {}

        for test in self.suite.tests:
            results[test.name] = self.run_test(test)

        return results
