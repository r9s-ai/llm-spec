"""Anthropic Messages API - 基础参数测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic import MessagesResponse
from llm_spec.validation.validator import ResponseValidator


class TestMessagesBasic:
    """Messages API 基础参数测试类"""

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

    # ==================== 阶段1: 基线与模型测试 ====================

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, MessagesResponse
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

    @pytest.mark.parametrize(
        "model",
        [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-haiku-20241022",
            "claude-sonnet-4-5-20250110",
        ],
    )
    def test_model_variants(self, model):
        """测试不同的 model 变体"""
        test_name = f"test_model_variants[{model}]"
        params = {**self.BASE_PARAMS, "model": model}

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
                param_name="model",
                param_value=model,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段2: 采样参数测试 ====================

    def test_param_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_param_temperature"
        params = {**self.BASE_PARAMS, "temperature": 0.7}

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
                param_name="temperature",
                param_value=0.7,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_top_p(self):
        """测试 top_p 参数"""
        test_name = "test_param_top_p"
        params = {**self.BASE_PARAMS, "top_p": 0.9}

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
                param_name="top_p",
                param_value=0.9,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_top_k(self):
        """测试 top_k 参数"""
        test_name = "test_param_top_k"
        params = {**self.BASE_PARAMS, "top_k": 40}

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
                param_name="top_k",
                param_value=40,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_combined_sampling(self):
        """测试组合采样参数: temperature + top_p + top_k"""
        test_name = "test_param_combined_sampling"
        params = {
            **self.BASE_PARAMS,
            "temperature": 0.8,
            "top_p": 0.95,
            "top_k": 50,
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
                param_name="combined_sampling",
                param_value={"temperature": 0.8, "top_p": 0.95, "top_k": 50},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段3: 停止控制测试 ====================

    def test_param_stop_sequences(self):
        """测试 stop_sequences 参数"""
        test_name = "test_param_stop_sequences"
        params = {
            **self.BASE_PARAMS,
            "stop_sequences": ["\n\n", "END"],
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
                param_name="stop_sequences",
                param_value=["\n\n", "END"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_max_tokens_minimum(self):
        """测试 max_tokens 最小值"""
        test_name = "test_param_max_tokens_minimum"
        params = {**self.BASE_PARAMS, "max_tokens": 1}

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
                param_name="max_tokens",
                param_value=1,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_max_tokens_maximum(self):
        """测试 max_tokens 最大值 (8192)"""
        test_name = "test_param_max_tokens_maximum"
        params = {**self.BASE_PARAMS, "max_tokens": 8192}

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
                param_name="max_tokens",
                param_value=8192,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段4: 系统提示测试 ====================

    def test_param_system(self):
        """测试 system 参数"""
        test_name = "test_param_system"
        params = {
            **self.BASE_PARAMS,
            "system": "You are a helpful assistant.",
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
                param_name="system",
                param_value="You are a helpful assistant.",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_system_with_multiline(self):
        """测试多行系统提示"""
        test_name = "test_system_with_multiline"
        system_prompt = """You are a professional assistant.
Your role is to:
1. Answer questions accurately
2. Be concise and clear
3. Show empathy"""

        params = {
            **self.BASE_PARAMS,
            "system": system_prompt,
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
                param_name="system",
                param_value="multiline_prompt",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_system_with_complex_instructions(self):
        """测试复杂系统指令"""
        test_name = "test_system_with_complex_instructions"
        system_prompt = (
            "You are an expert programmer. "
            "When answering questions, follow these rules: "
            "1) Always provide code examples; "
            "2) Explain your reasoning; "
            "3) Consider edge cases; "
            "4) Use best practices."
        )

        params = {
            **self.BASE_PARAMS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": "How do I reverse a string in Python?"}],
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
                param_name="system",
                param_value="complex_instructions",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ==================== 阶段5: 元数据与追踪 ====================

    def test_param_metadata(self):
        """测试 metadata 参数"""
        test_name = "test_param_metadata"
        params = {
            **self.BASE_PARAMS,
            "metadata": {"user_id": "test-user-123"},
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
                param_name="metadata",
                param_value={"user_id": "test-user-123"},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
