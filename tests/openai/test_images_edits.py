"""OpenAI Images Edit API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.images import ImageResponse
from llm_spec.validation.validator import ResponseValidator


class TestImagesEdits:
    """Images Edit API 测试类"""

    ENDPOINT = "/v1/images/edits"
    IMAGE_PATH = "test_assets/images/test_base.png"

    # 基线参数：仅包含必需参数（GPT image 模型）
    BASE_PARAMS = {
        "model": "gpt-image-1.5",
        "prompt": "Replace the background with a blue sky.",
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, openai_client):
        """为整个测试类设置报告收集器"""
        collector = ReportCollector(
            provider="openai",
            endpoint=self.ENDPOINT,
            base_url=openai_client.get_base_url(),
        )

        self.__class__.client = openai_client
        self.__class__.collector = collector

        yield

        report_path = collector.finalize()
        print(f"\n报告已生成: {report_path}")

    # ====================================================================
    # 基线测试
    # ====================================================================
    def test_baseline(self):
        """测试基线：gpt-image-1.5 单图 + prompt"""
        test_name = "test_baseline"

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=self.BASE_PARAMS,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="model",
                param_value=self.BASE_PARAMS["model"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

    # ====================================================================
    # 模型变体
    # ====================================================================
    # def test_model_variant_dalle2(self):
    #     """测试 dall-e-2 基线（单图）"""
    #     test_name = "test_model_variant_dalle2"
    #     params = {**self.BASE_PARAMS, "model": "dall-e-2"}

    #     with open(self.IMAGE_PATH, "rb") as img:
    #         files = {"image": ("image.png", img, "image/png")}
    #         status_code, headers, response_body = self.client.request(
    #             endpoint=self.ENDPOINT,
    #             params=params,
    #             files=files,
    #         )

    #     is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
    #         response_body, ImageResponse
    #     )

    #     self.collector.record_test(
    #         test_name=test_name,
    #         params=params,
    #         status_code=status_code,
    #         response_body=response_body,
    #         error=error_msg if not is_valid else None,
    #         missing_fields=missing_fields,
    #         expected_fields=expected_fields,
    #     )

    #     if not (200 <= status_code < 300):
    #         self.collector.add_unsupported_param(
    #             param_name="model",
    #             param_value="dall-e-2",
    #             test_name=test_name,
    #             reason=f"HTTP {status_code}: {response_body}",
    #         )

    #     assert 200 <= status_code < 300
    #     assert is_valid

    # ====================================================================
    # 参数变体（控制变量法）
    # ====================================================================
    def test_param_response_format_url_dalle2(self):
        """dall-e-2 支持 response_format=url"""
        test_name = "test_param_response_format_url_dalle2"
        params = {**self.BASE_PARAMS, "model": "dall-e-2", "response_format": "url"}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="response_format",
                param_value="url",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_background_transparent(self):
        """GPT image 支持 background 透明"""
        test_name = "test_param_background_transparent"
        params = {**self.BASE_PARAMS, "background": "transparent"}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="background",
                param_value="transparent",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_output_format_webp(self):
        """GPT image 支持 output_format=webp"""
        test_name = "test_param_output_format_webp"
        params = {**self.BASE_PARAMS, "output_format": "webp"}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="output_format",
                param_value="webp",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_output_compression(self):
        """GPT image 支持 output_compression (webp/jpeg)"""
        test_name = "test_param_output_compression"
        params = {**self.BASE_PARAMS, "output_format": "webp", "output_compression": 80}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="output_compression",
                param_value=80,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_size_gpt_landscape(self):
        """GPT image 尺寸横版"""
        test_name = "test_param_size_gpt_landscape"
        params = {**self.BASE_PARAMS, "size": "1536x1024"}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="size",
                param_value="1536x1024",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_n_multiple(self):
        """生成多张图片 (n=2)"""
        test_name = "test_param_n_multiple"
        params = {**self.BASE_PARAMS, "n": 2}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="n",
                param_value=2,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_input_fidelity_high(self):
        """输入忠实度（仅 GPT image 模型）"""
        test_name = "test_param_input_fidelity_high"
        params = {**self.BASE_PARAMS, "input_fidelity": "high"}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="input_fidelity",
                param_value="high",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_mask_png(self):
        """带 mask 的编辑（mask 与第一张图同尺寸 PNG）"""
        test_name = "test_param_mask_png"
        params = {**self.BASE_PARAMS}

        with open(self.IMAGE_PATH, "rb") as img, open(self.IMAGE_PATH, "rb") as mask:
            files = {
                "image": ("image.png", img, "image/png"),
                "mask": ("mask.png", mask, "image/png"),
            }
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="mask",
                param_value="png",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_user(self):
        """用户标识 user"""
        test_name = "test_param_user"
        params = {**self.BASE_PARAMS, "user": "user-123"}

        with open(self.IMAGE_PATH, "rb") as img:
            files = {"image": ("image.png", img, "image/png")}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, ImageResponse
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
                param_name="user",
                param_value="user-123",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

