"""OpenAI Responses API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.responses import (
    ResponseChunkObject,
    ResponseObject,
)
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.openai import OpenAIAdapter


class TestResponses:
    """Responses API 测试类"""
    client: OpenAIAdapter
    collector: ReportCollector

    ENDPOINT = "/v1/responses"

    # 基线参数:仅包含必需参数
    BASE_PARAMS = {
        "model": "gpt-4o-mini",
        "input": "Say hello",
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, request: pytest.FixtureRequest, openai_client: OpenAIAdapter):
        """为整个测试类设置报告收集器"""
        # 创建类级别的 collector
        collector = ReportCollector(
            provider="openai",
            endpoint=self.ENDPOINT,
            base_url=openai_client.get_base_url(),
        )

        # 设置为类属性,所有测试方法共享
        self.__class__.client = openai_client
        self.__class__.collector = collector

        yield

        # 类的所有测试完成后,生成一次报告
        output_dir = getattr(request.config, "run_reports_dir", "./reports")
        report_path = collector.finalize(output_dir)
        print(f"\n报告已生成: {report_path}")

    # ========================================================================
    # 阶段 1: 基线测试
    # ========================================================================

    def test_baseline(self):
        """测试基线:仅必需参数"""
        test_name = "test_baseline"

        # 发起请求
        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        # 验证响应
        result = ResponseValidator.validate_response(response, ResponseObject)

        # 记录测试结果（自动处理参数支持情况）
        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            is_baseline=True,
        )

        # 断言:测试应该通过
        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 2: 输入格式测试
    # ========================================================================

    def test_input_string(self):
        """测试 input 参数(字符串形式)"""
        test_name = "test_input_string"
        params = {**self.BASE_PARAMS, "input": "Hello, how are you?"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("input", "string"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_input_array_text(self):
        """测试 input 参数(数组形式,文本消息)"""
        test_name = "test_input_array_text"
        params = {
            **self.BASE_PARAMS,
            "input": [{"type": "message", "role": "user", "content": "Say hello"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("input", "array"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 3: 基础参数测试
    # ========================================================================

    def test_param_instructions(self):
        """测试 instructions 参数"""
        test_name = "test_param_instructions"
        params = {
            **self.BASE_PARAMS,
            "instructions": "You are a helpful assistant.",
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("instructions", "You are a helpful assistant."),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_param_temperature"
        params = {**self.BASE_PARAMS, "temperature": 0.7}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("temperature", 0.7),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_top_p(self):
        """测试 top_p 参数"""
        test_name = "test_param_top_p"
        params = {**self.BASE_PARAMS, "top_p": 0.9}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("top_p", 0.9),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_max_output_tokens(self):
        """测试 max_output_tokens 参数"""
        test_name = "test_param_max_output_tokens"
        params = {**self.BASE_PARAMS, "max_output_tokens": 100}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("max_output_tokens", 100),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_metadata(self):
        """测试 metadata 参数"""
        test_name = "test_param_metadata"
        params = {
            **self.BASE_PARAMS,
            "metadata": {"user_id": "123", "session": "abc"},
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("metadata", {"user_id": "123", "session": "abc"}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 4: 文本响应格式测试
    # ========================================================================

    def test_text_format_text(self):
        """测试 text 参数(格式: text)"""
        test_name = "test_text_format_text"
        params = {
            **self.BASE_PARAMS,
            "text": {"format": {"type": "text"}},
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("text", {"format": {"type": "text"}}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_text_format_json_object(self):
        """测试 text 参数(格式: json_object)"""
        test_name = "test_text_format_json_object"
        params = {
            **self.BASE_PARAMS,
            "input": "Return JSON: {\"status\": \"ok\"}",
            "text": {"format": {"type": "json_object"}},
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("text", {"format": {"type": "json_object"}}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_text_format_json_schema(self):
        """测试 text 参数(格式: json_schema)"""
        test_name = "test_text_format_json_schema"
        params = {
            **self.BASE_PARAMS,
            "input": "Generate a person's info",
            "text": {
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "number"},
                        },
                        "required": ["name", "age"],
                    },
                }
            },
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("text", {"format": {"type": "json_schema"}}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 5: 工具调用测试
    # ========================================================================

    def test_tools_function(self):
        """测试 tools 参数(自定义函数)"""
        test_name = "test_tools_function"
        params = {
            **self.BASE_PARAMS,
            "input": "What's the weather in Beijing?",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "City name",
                                },
                            },
                            "required": ["location"],
                        },
                    },
                }
            ],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("tools", "function"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_tools_file_search(self):
        """测试 tools 参数(内置文件搜索工具)"""
        test_name = "test_tools_file_search"
        params = {
            **self.BASE_PARAMS,
            "input": "Search for documentation",
            "tools": [{"type": "file_search"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("tools", "file_search"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_tools_web_search(self):
        """测试 tools 参数(内置网络搜索工具)"""
        test_name = "test_tools_web_search"
        params = {
            **self.BASE_PARAMS,
            "input": "Search the web for latest news",
            "tools": [{"type": "web_search"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("tools", "web_search"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_tools_code_interpreter(self):
        """测试 tools 参数(内置代码解释器工具)"""
        test_name = "test_tools_code_interpreter"
        params = {
            **self.BASE_PARAMS,
            "input": "Calculate 15 * 27",
            "tools": [{"type": "code_interpreter"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("tools", "code_interpreter"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    @pytest.mark.parametrize("tool_choice", ["none", "auto", "required"])
    def test_tool_choice_variants(self, tool_choice):
        """测试不同的 tool_choice 值"""
        test_name = f"test_tool_choice_variants[{tool_choice}]"
        params = {
            **self.BASE_PARAMS,
            "input": "What's the weather?",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                            "required": ["location"],
                        },
                    },
                }
            ],
            "tool_choice": tool_choice,
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("tool_choice", tool_choice),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_parallel_tool_calls(self):
        """测试 parallel_tool_calls 参数"""
        test_name = "test_parallel_tool_calls"
        params = {
            **self.BASE_PARAMS,
            "input": "Call functions",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "func1",
                        "description": "Function 1",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "parallel_tool_calls": True,
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("parallel_tool_calls", True),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 6: 对话/状态管理测试
    # ========================================================================

    def test_param_store(self):
        """测试 store 参数"""
        test_name = "test_param_store"
        params = {**self.BASE_PARAMS, "store": False}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("store", False),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 7: 高级参数测试
    # ========================================================================

    def test_param_service_tier(self):
        """测试 service_tier 参数"""
        test_name = "test_param_service_tier"
        params = {**self.BASE_PARAMS, "service_tier": "auto"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("service_tier", "auto"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_safety_identifier(self):
        """测试 safety_identifier 参数"""
        test_name = "test_param_safety_identifier"
        params = {**self.BASE_PARAMS, "safety_identifier": "user_hash_123"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("safety_identifier", "user_hash_123"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_max_tool_calls(self):
        """测试 max_tool_calls 参数"""
        test_name = "test_param_max_tool_calls"
        params = {
            **self.BASE_PARAMS,
            "input": "Search for information",
            "tools": [{"type": "web_search"}],
            "max_tool_calls": 5,
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("max_tool_calls", 5),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_truncation(self):
        """测试 truncation 参数"""
        test_name = "test_param_truncation"
        params = {**self.BASE_PARAMS, "truncation": "auto"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ResponseObject)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("truncation", "auto"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 8: 流式响应测试
    # ========================================================================

    def test_streaming_basic(self):
        """测试基本流式响应"""
        import json

        test_name = "test_streaming_basic"
        params = {**self.BASE_PARAMS, "stream": True}

        chunks: list[dict] = []
        complete_content = ""
        has_usage = False
        usage_data = None
        raw_lines = []  # 调试:收集所有原始行
        buffer = ""

        try:
            for chunk_bytes in self.client.stream(
                endpoint=self.ENDPOINT,
                params=params,
            ):
                # 解析 SSE 格式
                chunk_str = chunk_bytes.decode("utf-8")
                raw_lines.append(repr(chunk_str))  # 调试:记录原始数据
                buffer += chunk_str

                events = buffer.split("\n\n")
                buffer = events.pop()

                for event in events:
                    data_lines = []
                    for line in event.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())

                    if not data_lines:
                        continue

                    data_str = "\n".join(data_lines)
                    if data_str == "[DONE]":
                        buffer = ""
                        break

                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError as je:
                        print(f"JSON解析失败: {data_str[:120]}, 错误: {je}")
                        continue

                    chunks.append(chunk_data)

                    # 验证每个 chunk
                    result = ResponseValidator.validate_json(chunk_data, ResponseChunkObject)
                    if not result.is_valid:
                        raise AssertionError(f"流式 chunk 响应验证失败: {result.error_message}")

                    # 累积内容 (如果有delta)
                    if chunk_data.get("delta"):
                        delta = chunk_data["delta"]
                        if isinstance(delta, dict):
                            content = delta.get("content") or delta.get("text", "")
                            if content:
                                complete_content += content

                    # 检查嵌套的usage (在response.completed chunk中)
                    response_obj = chunk_data.get("response", {})
                    if response_obj.get("usage") is not None:
                        has_usage = True
                        usage_data = response_obj["usage"]

            # 调试输出
            print(f"\n收到 {len(raw_lines)} 个原始chunk")
            print(f"解析出 {len(chunks)} 个数据chunk")
            print(f"内容长度: {len(complete_content)}")
            print(f"包含usage: {has_usage}")
            if has_usage:
                print(f"Usage数据: {usage_data}")
            if len(raw_lines) > 0:
                print(f"第一个chunk示例: {raw_lines[0][:200]}")

            # 记录测试结果
            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=200,  # 流式响应成功连接
                response_body={
                    "chunks_count": len(chunks),
                    "content": complete_content,
                    "has_usage": has_usage,
                    "usage": usage_data,
                },
                error=None,
                missing_fields=[],
            )

            assert (
                len(chunks) > 0
            ), f"应该接收到至少一个chunk,实际收到 {len(raw_lines)} 个原始chunk"
            # 注意：有些实现/网关在未开启 stream_options 时不会返回 usage。
            # 这里不强制要求 has_usage=True；若需要强制，请在 params 中显式开启相应选项并断言。

        except Exception as e:
            print(f"\n异常信息: {type(e).__name__}: {str(e)}")
            print(f"收到的原始chunks数量: {len(raw_lines)}")
            if raw_lines:
                print(f"前3个chunks: {raw_lines[:3]}")

            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=500,
                response_body=None,
                error=str(e),
            )
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value=True,
                test_name=test_name,
                reason=f"流式请求失败: {str(e)}",
            )
            pytest.fail(f"流式测试失败: {str(e)}")
