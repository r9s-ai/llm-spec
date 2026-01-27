"""OpenAI Audio Translations API 测试"""

from pathlib import Path

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.audio import AudioTranslationResponse
from llm_spec.validation.validator import ResponseValidator


class TestAudioTranslations:
    """Audio Translations API 测试类"""

    ENDPOINT = "/v1/audio/translations"

    # 基线参数：仅包含必需参数（file 在具体请求时通过 multipart 传递）
    BASE_PARAMS = {
        "model": "whisper-1",
    }

    # 测试用音频文件
    AUDIO_EN = "test_assets/audio/hello_en.mp3"

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

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _request_with_file(
        self,
        params: dict,
        file_path: str | Path | None = None,
        mime_type: str = "audio/mpeg",
    ):
        """使用 multipart/form-data 发送带文件的请求"""
        path = Path(file_path or self.AUDIO_EN)
        with path.open("rb") as f:
            files = {"file": (path.name, f, mime_type)}
            status_code, headers, response_body = self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )
        # 返回路径用于报告展示（文件实际已通过 multipart 上传）
        return status_code, headers, response_body, path

    def _validate_json_response(self, response_body):
        """仅在响应是 dict 时做 JSON 验证，非 JSON 响应直接视为通过。"""
        if not isinstance(response_body, dict):
            return True, None, [], []
        return ResponseValidator.validate(response_body, AudioTranslationResponse)

    # ------------------------------------------------------------------
    # 基线
    # ------------------------------------------------------------------
    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        params = {**self.BASE_PARAMS}
        status_code, headers, response_body, used_path = self._request_with_file(params)
        record_params = {**params, "file": used_path.name}

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
        )

        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

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

        status_code, headers, response_body, used_path = self._request_with_file(params)
        record_params = {**params, "file": used_path.name}

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
        )

        self.collector.record_test(
            test_name=test_name,
            params=record_params,
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

    def test_prompt(self):
        """测试 prompt 参数（英文提示）"""
        test_name = "test_prompt"
        params = {
            **self.BASE_PARAMS,
            "prompt": "Please translate the audio politely into English.",
        }

        status_code, headers, response_body, used_path = self._request_with_file(params)
        record_params = {**params, "file": used_path.name}

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
        )

        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="prompt",
                param_value=params["prompt"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_temperature"
        params = {**self.BASE_PARAMS, "temperature": 0.5}

        status_code, headers, response_body, used_path = self._request_with_file(params)
        record_params = {**params, "file": used_path.name}

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
        )

        self.collector.record_test(
            test_name=test_name,
            params=record_params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="temperature",
                param_value=0.5,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
