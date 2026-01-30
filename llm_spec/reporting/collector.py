"""报告收集器，用于累积测试结果"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_spec.reporting.types import ReportData, UnsupportedParameter
from llm_spec.types import JSONValue


class ReportCollector:
    """测试报告收集器"""

    def __init__(self, provider: str, endpoint: str, base_url: str):
        """初始化报告收集器

        Args:
            provider: Provider 名称
            endpoint: API 端点
            base_url: 基础 URL
        """
        self.provider = provider
        self.endpoint = endpoint
        self.base_url = base_url
        self.test_time = datetime.now().isoformat()

        # 测试统计
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

        # 参数跟踪
        self.tested_params: set[str] = set()
        self.unsupported_params: list[UnsupportedParameter] = []

        # 响应字段跟踪
        self.expected_fields: set[str] = set()
        self.unsupported_fields: list[dict[str, Any]] = []  # TODO: add typed schema later

        # 错误跟踪
        self.errors: list[dict[str, Any]] = []  # TODO: add typed schema later

    @staticmethod
    def _extract_param_paths(
        params: dict[str, Any], prefix: str = "", max_depth: int = 10
    ) -> set[str]:
        """递归提取参数路径（支持嵌套结构）

        Args:
            params: 参数字典
            prefix: 路径前缀
            max_depth: 最大递归深度（防止无限递归）

        Returns:
            参数路径集合

        Examples:
            >>> ReportCollector._extract_param_paths({"temperature": 0.7})
            {'temperature'}

            >>> ReportCollector._extract_param_paths({
            ...     "generationConfig": {"temperature": 0.7, "topP": 0.9}
            ... })
            {'generationConfig', 'generationConfig.temperature', 'generationConfig.topP'}

            >>> ReportCollector._extract_param_paths({
            ...     "messages": [{"role": "user", "content": "Hello"}]
            ... })
            {'messages', 'messages[0].role', 'messages[0].content'}
        """
        if max_depth <= 0:
            return set()

        paths = set()

        for key, value in params.items():
            # 构建当前路径
            current_path = f"{prefix}.{key}" if prefix else key
            paths.add(current_path)

            # 如果值是字典，递归提取
            if isinstance(value, dict) and value:  # 跳过空字典
                nested_paths = ReportCollector._extract_param_paths(
                    value, current_path, max_depth - 1
                )
                paths.update(nested_paths)

            # 如果值是列表，检查列表中的字典
            elif isinstance(value, list) and value:  # 跳过空列表
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        nested_paths = ReportCollector._extract_param_paths(
                            item, f"{current_path}[{i}]", max_depth - 1
                        )
                        paths.update(nested_paths)

        return paths

    def record_test(
        self,
        test_name: str,
        params: dict[str, Any],
        status_code: int,
        response_body: JSONValue | str | None,
        error: str | None = None,
        missing_fields: list[str] | None = None,
        expected_fields: list[str] | None = None,
    ) -> None:
        """记录单个测试结果

        Args:
            test_name: 测试名称
            params: 请求参数
            status_code: HTTP 状态码
            response_body: 响应体
            error: 错误消息（如果有）
            missing_fields: 缺失的响应字段
            expected_fields: 期望的响应字段（从 schema 提取）
        """
        self.total_tests += 1

        # 记录测试的参数（支持嵌套结构）
        param_paths = self._extract_param_paths(params)
        self.tested_params.update(param_paths)

        # 记录期望字段
        if expected_fields:
            for field in expected_fields:
                self.expected_fields.add(field)

        # 判断测试是否通过
        is_success = (200 <= status_code < 300) and error is None

        if is_success:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

            # 记录错误
            if error:
                if 400 <= status_code < 500:
                    error_type = "http_error"
                elif 500 <= status_code < 600:
                    error_type = "server_error"
                else:
                    error_type = "validation_error"

                self.errors.append(
                    {
                        "test_name": test_name,
                        "type": error_type,
                        "message": f"HTTP {status_code}: {error}",
                    }
                )

        # 记录缺失的响应字段
        if missing_fields:
            for field in missing_fields:
                self.unsupported_fields.append(
                    {
                        "field": field,
                        "test_name": test_name,
                        "reason": "Field missing in response",
                    }
                )

    @staticmethod
    def response_body_from_httpx(response: "object") -> JSONValue | str:
        """Best-effort extract response body for reporting.

        Preference order:
        1) JSON (dict/list/primitive) if response.json() succeeds
        2) text fallback
        """
        # Keep this method dependency-light (no hard dependency on httpx at runtime).
        try:
            json_method = getattr(response, "json", None)
            if callable(json_method):
                value: object = json_method()
                # Only accept JSON-shaped values
                if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
                    return value
        except Exception:
            pass

        # Binary-ish responses (e.g. audio) - store a lightweight summary instead of junk text.
        try:
            headers_obj = getattr(response, "headers", None)
            content_type: str | None = None
            if headers_obj is not None:
                # headers could be Mapping or httpx.Headers
                content_type_val = headers_obj.get("content-type")
                if isinstance(content_type_val, str):
                    content_type = content_type_val

            if content_type is not None and (
                content_type.startswith("audio/")
                or content_type.startswith("image/")
                or content_type.startswith("application/octet-stream")
            ):
                content = getattr(response, "content", b"")
                size = len(content) if isinstance(content, (bytes, bytearray)) else None
                return {
                    "binary": True,
                    "content_type": content_type,
                    "size_bytes": size,
                }
        except Exception:
            pass

        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        return str(response)

    def add_unsupported_param(
        self, param_name: str, param_value: Any, test_name: str, reason: str
    ) -> None:
        """添加不支持的参数

        Args:
            param_name: 参数名
            param_value: 参数值
            test_name: 测试名称
            reason: 不支持的原因
        """
        self.unsupported_params.append(
            UnsupportedParameter(
                parameter=param_name,
                value=param_value,
                test_name=test_name,
                reason=reason,
            )
        )

    def finalize(self, output_dir: str = "./reports") -> str:
        """生成最终报告

        Args:
            output_dir: 输出目录

        Returns:
            报告文件路径
        """
        # 生成子目录名
        endpoint_name = self.endpoint.replace("/", "_").strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir_name = f"{self.provider}_{endpoint_name}_{timestamp}"

        # 创建报告目录
        report_dir = Path(output_dir) / report_dir_name
        report_dir.mkdir(parents=True, exist_ok=True)

        # 构建报告
        report: ReportData = {
            "test_time": self.test_time,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "base_url": self.base_url,
            "test_summary": {
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
            },
            "parameters": {
                "tested": sorted(list(self.tested_params)),
                "untested": [],  # TODO: 需要从spec定义中计算
                "unsupported": self.unsupported_params,
            },
            "response_fields": {
                "expected": sorted(list(self.expected_fields)),
                "unsupported": self.unsupported_fields,
            },
            "errors": self.errors,
        }

        # 写入 JSON 文件
        json_path = report_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 生成参数表格
        self._generate_parameter_tables_if_available(str(report_dir), report)

        return str(json_path)

    def _generate_parameter_tables_if_available(
        self, output_dir: str, report_data: ReportData
    ) -> None:
        """动态生成参数支持表格

        Args:
            output_dir: 输出目录
            report_data: 报告数据
        """
        try:
            from llm_spec.reporting.formatter import ParameterTableFormatter

            # 创建格式化器（只需要报告数据）
            formatter = ParameterTableFormatter(report_data)

            # 生成 Markdown 表格
            markdown_path = formatter.save_markdown(output_dir)
            print(f"参数表格 (Markdown): {markdown_path}")

            # 生成 HTML 报告
            html_path = formatter.save_html(output_dir)
            print(f"参数表格 (HTML): {html_path}")

        except (ImportError, AttributeError, ModuleNotFoundError):
            # 如果导入失败，静默处理（不影响主流程）
            pass
