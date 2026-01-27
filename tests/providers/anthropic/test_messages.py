"""Anthropic Messages API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic import MessagesResponse
from llm_spec.validation.validator import ResponseValidator


class TestMessages:
    """Messages API 测试类"""

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
        # 创建类级别的 collector
        collector = ReportCollector(
            provider="anthropic",
            endpoint=self.ENDPOINT,
            base_url=anthropic_client.get_base_url(),
        )

        # 设置为类属性，所有测试方法共享
        self.__class__.client = anthropic_client
        self.__class__.collector = collector

        yield

        # 类的所有测试完成后，生成一次报告
        report_path = collector.finalize()
        print(f"\n报告已生成: {report_path}")

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
