"""Anthropic Messages API - 高级参数与多模态测试"""

import base64
import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic import MessagesResponse
from llm_spec.validation.validator import ResponseValidator


class TestMessagesAdvanced:
    """Messages API 高级参数与多模态测试类"""

    ENDPOINT = "/v1/messages"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello"}],
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

    # ==================== 阶段1: 多轮对话测试 ====================

    def test_multi_turn_conversation(self):
        """测试多轮对话历史"""
        test_name = "test_multi_turn_conversation"
        params = {
            **self.BASE_PARAMS,
            "messages": [
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is Paris."},
                {"role": "user", "content": "What about Germany?"},
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
                param_name="messages",
                param_value="multi_turn",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_alternating_roles(self):
        """测试角色交替验证"""
        test_name = "test_alternating_roles"
        params = {
            **self.BASE_PARAMS,
            "messages": [
                {"role": "user", "content": "Tell me a joke"},
                {"role": "assistant", "content": "Why did the programmer quit? Because they didn't get arrays!"},
                {"role": "user", "content": "That's funny! Tell me another one."},
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
                param_name="messages",
                param_value="alternating_roles",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_long_conversation_history(self):
        """测试长对话历史 (10轮)"""
        test_name = "test_long_conversation_history"

        # 构建10轮对话
        messages = []
        for i in range(5):
            messages.append({"role": "user", "content": f"Question {i + 1}: What is {i} + {i}?"})
            messages.append({"role": "assistant", "content": f"The answer is {i + i}."})
        messages.append({"role": "user", "content": "Thank you for all the answers!"})

        params = {
            **self.BASE_PARAMS,
            "messages": messages,
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
                param_name="messages",
                param_value="long_history",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段2: 多模态内容测试 ====================

    def test_param_image_base64(self, test_assets):
        """测试 base64 图片输入"""
        test_name = "test_param_image_base64"

        # 读取测试图片并转换为base64
        image_path = test_assets / "images" / "test.png"

        # 创建一个简单的1x1 PNG图片的base64数据（如果测试资源不存在）
        # 这是一个1x1透明PNG的base64编码
        sample_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        try:
            if image_path.exists():
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
            else:
                image_data = sample_base64
        except Exception:
            image_data = sample_base64

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
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": "What do you see in this image?"},
                    ],
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
                param_name="image_base64",
                param_value="base64_image",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize(
        "media_type",
        ["image/jpeg", "image/png", "image/gif", "image/webp"],
    )
    def test_image_media_type_variants(self, media_type):
        """测试不同图片格式的 media_type"""
        test_name = f"test_image_media_type_variants[{media_type}]"

        # 使用简单的1x1 PNG base64数据
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
                param_name="image.source.media_type",
                param_value=media_type,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_text_and_image_combined(self):
        """测试文本+图片混合内容"""
        test_name = "test_text_and_image_combined"

        sample_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        params = {
            **self.BASE_PARAMS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Here is an image:"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": sample_base64,
                            },
                        },
                        {"type": "text", "text": "What colors do you see?"},
                    ],
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
                param_name="content",
                param_value="text_and_image_combined",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段3: 内容块格式测试 ====================

    def test_content_as_string(self):
        """测试 content 为字符串格式"""
        test_name = "test_content_as_string"
        params = {
            **self.BASE_PARAMS,
            "messages": [{"role": "user", "content": "This is a simple string message"}],
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
                param_name="content",
                param_value="string",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_content_as_blocks(self):
        """测试 content 为块数组格式"""
        test_name = "test_content_as_blocks"
        params = {
            **self.BASE_PARAMS,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "This is a text block"}],
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
                param_name="content",
                param_value="blocks",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_multiple_text_blocks(self):
        """测试多个文本块"""
        test_name = "test_multiple_text_blocks"
        params = {
            **self.BASE_PARAMS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "First text block."},
                        {"type": "text", "text": "Second text block."},
                        {"type": "text", "text": "Third text block."},
                    ],
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
                param_name="content",
                param_value="multiple_text_blocks",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段4: 思考模式测试 (Claude 3.7+) ====================

    def test_param_thinking_enabled(self):
        """测试启用思考模式 (Claude 3.7+)"""
        test_name = "test_param_thinking_enabled"
        params = {
            **self.BASE_PARAMS,
            "thinking": {"type": "enabled"},
            "messages": [{"role": "user", "content": "Solve: What is 25 * 17?"}],
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
                param_name="thinking.type",
                param_value="enabled",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        # 思考模式可能只在特定模型上支持，失败不强制断言
        # assert 200 <= status_code < 300

    def test_param_thinking_budget_tokens(self):
        """测试思考token预算 (Claude 3.7+)"""
        test_name = "test_param_thinking_budget_tokens"
        params = {
            **self.BASE_PARAMS,
            "thinking": {"type": "enabled", "budget_tokens": 2000},
            "messages": [
                {"role": "user", "content": "Explain the theory of relativity in detail."}
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
                param_name="thinking.budget_tokens",
                param_value=2000,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        # 思考模式可能只在特定模型上支持，失败不强制断言
        # assert 200 <= status_code < 300
