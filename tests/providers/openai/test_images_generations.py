"""OpenAI Images API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.images import ImageResponse
from llm_spec.validation.validator import ResponseValidator


class TestImagesGenerations:
    """Images API 测试类"""

    ENDPOINT = "/v1/images/generations"

    # 基线参数：仅包含必需参数（dall-e-3）
    BASE_PARAMS = {
        "model": "dall-e-3",
        "prompt": "A cute cat",
        "n": 1,
    }

    # GPT image 专属基线
    BASE_GPT_PARAMS = {
        "model": "gpt-image-1.5",
        "prompt": "A simple geometric logo",
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

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
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

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

    # ========================================================================
    # 尺寸参数
    # ========================================================================
    def test_param_size(self):
        """测试 size 参数（dall-e-3 默认尺寸）"""
        test_name = "test_param_size"
        params = {**self.BASE_PARAMS, "size": "1024x1024"}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value="1024x1024",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

    @pytest.mark.parametrize("size", ["512x512", "256x256"])
    def test_param_size_dalle2(self, size):
        """测试 size 参数（dall-e-2 尺寸变体）"""
        test_name = f"test_param_size_dalle2[{size}]"
        params = {**self.BASE_PARAMS, "model": "dall-e-2", "size": size}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value=size,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize("size", ["1792x1024", "1024x1792"])
    def test_param_size_dalle3(self, size):
        """测试 dall-e-3 尺寸变体"""
        test_name = f"test_param_size_dalle3[{size}]"
        params = {**self.BASE_PARAMS, "size": size}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value=size,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 质量参数（dall-e-3）
    # ========================================================================
    @pytest.mark.parametrize("quality", ["hd", "standard"])
    def test_param_quality_dalle3(self, quality):
        """测试 quality 参数（dall-e-3）"""
        test_name = f"test_param_quality_dalle3[{quality}]"
        params = {**self.BASE_PARAMS, "quality": quality}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="quality",
                param_value=quality,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 响应格式 / 风格
    # ========================================================================
    @pytest.mark.parametrize("response_format", ["url", "b64_json"])
    def test_param_response_format(self, response_format):
        """测试 response_format 参数（dall-e-3/dall-e-2）"""
        test_name = f"test_param_response_format[{response_format}]"
        params = {**self.BASE_PARAMS, "response_format": response_format}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value=response_format,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize("style", ["vivid", "natural"])
    def test_param_style(self, style):
        """测试 style 参数（dall-e-3）"""
        test_name = f"test_param_style[{style}]"
        params = {**self.BASE_PARAMS, "style": style}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="style",
                param_value=style,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 数量 / 用户标识
    # ========================================================================
    def test_param_n_dalle2(self):
        """测试 n 参数（dall-e-2 支持多张）"""
        test_name = "test_param_n_dalle2"
        params = {**self.BASE_PARAMS, "model": "dall-e-2", "n": 2}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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

    def test_param_user(self):
        """测试 user 参数"""
        test_name = "test_param_user"
        params = {**self.BASE_PARAMS, "user": "user-123"}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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

    # ------------------------------------------------------------------
    # GPT Image 专属参数
    # ------------------------------------------------------------------
    def test_gpt_image_background_transparent(self):
        """测试 background 参数（透明背景，GPT image 模型）"""
        test_name = "test_gpt_image_background_transparent"
        params = {
            "model": "gpt-image-1.5",
            "prompt": "A simple logo with a transparent background",
            "background": "transparent",
            "output_format": "png",
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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

    @pytest.mark.parametrize("output_format", ["png", "jpeg", "webp"])
    def test_gpt_image_output_formats(self, output_format):
        """测试 output_format 变体（GPT image 模型）"""
        test_name = f"test_gpt_image_output_formats[{output_format}]"
        params = {
            **self.BASE_GPT_PARAMS,
            "prompt": "A minimal illustration of a rocket",
            "output_format": output_format,
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value=output_format,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_gpt_image_output_webp_compression(self):
        """测试 output_format=webp + output_compression（GPT image 模型）"""
        test_name = "test_gpt_image_output_webp_compression"
        params = {
            "model": "gpt-image-1.5",
            "prompt": "A futuristic city skyline",
            "output_format": "webp",
            "output_compression": 80,
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="output_format/output_compression",
                param_value={"output_format": "webp", "output_compression": 80},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_gpt_image_output_jpeg_compression(self):
        """测试 output_format=jpeg + output_compression（GPT image 模型）"""
        test_name = "test_gpt_image_output_jpeg_compression"
        params = {
            "model": "gpt-image-1.5",
            "prompt": "A portrait photo realistic style",
            "output_format": "jpeg",
            "output_compression": 80,
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="output_format/output_compression",
                param_value={"output_format": "jpeg", "output_compression": 80},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize("background", ["transparent", "opaque", "auto"])
    def test_gpt_image_background_variants(self, background):
        """测试 background 变体（GPT image 模型）"""
        test_name = f"test_gpt_image_background_variants[{background}]"
        params = {
            **self.BASE_GPT_PARAMS,
            "prompt": "A product icon with specified background",
            "background": background,
            # 若透明背景，默认 png 支持透明；其它背景也可用 png
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value=background,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_gpt_image_moderation_low(self):
        """测试 moderation=low（GPT image 模型）"""
        test_name = "test_gpt_image_moderation_low"
        params = {
            "model": "gpt-image-1.5",
            "prompt": "A landscape painting with trees and river",
            "moderation": "low",
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="moderation",
                param_value="low",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_gpt_image_moderation_auto(self):
        """测试 moderation=auto（GPT image 模型）"""
        test_name = "test_gpt_image_moderation_auto"
        params = {
            **self.BASE_GPT_PARAMS,
            "prompt": "A sketch of a city skyline",
            "moderation": "auto",
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="moderation",
                param_value="auto",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_gpt_image_quality_high(self):
        """测试 quality=high（GPT image 模型）"""
        test_name = "test_gpt_image_quality_high"
        params = {
            **self.BASE_GPT_PARAMS,
            "prompt": "A detailed illustration of a spaceship cockpit",
            "quality": "high",
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="quality",
                param_value="high",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize("quality", ["medium", "low", "auto"])
    def test_gpt_image_quality_variants(self, quality):
        """测试 quality 其它取值（GPT image 模型）"""
        test_name = f"test_gpt_image_quality_variants[{quality}]"
        params = {
            **self.BASE_GPT_PARAMS,
            "prompt": "A clean line-art illustration",
            "quality": quality,
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_name="quality",
                param_value=quality,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_gpt_image_n_multiple(self):
        """测试 n 参数（GPT image 模型，多张生成）"""
        test_name = "test_gpt_image_n_multiple"
        params = {**self.BASE_GPT_PARAMS, "prompt": "A set of minimal icons", "n": 2}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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

    @pytest.mark.parametrize("size", ["1024x1024", "1536x1024", "1024x1536"])
    def test_gpt_image_sizes(self, size):
        """测试 size 参数（GPT image 模型）"""
        test_name = f"test_gpt_image_sizes[{size}]"
        params = {**self.BASE_GPT_PARAMS, "prompt": "A futuristic device render", "size": size}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
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
                param_value=size,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ------------------------------------------------------------------
    # GPT Image 流式与 partial_images
    # ------------------------------------------------------------------
    def test_gpt_image_stream_basic(self):
        """测试 stream=true（GPT image 模型，基础流式）"""
        import json

        test_name = "test_gpt_image_stream_basic"
        params = {**self.BASE_GPT_PARAMS, "prompt": "A quick sketch of a tree", "stream": True}

        chunks = []
        raw_lines = []

        try:
            for chunk_bytes in self.client.stream(
                endpoint=self.ENDPOINT,
                params=params,
            ):
                chunk_str = chunk_bytes.decode("utf-8")
                raw_lines.append(repr(chunk_str))
                for line in chunk_str.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            chunks.append(chunk_data)
                        except json.JSONDecodeError:
                            # 跳过非 JSON 行
                            pass

            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=200,
                response_body={"chunks_count": len(chunks)},
                error=None,
                missing_fields=[],
            )

            assert len(chunks) > 0, f"应收到至少一个 chunk，原始行数={len(raw_lines)}"

        except Exception as e:
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

    def test_gpt_image_partial_images(self):
        """测试 partial_images 参数（GPT image 模型）"""
        import json

        test_name = "test_gpt_image_partial_images"
        params = {
            **self.BASE_GPT_PARAMS,
            "prompt": "A mountain landscape",
            "stream": True,
            "partial_images": 1,
        }

        chunks = []
        raw_lines = []

        try:
            for chunk_bytes in self.client.stream(
                endpoint=self.ENDPOINT,
                params=params,
            ):
                chunk_str = chunk_bytes.decode("utf-8")
                raw_lines.append(repr(chunk_str))
                for line in chunk_str.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            chunks.append(chunk_data)
                        except json.JSONDecodeError:
                            pass

            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=200,
                response_body={"chunks_count": len(chunks)},
                error=None,
                missing_fields=[],
            )

            assert len(chunks) > 0, f"应收到至少一个 chunk，原始行数={len(raw_lines)}"

        except Exception as e:
            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=500,
                response_body=None,
                error=str(e),
            )
            self.collector.add_unsupported_param(
                param_name="partial_images",
                param_value=1,
                test_name=test_name,
                reason=f"partial_images 流式请求失败: {str(e)}",
            )
            pytest.fail(f"partial_images 流式测试失败: {str(e)}")
