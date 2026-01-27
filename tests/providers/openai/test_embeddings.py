"""OpenAI Embeddings API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.embeddings import EmbeddingResponse
from llm_spec.validation.validator import ResponseValidator


class TestEmbeddings:
    """Embeddings API 测试类"""

    ENDPOINT = "/v1/embeddings"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "text-embedding-ada-002",
        "input": "Hello, world!",
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, openai_client):
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
            response_body, EmbeddingResponse
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

    def test_param_input_array(self):
        """测试 input 参数（数组形式）"""
        test_name = "test_param_input_array"
        params = {
            **self.BASE_PARAMS,
            "input": ["Hello", "World"],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, EmbeddingResponse
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
                param_name="input",
                param_value="array",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize(
        "model",
        [
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large",
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
            response_body, EmbeddingResponse
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

    def test_param_encoding_format(self):
        """测试 encoding_format 参数"""
        test_name = "test_param_encoding_format"
        params = {**self.BASE_PARAMS, "encoding_format": "float"}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, EmbeddingResponse
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
                param_name="encoding_format",
                param_value="float",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_dimensions(self):
        """测试 dimensions 参数（仅 v3 模型支持）"""
        test_name = "test_param_dimensions"
        params = {
            "model": "text-embedding-3-small",
            "input": "Test",
            "dimensions": 512,
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, EmbeddingResponse
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
                param_name="dimensions",
                param_value=512,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
