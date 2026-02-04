"""OpenAI Chat Completions API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.chat import ChatCompletionResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.openai import OpenAIAdapter


class TestChatCompletions:
    """Chat Completions API 测试类"""
    client: OpenAIAdapter
    collector: ReportCollector

    ENDPOINT = "/v1/chat/completions"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say hello"}],
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

        # 设置为类属性，所有测试方法共享
        self.__class__.client = openai_client
        self.__class__.collector = collector

        yield

        # 类的所有测试完成后，生成一次报告
        output_dir = getattr(request.config, "run_reports_dir", "./reports")
        report_path = collector.finalize(output_dir)
        print(f"\n报告已生成: {report_path}")

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        # 发起请求
        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        # 验证响应
        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        # 记录测试结果（自动处理参数支持情况）
        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            is_baseline=True,  # 标记为 baseline 测试
        )

        # 断言：测试应该通过
        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_param_temperature"
        params = {**self.BASE_PARAMS, "temperature": 0.7}

        # 发起请求
        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        # 验证响应
        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        # 记录测试结果（自动处理参数支持情况）
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("temperature", 0.7),  # 指定测试的参数
        )

        # 断言
        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_max_tokens(self):
        """测试 max_tokens 参数"""
        test_name = "test_param_max_tokens"
        params = {**self.BASE_PARAMS, "max_tokens": 100}

        # 发起请求
        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        # 验证响应
        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        # 记录测试结果（自动处理参数支持情况）
        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("max_tokens", 100),
        )

        # 断言
        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # @pytest.mark.parametrize("model", ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"])
    # def test_model_variants(self, model):
    #     """测试不同的 model 变体"""
    #     test_name = f"test_model_variants[{model}]"
    #     params = {**self.BASE_PARAMS, "model": model}

    #     # 发起请求
    #     status_code, headers, response_body = self.client.request(
    #         endpoint=self.ENDPOINT,
    #         params=params,
    #     )

    #     # 验证响应
    #     is_valid, result.error_message, missing_fields, expected_fields = ResponseValidator.validate(
    #         response_body, ChatCompletionResponse
    #     )

    #     # 记录测试结果
    #     self.collector.record_test(
    #         test_name=test_name,
    #         params=params,
    #         status_code=status_code,
    #         response_body=response_body,
    #         error=result.error_message if not result.is_valid else None,
    #         missing_fields=result.missing_fields,
    #     )

    #     # 如果失败，记录不支持的参数
    #     if not (200 <= status_code < 300):
    #         self.collector.add_unsupported_param(
    #             param_name="model",
    #             param_value=model,
    #             test_name=test_name,
    #             reason=f"HTTP {status_code}: {response_body}",
    #         )

    #     # 断言
    #     assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
    #     assert result.is_valid, f"响应验证失败: {result.error_message}"
    # ========================================================================
    # 阶段 2: 基础参数测试 (控制变量法)
    # ========================================================================

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

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

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

    def test_param_n(self):
        """测试 n 参数（生成多个响应）"""
        test_name = "test_param_n"
        params = {**self.BASE_PARAMS, "n": 2}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("n", 2),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_stop_string(self):
        """测试 stop 参数（字符串形式）"""
        test_name = "test_param_stop_string"
        params = {**self.BASE_PARAMS, "stop": "\n"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("stop", "\n"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_stop_array(self):
        """测试 stop 参数（数组形式）"""
        test_name = "test_param_stop_array"
        params = {**self.BASE_PARAMS, "stop": ["\n", "END"]}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("stop", ["\n", "END"]),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_frequency_penalty(self):
        """测试 frequency_penalty 参数"""
        test_name = "test_param_frequency_penalty"
        params = {**self.BASE_PARAMS, "frequency_penalty": 0.5}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("frequency_penalty", 0.5),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_presence_penalty(self):
        """测试 presence_penalty 参数"""
        test_name = "test_param_presence_penalty"
        params = {**self.BASE_PARAMS, "presence_penalty": 0.5}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("presence_penalty", 0.5),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_seed(self):
        """测试 seed 参数（确定性输出）"""
        test_name = "test_param_seed"
        params = {**self.BASE_PARAMS, "seed": 12345}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("seed", 12345),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_max_completion_tokens(self):
        """测试 max_completion_tokens 参数（新参数）"""
        test_name = "test_param_max_completion_tokens"
        params = {**self.BASE_PARAMS, "max_completion_tokens": 100}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("max_completion_tokens", 100),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_user(self):
        """测试 user 参数（用户标识）"""
        test_name = "test_param_user"
        params = {**self.BASE_PARAMS, "user": "user-123"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("user", "user-123"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 3: 响应格式测试
    # ========================================================================

    def test_response_format_text(self):
        """测试 response_format 为 text（默认）"""
        test_name = "test_response_format_text"
        params = {**self.BASE_PARAMS, "response_format": {"type": "text"}}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("response_format", {"type": "text"}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_response_format_json_object(self):
        """测试 response_format 为 json_object"""
        test_name = "test_response_format_json_object"
        params = {
            **self.BASE_PARAMS,
            "messages": [{"role": "user", "content": "Return JSON: {\"status\": \"ok\"}"}],
            "response_format": {"type": "json_object"},
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("response_format", {"type": "json_object"}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_response_format_json_schema(self):
        """测试 response_format 为 json_schema"""
        test_name = "test_response_format_json_schema"
        params = {
            **self.BASE_PARAMS,
            "messages": [{"role": "user", "content": "Generate a person's info"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "person",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "number"},
                        },
                        "required": ["name", "age"],
                    },
                },
            },
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("response_format", {"type": "json_schema"}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 4: 工具调用测试
    # ========================================================================

    def test_param_tools(self):
        """测试 tools 参数（函数调用）"""
        test_name = "test_param_tools"
        params = {
            **self.BASE_PARAMS,
            "messages": [{"role": "user", "content": "What's the weather in Beijing?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string", "description": "City name"},
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

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("tools", "function_call"),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    @pytest.mark.parametrize("tool_choice", ["none", "auto", "required"])
    def test_tool_choice_variants(self, tool_choice):
        """测试不同的 tool_choice 值"""
        test_name = f"test_tool_choice_variants[{tool_choice}]"
        params = {
            **self.BASE_PARAMS,
            "messages": [{"role": "user", "content": "What's the weather?"}],
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

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

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
            "messages": [{"role": "user", "content": "Call functions"}],
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

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

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
    # 阶段 5: Logprobs 测试
    # ========================================================================

    def test_param_logprobs(self):
        """测试 logprobs 参数"""
        test_name = "test_param_logprobs"
        params = {**self.BASE_PARAMS, "logprobs": True}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("logprobs", True),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    @pytest.mark.parametrize("top_logprobs", [1, 5, 10])
    def test_param_top_logprobs(self, top_logprobs):
        """测试不同的 top_logprobs 值"""
        test_name = f"test_param_top_logprobs[{top_logprobs}]"
        params = {**self.BASE_PARAMS, "logprobs": True, "top_logprobs": top_logprobs}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("top_logprobs", top_logprobs),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 6: 流式响应测试
    # ========================================================================

    def test_streaming_basic(self):
        """测试基本流式响应"""
        import json

        from llm_spec.validation.schemas.openai.chat import (
            ChatCompletionChunkResponse,
        )

        test_name = "test_streaming_basic"
        params = {**self.BASE_PARAMS, "stream": True}

        chunks: list[dict] = []
        complete_content = ""
        raw_lines: list[str] = []  # 调试：收集所有原始行
        # SSE 解析缓冲，解决 JSON 被拆到多个网络 chunk 的情况
        buffer = ""

        try:
            for chunk_bytes in self.client.stream(
                endpoint=self.ENDPOINT,
                params=params,
            ):
                # 解析 SSE 格式
                chunk_str = chunk_bytes.decode("utf-8")
                raw_lines.append(repr(chunk_str))  # 调试：记录原始数据
                buffer += chunk_str

                # 按 SSE 事件边界（空行）拆分。保留最后一个可能不完整的事件在 buffer 中。
                events = buffer.split("\n\n")
                buffer = events.pop()  # last partial

                for event in events:
                    # 一个 event 可能包含多行，例如:
                    # data: {...}\n
                    # data: {...}\n
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
                        buffer = ""  # clean
                        break

                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError as je:
                        # 记录但不中断；不稳定网络下可能出现 malformed 或非 json 行
                        print(f"JSON解析失败: {data_str[:120]}, 错误: {je}")
                        continue

                    chunks.append(chunk_data)

                    # 验证每个 chunk（基于 dict 校验，而不是 httpx.Response）
                    result = ResponseValidator.validate_json(chunk_data, ChatCompletionChunkResponse)
                    if not result.is_valid:
                        raise AssertionError(f"流式 chunk 响应验证失败: {result.error_message}")

                    # 累积内容
                    if chunk_data.get("choices"):
                        delta_content = chunk_data["choices"][0].get("delta", {}).get("content")
                        if delta_content:
                            complete_content += delta_content

            # 调试输出
            print(f"\n收到 {len(raw_lines)} 个原始chunk")
            print(f"解析出 {len(chunks)} 个数据chunk")
            print(f"内容长度: {len(complete_content)}")
            if len(raw_lines) > 0:
                print(f"第一个chunk示例: {raw_lines[0][:200]}")

            # 记录测试结果
            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=200,  # 流式响应成功连接
                response_body={"chunks_count": len(chunks), "content": complete_content},
                error=None,
                missing_fields=[],
            )

            assert len(chunks) > 0, f"应该接收到至少一个chunk，实际收到 {len(raw_lines)} 个原始chunk"
            assert len(complete_content) > 0, "应该有生成的内容"

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

    def test_streaming_with_usage(self):
        """测试带 usage 的流式响应"""
        import json

        from llm_spec.validation.schemas.openai.chat import (
            ChatCompletionChunkResponse,
        )

        test_name = "test_streaming_with_usage"
        params = {
            **self.BASE_PARAMS,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        chunks: list[dict] = []
        has_usage = False
        buffer = ""

        try:
            for chunk_bytes in self.client.stream(
                endpoint=self.ENDPOINT,
                params=params,
            ):
                chunk_str = chunk_bytes.decode("utf-8")
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
                    except json.JSONDecodeError:
                        continue

                    chunks.append(chunk_data)

                    # 检查是否包含 usage
                    if chunk_data.get("usage"):
                        has_usage = True

                    # 验证每个 chunk（dict 校验）
                    result = ResponseValidator.validate_json(chunk_data, ChatCompletionChunkResponse)
                    if not result.is_valid:
                        raise AssertionError(f"流式 chunk 响应验证失败: {result.error_message}")

            # 记录测试结果
            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=200,
                response_body={"chunks_count": len(chunks), "has_usage": has_usage},
                error=None,
                missing_fields=[],
            )

            if not has_usage:
                self.collector.add_unsupported_param(
                    param_name="stream_options",
                    param_value={"include_usage": True},
                    test_name=test_name,
                    reason="流式响应中未包含 usage 信息",
                )
                # stream_options 依赖 stream 开关
                self.collector.add_unsupported_param(
                    param_name="stream",
                    param_value=True,
                    test_name=test_name,
                    reason="流式响应中未包含 usage 信息",
                )

            assert len(chunks) > 0, "应该接收到至少一个chunk"
            # 注意：has_usage 可能为 False，这是正常的，表示 API 不支持该功能

        except Exception as e:
            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=500,
                response_body=None,
                error=str(e),
            )
            self.collector.add_unsupported_param(
                param_name="stream_options",
                param_value={"include_usage": True},
                test_name=test_name,
                reason=f"带 usage 的流式请求失败: {str(e)}",
            )
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value=True,
                test_name=test_name,
                reason=f"带 usage 的流式请求失败: {str(e)}",
            )
            pytest.fail(f"流式测试失败: {str(e)}")

    # ========================================================================
    # 阶段 7: 高级参数测试
    # ========================================================================

    def test_param_logit_bias(self):
        """测试 logit_bias 参数"""
        test_name = "test_param_logit_bias"
        # Token ID for "hello" is usually 31373 in GPT tokenizer
        # 使用 -100 而非 100，因为极端正值可能导致 API 处理异常
        params = {**self.BASE_PARAMS, "logit_bias": {"31373": -100}}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("logit_bias", {"31373": -100}),
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

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

        result = ResponseValidator.validate_response(response, ChatCompletionResponse)

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
