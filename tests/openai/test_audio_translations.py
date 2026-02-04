"""OpenAI Audio Translations API 测试"""

from pathlib import Path

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.audio import AudioTranslationResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.openai import OpenAIAdapter


class TestAudioTranslations:
    """Audio Translations API 测试类"""
    client: OpenAIAdapter
    collector: ReportCollector

    ENDPOINT = "/v1/audio/translations"

    # 基线参数：仅包含必需参数（file 在具体请求时通过 multipart 传递）
    BASE_PARAMS = {
        "model": "whisper-1",
    }

    # 测试用音频文件
    AUDIO_EN = "test_assets/audio/hello_en.mp3"

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, request: pytest.FixtureRequest, openai_client: OpenAIAdapter):
        """为整个测试类设置报告收集器"""
        collector = ReportCollector(
            provider="openai",
            endpoint=self.ENDPOINT,
            base_url=openai_client.get_base_url(),
        )

        self.__class__.client = openai_client
        self.__class__.collector = collector

        yield

        output_dir = getattr(request.config, "run_reports_dir", "./reports")
        report_path = collector.finalize(output_dir)
        print(f"\n报告已生成: {report_path}")

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _request_with_file(
        self,
        params: dict,
        file_path: str | Path | None = None,
        mime_type: str = "audio/mpeg",
    ) -> tuple[object, Path]:
        """使用 multipart/form-data 发送带文件的请求"""
        path = Path(file_path or self.AUDIO_EN)
        with path.open("rb") as f:
            files = {"file": (path.name, f, mime_type)}
            response = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )
        # 返回 response 与路径用于报告展示（文件实际已通过 multipart 上传）
        return response, path

    # ------------------------------------------------------------------
    # 基线
    # ------------------------------------------------------------------
    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        params = {**self.BASE_PARAMS}
        response, used_path = self._request_with_file(params)
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)
        record_params = {**params, "file": used_path.name}

        # Audio translations endpoint should return JSON; validate_response will parse JSON from httpx.Response.
        # Here we only assert schema validity if response is JSON.
        result = ResponseValidator.validate_response(response, AudioTranslationResponse)

        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        # baseline 失败也需要记录：把必需参数标为不支持（无对照基线可用）
        if not (200 <= status_code < 300):
            # BASE_PARAMS 仅包含 model；file 属于 multipart 必需字段
            self.collector.add_unsupported_param(
                param_name="model",
                param_value=record_params.get("model"),
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )
            self.collector.add_unsupported_param(
                param_name="file",
                param_value="<multipart>",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )
        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"

    # ------------------------------------------------------------------
    # 参数测试
    # ------------------------------------------------------------------
    @pytest.mark.parametrize(
        "response_format",
        [
            "json",
            "text",  # 文本格式，ResponseValidator 将跳过结构校验
            "srt",
            "verbose_json",
            "vtt",
        ],
    )
    def test_response_format_variants(self, response_format):
        """测试 response_format 参数"""
        test_name = f"test_response_format[{response_format}]"
        params = {**self.BASE_PARAMS, "response_format": response_format}

        response, used_path = self._request_with_file(params)
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)
        record_params = {**params, "file": used_path.name}

        result = ResponseValidator.validate_response(response, AudioTranslationResponse)
        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("response_format", response_format),
        )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_prompt(self):
        """测试 prompt 参数（英文提示）"""
        test_name = "test_prompt"
        params = {
            **self.BASE_PARAMS,
            "prompt": "Please translate the audio politely into English.",
        }

        response, used_path = self._request_with_file(params)
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)
        record_params = {**params, "file": used_path.name}

        result = ResponseValidator.validate_response(response, AudioTranslationResponse)
        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("prompt", params["prompt"]),
        )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_temperature"
        params = {**self.BASE_PARAMS, "temperature": 0.5}

        response, used_path = self._request_with_file(params)
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)
        record_params = {**params, "file": used_path.name}

        result = ResponseValidator.validate_response(response, AudioTranslationResponse)
        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
            tested_param=("temperature", 0.5),
        )

        assert 200 <= status_code < 300
        assert result.is_valid
