"""Google Gemini EmbedContent API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.gemini import EmbedContentResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.gemini import GeminiAdapter

class TestEmbedContent:
    """EmbedContent API 测试类"""

    client: GeminiAdapter

    collector: ReportCollector

    ENDPOINT = "/v1beta/models/text-embedding-005:embedContent"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "content": {"parts": [{"text": "Hello, world!"}]},
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, request: pytest.FixtureRequest, gemini_client: GeminiAdapter):
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
        output_dir = getattr(request.config, "run_reports_dir", "./reports")
        report_path = collector.finalize(output_dir)
        print(f"\n报告已生成: {report_path}")

    # ========================================================================
    # 阶段 1: 基线测试
    # ========================================================================

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = response.text

        result = ResponseValidator.validate_response(response, EmbedContentResponse)

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
            self.collector.add_unsupported_param(
                param_name="content",
                param_value="object",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"

    # ========================================================================
    # 阶段 2: TaskType 测试
    # ========================================================================

    def test_param_task_type_retrieval_query(self):
        """测试 taskType 参数 - RETRIEVAL_QUERY"""
        test_name = "test_param_task_type_retrieval_query"
        params = {
            **self.BASE_PARAMS,
            "taskType": "RETRIEVAL_QUERY",
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = response.text

        result = ResponseValidator.validate_response(response, EmbedContentResponse)

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
                param_name="taskType",
                param_value="RETRIEVAL_QUERY",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_param_task_type_retrieval_document(self):
        """测试 taskType 参数 - RETRIEVAL_DOCUMENT"""
        test_name = "test_param_task_type_retrieval_document"
        params = {
            **self.BASE_PARAMS,
            "taskType": "RETRIEVAL_DOCUMENT",
            "title": "Sample document title",
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = response.text

        result = ResponseValidator.validate_response(response, EmbedContentResponse)

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
                param_name="taskType",
                param_value="RETRIEVAL_DOCUMENT",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )
            self.collector.add_unsupported_param(
                param_name="title",
                param_value=params.get("title"),
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    @pytest.mark.parametrize(
        "task_type",
        [
            "RETRIEVAL_QUERY",
            "RETRIEVAL_DOCUMENT",
            "SEMANTIC_SIMILARITY",
            "CLASSIFICATION",
            "CLUSTERING",
            "QUESTION_ANSWERING",
            "FACT_VERIFICATION",
        ],
    )
    def test_task_type_variants(self, task_type):
        """测试不同的 taskType 变体"""
        test_name = f"test_task_type_variants[{task_type}]"
        params = {
            **self.BASE_PARAMS,
            "taskType": task_type,
        }

        # RETRIEVAL_DOCUMENT 需要 title 参数
        if task_type == "RETRIEVAL_DOCUMENT":
            params["title"] = "Sample document"

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = response.text

        result = ResponseValidator.validate_response(response, EmbedContentResponse)

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
                param_name="taskType",
                param_value=task_type,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    # ========================================================================
    # 阶段 3: 输出维度测试
    # ========================================================================

    def test_param_output_dimensionality(self):
        """测试 outputDimensionality 参数"""
        test_name = "test_param_output_dimensionality"
        params = {
            **self.BASE_PARAMS,
            "outputDimensionality": 256,
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = response.text

        result = ResponseValidator.validate_response(response, EmbedContentResponse)

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
                param_name="outputDimensionality",
                param_value=256,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid
