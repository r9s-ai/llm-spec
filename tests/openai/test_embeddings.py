"""OpenAI Embeddings API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.embeddings import EmbeddingResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.openai import OpenAIAdapter


class TestEmbeddings:
    """Embeddings API 测试类"""
    client: OpenAIAdapter
    collector: ReportCollector

    ENDPOINT = "/v1/embeddings"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "text-embedding-3-small",
        "input": "Hello, world!",
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

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, EmbeddingResponse)

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        # baseline 失败也需要记录：把必需参数标为不支持（无对照基线可用）
        if not (200 <= status_code < 300):
            for k in ("model", "input"):
                self.collector.add_unsupported_param(
                    param_name=k,
                    param_value=self.BASE_PARAMS.get(k),
                    test_name=test_name,
                    reason=f"HTTP {status_code}: {response_body}",
                )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    def test_param_input_array(self):
        """测试 input 参数（字符串数组）"""
        test_name = "test_param_input_array"
        params = {
            **self.BASE_PARAMS,
            "input": ["Hello", "World"],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, EmbeddingResponse)

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

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_param_input_tokens(self):
        """测试 input 参数（token 数组）"""
        test_name = "test_param_input_tokens"
        params = {
            **self.BASE_PARAMS,
            "input": [[11, 12, 13, 14]],
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, EmbeddingResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("input", "token_array"),
        )

        assert 200 <= status_code < 300
        assert result.is_valid

    # @pytest.mark.parametrize(
    #     "model",
    #     [
    #         "text-embedding-3-small",
    #         "text-embedding-3-large",
    #     ],
    # )
    # def test_model_variants(self, model):
    #     """测试不同的 model 变体"""
    #     test_name = f"test_model_variants[{model}]"
    #     params = {**self.BASE_PARAMS, "model": model}

    #     status_code, headers, response_body = self.client.request(
    #         endpoint=self.ENDPOINT,
    #         params=params,
    #     )

    #     is_valid, result.error_message, missing_fields, expected_fields = ResponseValidator.validate(
    #         response_body, EmbeddingResponse
    #     )

    #     self.collector.record_test(
    #         test_name=test_name,
    #         params=params,
    #         status_code=status_code,
    #         response_body=response_body,
    #         error=result.error_message if not result.is_valid else None,
    #         missing_fields=result.missing_fields,
    #         expected_fields=result.expected_fields,
    #     )

    #     if not (200 <= status_code < 300):
    #         self.collector.add_unsupported_param(
    #             param_name="model",
    #             param_value=model,
    #             test_name=test_name,
    #             reason=f"HTTP {status_code}: {response_body}",
    #         )

    #     assert 200 <= status_code < 300
    #     assert result.is_valid

    def test_param_encoding_format(self):
        """测试 encoding_format 参数（base64）"""
        test_name = "test_param_encoding_format"
        params = {**self.BASE_PARAMS, "encoding_format": "base64"}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, EmbeddingResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("encoding_format", "base64"),
        )

        assert 200 <= status_code < 300
        assert result.is_valid

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

        result = ResponseValidator.validate_response(response, EmbeddingResponse)

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

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_param_dimensions(self):
        """测试 dimensions 参数（仅 v3 模型支持）"""
        test_name = "test_param_dimensions"
        params = {
            "model": "text-embedding-3-small",
            "input": "Test",
            "dimensions": 512,
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, EmbeddingResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("dimensions", 512),
        )

        assert 200 <= status_code < 300
        assert result.is_valid
