"""Anthropic Messages API - 基础参数测试"""

import base64
import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic import MessagesResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.anthropic import AnthropicAdapter

class TestMessagesBasic:
    """Messages API 基础参数测试类"""

    client: AnthropicAdapter

    collector: ReportCollector

    ENDPOINT = "/v1/messages"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "claude-haiku-4.5",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "Hello"}],
    }

    # 工具定义：用于工具调用测试
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

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, request: pytest.FixtureRequest, anthropic_client: AnthropicAdapter):
        """为整个测试类设置报告收集器"""
        collector = ReportCollector(
            provider="anthropic",
            endpoint=self.ENDPOINT,
            base_url=anthropic_client.get_base_url(),
        )

        self.__class__.client = anthropic_client
        self.__class__.collector = collector

        yield

        output_dir = getattr(request.config, "run_reports_dir", "./reports")
        report_path = collector.finalize(output_dir)
        print(f"\n报告已生成: {report_path}")

    # ==================== 阶段1: 基线与模型测试 ====================

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"


    # ==================== 阶段2: 采样参数测试 ====================

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

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="temperature",
                param_value=0.7,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

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

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="top_p",
                param_value=0.9,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_param_top_k(self):
        """测试 top_k 参数"""
        test_name = "test_param_top_k"
        params = {**self.BASE_PARAMS, "top_k": 40}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="top_k",
                param_value=40,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ==================== 阶段3: 停止控制测试 ====================

    def test_param_stop_sequences(self):
        """测试 stop_sequences 参数"""
        test_name = "test_param_stop_sequences"
        # API requires stop sequences to contain non-whitespace characters
        params = {
            **self.BASE_PARAMS,
            "stop_sequences": ["StopHere", "EndProcess"],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="stop_sequences",
                param_value=["StopHere", "EndProcess"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ==================== 阶段4: 系统提示测试 ====================

    def test_param_system(self):
        """测试 system 参数"""
        test_name = "test_param_system"
        params = {
            **self.BASE_PARAMS,
            "system": "You are a helpful assistant.",
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="system",
                param_value="You are a helpful assistant.",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ==================== 阶段5: 元数据与追踪 ====================

    def test_param_metadata(self):
        """测试 metadata 参数"""
        test_name = "test_param_metadata"
        params = {
            **self.BASE_PARAMS,
            "metadata": {"user_id": "test-user-123"},
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="metadata",
                param_value={"user_id": "test-user-123"},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ==================== 阶段6: 流式响应测试 ====================

    @pytest.mark.asyncio
    async def test_param_stream(self):
        """测试 stream 参数"""
        test_name = "test_param_stream"
        params = {**self.BASE_PARAMS, "stream": True}

        chunks = []
        error_occurred = False
        error_message: str | None = None

        try:
            async for chunk in self.client.stream_async(self.ENDPOINT, params):
                chunks.append(chunk)
                if len(chunks) >= 3:  # 收到几个 chunk 即可验证参数支持
                    break
        except Exception as e:
            error_occurred = True
            error_message = str(e)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=200 if not error_occurred else 500,
            response_body={"chunks_received": len(chunks)} if chunks else None,
            error=error_message if error_occurred else None,
        )

        if error_occurred:
            self.collector.add_unsupported_param(
                param_name="stream",
                param_value=True,
                test_name=test_name,
                reason=f"Streaming error: {error_message}",
            )

        assert not error_occurred, f"Streaming failed: {error_message}"
        assert len(chunks) > 0, "No chunks received"

    # ==================== 阶段7: 多模态测试 ====================

    def test_param_image_base64(self):
        """测试 base64 图片输入"""
        test_name = "test_param_image_base64"

        # 使用简单的1x1 PNG图片的base64数据
        sample_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        params = {
            **self.BASE_PARAMS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": sample_base64,
                            },
                        },
                        {"type": "text", "text": "What do you see in this image?"},
                    ],
                }
            ],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="image_base64",
                param_value="base64_image",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    @pytest.mark.parametrize(
        "media_type",
        ["image/jpeg", "image/png", "image/gif", "image/webp"],
    )
    def test_image_media_type_variants(self, media_type):
        """测试不同图片格式的 media_type"""
        test_name = f"test_image_media_type_variants[{media_type}]"

        sample_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        params = {
            **self.BASE_PARAMS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": sample_base64,
                            },
                        },
                        {"type": "text", "text": "Describe this image."},
                    ],
                }
            ],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="image.source.media_type",
                param_value=media_type,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ==================== 阶段8: 工具调用测试 ====================

    def test_param_tools(self):
        """测试 tools 参数"""
        test_name = "test_param_tools"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "messages": [{"role": "user", "content": "What's the weather in San Francisco?"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="basic_tool",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_param_tool_choice_auto(self):
        """测试 tool_choice 参数 (auto)"""
        test_name = "test_param_tool_choice_auto"
        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "tool_choice": {"type": "auto"},
            "messages": [{"role": "user", "content": "What's the weather in London?"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_choice.type",
                param_value="auto",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="function",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    @pytest.mark.parametrize("choice_type", ["any", "tool"])
    def test_tool_choice_variants(self, choice_type):
        """测试 tool_choice 参数变体"""
        test_name = f"test_tool_choice_variants[{choice_type}]"

        if choice_type == "any":
            tool_choice = {"type": "any"}
        else:  # choice_type == "tool"
            tool_choice = {"type": "tool", "name": "get_weather"}

        params = {
            **self.BASE_PARAMS,
            "tools": [self.WEATHER_TOOL],
            "tool_choice": tool_choice,
            "messages": [{"role": "user", "content": "What's the weather?"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="tool_choice.type",
                param_value=choice_type,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )
            self.collector.add_unsupported_param(
                param_name="tools",
                param_value="function",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ==================== 阶段9: 思考模式测试 ====================

    def test_param_thinking(self):
        """测试 thinking 参数"""
        test_name = "test_param_thinking"
        # thinking.enabled requires budget_tokens to be set
        params = {
            **self.BASE_PARAMS,
            "max_tokens": 512+2048,
            "thinking": {
                "type": "enabled",
                "budget_tokens": 2048
            },
            "messages": [{"role": "user", "content": "Solve: What is 25 * 17?"}],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, MessagesResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="thinking.type",
                param_value="enabled",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        # 思考模式可能只在特定模型上支持，不强制断言
        assert 200 <= status_code < 300
