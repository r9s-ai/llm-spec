"""Anthropic Messages API - 工具调用测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic import MessagesResponse
from llm_spec.validation.validator import ResponseValidator


class TestMessagesTools:
    """Messages API 工具调用测试类"""

    ENDPOINT = "/v1/messages"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello"}],
    }

    # 示例工具定义：获取天气
    WEATHER_TOOL = {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "The unit of temperature",
                },
            },
            "required": ["location"],
        },
    }

    # 示例工具定义：计算器
    CALCULATOR_TOOL = {
        "name": "calculator",
        "description": "Perform basic arithmetic operations",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The operation to perform",
                },
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["operation", "a", "b"],
        },
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, anthropic_client):
        """为整个测试类设置报告收集器"""
        collector = ReportCollector(
            provider="anthropic",
            endpoint=self.ENDPOINT,
            base_url=anthropic_client.get_base_url(),
        )

        self.__class__.client = anthropic_client
        self.__class__.collector = collector

        yield

        report_path = collector.finalize()
        print(f"\n报告已生成: {report_path}")

    # ==================== 阶段1: 基础工具调用 ====================

    def test_param_tools_basic(self):
        """测试基础工具定义"""
        test_name = "test_param_tools_basic"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [{"role": "user", "content": "What's the weather in San Francisco?"}],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="basic_tool",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_tool_use_response(self):
        """测试验证工具调用响应格式"""
        test_name = "test_tool_use_response"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [
                {"role": "user", "content": "What's the weather like in Tokyo in celsius?"}
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="tool_use_response",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

        # 验证响应包含 tool_use 类型的内容块
        if response_body and "content" in response_body:
            content_blocks = response_body["content"]
            has_tool_use = any(
                block.get("type") == "tool_use" for block in content_blocks if isinstance(block, dict)
            )
            # tool_use 可能出现也可能不出现，取决于模型决策

    def test_tool_result_submission(self):
        """测试提交工具结果"""
        test_name = "test_tool_result_submission"

        # 第一次请求：让模型调用工具
        params_initial = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [{"role": "user", "content": "What's the weather in Paris?"}],
        }

        status_code_1, _, response_body_1 = self.client.request(
            endpoint=self.ENDPOINT,
            params=params_initial,
        )

        # 如果第一次请求失败，直接记录并返回
        if not (200 <= status_code_1 < 300):
            self.collector.record_test(
                test_name=test_name,
                params=params_initial,
                status_code=status_code_1,
                response_body=response_body_1,
                error=f"Initial request failed: HTTP {status_code_1}",
            )
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="tool_result_submission",
                test_name=test_name,
                reason=f"HTTP {status_code_1}: {response_body_1}",
            )
            assert False, f"Initial tool call failed: {status_code_1}"

        # 第二次请求：提交模拟的工具结果
        params_with_result = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [
                {"role": "user", "content": "What's the weather in Paris?"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "get_weather",
                            "input": {"location": "Paris, France", "unit": "celsius"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool_123",
                            "content": "The weather in Paris is 18°C and partly cloudy.",
                        }
                    ],
                },
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params_with_result,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params_with_result,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_result",
                param_value="submission",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段2: 工具选择策略 ====================

    def test_tool_choice_auto(self):
        """测试自动选择工具 (tool_choice: auto)"""
        test_name = "test_tool_choice_auto"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "tool_choice": {"type": "auto"},
            "messages": [{"role": "user", "content": "What's the weather in London?"}],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_choice",
                param_value="auto",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_tool_choice_any(self):
        """测试强制使用任意工具 (tool_choice: any)"""
        test_name = "test_tool_choice_any"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL, self.CALCULATOR_TOOL],
            "tool_choice": {"type": "any"},
            "messages": [{"role": "user", "content": "Help me with something"}],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_choice",
                param_value="any",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_tool_choice_specific_tool(self):
        """测试指定特定工具 (tool_choice: tool)"""
        test_name = "test_tool_choice_specific_tool"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL, self.CALCULATOR_TOOL],
            "tool_choice": {"type": "tool", "name": "calculator"},
            "messages": [{"role": "user", "content": "What is 15 times 23?"}],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_choice",
                param_value="specific_tool",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段3: 复杂工具场景 ====================

    def test_multiple_tools(self):
        """测试多个工具定义"""
        test_name = "test_multiple_tools"

        # 第三个工具：查找餐厅
        restaurant_tool = {
            "name": "find_restaurant",
            "description": "Find restaurants in a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "cuisine": {"type": "string"},
                },
                "required": ["location"],
            },
        }

        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL, self.CALCULATOR_TOOL, restaurant_tool],
            "messages": [
                {"role": "user", "content": "Find me Italian restaurants in New York"}
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="multiple_tools",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_tool_with_complex_schema(self):
        """测试复杂输入 schema 的工具"""
        test_name = "test_tool_with_complex_schema"

        complex_tool = {
            "name": "book_flight",
            "description": "Book a flight with detailed preferences",
            "input_schema": {
                "type": "object",
                "properties": {
                    "departure": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                            "date": {"type": "string"},
                            "time": {"type": "string"},
                        },
                        "required": ["city", "date"],
                    },
                    "arrival": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                            "date": {"type": "string"},
                        },
                        "required": ["city"],
                    },
                    "passengers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "age": {"type": "number"},
                            },
                        },
                    },
                    "class": {
                        "type": "string",
                        "enum": ["economy", "business", "first"],
                    },
                },
                "required": ["departure", "arrival"],
            },
        }

        params = {
            **self.BASE_PARAMS,
            "tools": [complex_tool],
            "messages": [
                {
                    "role": "user",
                    "content": "Book me a flight from NYC to LA on June 15th, business class",
                }
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="complex_schema",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_parallel_tool_use(self):
        """测试并行工具调用"""
        test_name = "test_parallel_tool_use"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL, self.CALCULATOR_TOOL],
            "messages": [
                {
                    "role": "user",
                    "content": "What's the weather in Tokyo and also calculate 42 * 17?",
                }
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="parallel_use",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_multi_turn_tool_conversation(self):
        """测试多轮工具对话"""
        test_name = "test_multi_turn_tool_conversation"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.CALCULATOR_TOOL],
            "messages": [
                {"role": "user", "content": "Calculate 10 + 5"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "calc_1",
                            "name": "calculator",
                            "input": {"operation": "add", "a": 10, "b": 5},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "calc_1", "content": "15"}
                    ],
                },
                {"role": "user", "content": "Now multiply that result by 3"},
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="multi_turn",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段4: 工具错误处理 ====================

    def test_tool_result_with_error(self):
        """测试带错误标志的工具结果"""
        test_name = "test_tool_result_with_error"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "weather_1",
                            "name": "get_weather",
                            "input": {"location": "Unknown City"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "weather_1",
                            "content": "Error: Location not found",
                            "is_error": True,
                        }
                    ],
                },
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_result.is_error",
                param_value=True,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_tool_without_tool_choice(self):
        """测试只有 tools 没有 tool_choice 参数"""
        test_name = "test_tool_without_tool_choice"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [{"role": "user", "content": "Tell me about the weather"}],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="without_tool_choice",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
