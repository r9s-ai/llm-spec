"""Google Gemini CountTokens API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.gemini import CountTokensResponse
from llm_spec.validation.validator import ResponseValidator


class TestCountTokens:
    """CountTokens API 测试类"""

    ENDPOINT = "/v1beta/models/gemini-2.5-flash:countTokens"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "contents": [{"parts": [{"text": "Hello, world!"}]}],
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, gemini_client):
        """为整个测试类设置报告收集器"""
        # 创建类级别的 collector
        collector = ReportCollector(
            provider="gemini",
            endpoint=self.ENDPOINT,
            base_url=gemini_client.get_base_url(),
        )

        # 设置为类属性，所有测试方法共享
        self.__class__.client = gemini_client
        self.__class__.collector = collector

        yield

        # 类的所有测试完成后，生成一次报告
        report_path = collector.finalize()
        print(f"\n报告已生成: {report_path}")

    # ========================================================================
    # 阶段 1: 基线测试
    # ========================================================================

    def test_baseline(self):
        """测试基线：仅文本内容"""
        test_name = "test_baseline"

        status_code, _headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, CountTokensResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

    # ========================================================================
    # 阶段 2: 多轮对话测试
    # ========================================================================

    def test_multi_turn_conversation(self):
        """测试多轮对话的 token 计数"""
        test_name = "test_multi_turn_conversation"
        params = {
            "contents": [
                {"role": "user", "parts": [{"text": "Hello"}]},
                {"role": "model", "parts": [{"text": "Hi there! How can I help you?"}]},
                {"role": "user", "parts": [{"text": "Tell me about Gemini API"}]},
            ],
        }

        status_code, _headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, CountTokensResponse
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

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 3: 系统指令测试
    # ========================================================================

    def test_with_system_instruction(self):
        """测试包含系统指令的 token 计数"""
        test_name = "test_with_system_instruction"
        params = {
            "contents": [{"parts": [{"text": "Hello"}]}],
            "systemInstruction": {
                "parts": [{"text": "You are a helpful assistant specializing in technical topics."}]
            },
        }

        status_code, _headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, CountTokensResponse
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
                param_name="systemInstruction",
                param_value="system_prompt",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 4: 工具定义测试
    # ========================================================================

    def test_with_tools(self):
        """测试包含工具定义的 token 计数"""
        test_name = "test_with_tools"
        params = {
            "contents": [{"parts": [{"text": "What's the weather?"}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "get_weather",
                            "description": "Get current weather for a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string", "description": "City name"}
                                },
                                "required": ["location"],
                            },
                        }
                    ]
                }
            ],
        }

        status_code, _headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, CountTokensResponse
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
                param_value="function_declarations",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
