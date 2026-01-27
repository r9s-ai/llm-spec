"""OpenAI Audio Transcriptions API 测试"""

from base64 import b64encode
from pathlib import Path

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.audio import AudioTranscriptionResponse
from llm_spec.validation.validator import ResponseValidator


class TestAudioTranscriptions:
    """Audio Transcriptions API 测试类"""

    ENDPOINT = "/v1/audio/transcriptions"

    # 基线参数：仅包含必需参数（file 在具体请求时通过 multipart 传递）
    BASE_PARAMS = {
        "model": "whisper-1",
    }

    # 测试用音频文件
    AUDIO_EN = "test_assets/audio/hello_en.mp3"
    AUDIO_ZH = "test_assets/audio/hello_zh.mp3"

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
            return self.client.request(
                endpoint=self.ENDPOINT,
                params=params,
                files=files,
            )

    def _data_url_from_file(self, file_path: str | Path) -> str:
        """构造 data URL（用于 known_speaker_references）"""
        path = Path(file_path)
        data = path.read_bytes()
        b64 = b64encode(data).decode("ascii")
        return f"data:audio/mpeg;base64,{b64}"

    def _validate_json_response(self, response_body):
        """仅在响应是 dict 时做 JSON 验证，非 JSON 响应直接视为通过。"""
        if not isinstance(response_body, dict):
            return True, None, [], []
        return ResponseValidator.validate(response_body, AudioTranscriptionResponse)

    # ------------------------------------------------------------------
    # 基线
    # ------------------------------------------------------------------
    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        params = {**self.BASE_PARAMS, "model": "whisper-1"}
        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

    # ------------------------------------------------------------------
    # 参数测试
    # ------------------------------------------------------------------
    def test_param_language(self):
        """测试 language 参数"""
        test_name = "test_param_language"
        params = {**self.BASE_PARAMS, "model": "whisper-1", "language": "en"}

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="language",
                param_value="en",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_param_temperature"
        params = {**self.BASE_PARAMS, "model": "whisper-1", "temperature": 0.0}

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_value=0.0,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # @pytest.mark.parametrize(
    #     "model",
    #     [
    #         "gpt-4o-mini-transcribe",
    #         "whisper-1",
    #     ],
    # )
    # def test_model_variants(self, model):
    #     """测试不同的 model 变体"""
    #     test_name = f"test_model_variants[{model}]"
    #     params = {**self.BASE_PARAMS, "model": model}

    #     status_code, headers, response_body = self._request_with_file(params)

    #     is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
    #         response_body
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
    #             param_value=model,
    #             test_name=test_name,
    #             reason=f"HTTP {status_code}: {response_body}",
    #         )

    #     assert 200 <= status_code < 300
    #     assert is_valid

    @pytest.mark.parametrize(
        "response_format",
        [
            "json",
            "text",  # 文本格式，ResponseValidator 将跳过结构校验
        ],
    )
    def test_response_format_variants(self, response_format):
        """测试 response_format 参数（常见格式）"""
        test_name = f"test_response_format[{response_format}]"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "response_format": response_format,
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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

    def test_prompt(self):
        """测试 prompt 参数"""
        test_name = "test_prompt"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "prompt": "Please transcribe in a friendly style.",
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="prompt",
                param_value=params["prompt"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_chunking_strategy_auto(self):
        """测试 chunking_strategy = auto"""
        test_name = "test_chunking_strategy_auto"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "chunking_strategy": "auto",
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="chunking_strategy",
                param_value="auto",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_chunking_strategy_server_vad(self):
        """测试 chunking_strategy = server_vad 对象"""
        test_name = "test_chunking_strategy_server_vad"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "chunking_strategy": {"type": "server_vad"},
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="chunking_strategy",
                param_value=params["chunking_strategy"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_include_logprobs(self):
        """测试 include=logprobs（仅支持部分模型 + response_format=json）"""
        test_name = "test_include_logprobs"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "include": ["logprobs"],
            "response_format": "json",
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="include",
                param_value=params["include"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_known_speakers(self):
        """测试 known_speaker_names + known_speaker_references"""
        test_name = "test_known_speakers"

        names = ["speaker_a", "speaker_b"]
        refs = [
            self._data_url_from_file(self.AUDIO_EN),
            self._data_url_from_file(self.AUDIO_ZH),
        ]

        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "known_speaker_names": names,
            "known_speaker_references": refs,
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="known_speaker_names/known_speaker_references",
                param_value={"names": names, "references": "[data URLs omitted]"},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_timestamp_granularities(self):
        """测试 timestamp_granularities（需 response_format=verbose_json）"""
        test_name = "test_timestamp_granularities"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "response_format": "verbose_json",
            "timestamp_granularities": ["word", "segment"],
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="timestamp_granularities",
                param_value=params["timestamp_granularities"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_stream_flag(self):
        """测试 stream=true（gpt-4o-mini-transcribe 支持；whisper-1 忽略）"""
        test_name = "test_stream_true"
        params = {
            **self.BASE_PARAMS,
            "model": "gpt-4o-mini-transcribe",
            "stream": True,
        }

        status_code, headers, response_body = self._request_with_file(params)

        is_valid, error_msg, missing_fields, expected_fields = self._validate_json_response(
            response_body
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
                param_name="stream",
                param_value=True,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
