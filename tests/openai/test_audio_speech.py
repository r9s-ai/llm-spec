"""OpenAI Audio Speech API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector


class TestAudioSpeech:
    """Audio Speech API 测试类"""

    ENDPOINT = "/v1/audio/speech"
    # 音频接口返回二进制流，没有 JSON 字段，但报告仍需要记录“期望字段”
    EXPECTED_FIELDS = ["binary_audio_stream"]

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "gpt-4o-mini-tts",
        "input": "Hello, world!",
        "voice": "alloy",
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

    # ========================================================================
    # 阶段 1: 基线测试
    # ========================================================================

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )

        # 音频响应是二进制数据，只验证状态码
        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            expected_fields=self.EXPECTED_FIELDS,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}"

    # ========================================================================
    # 阶段 2: 声音变体测试
    # ========================================================================

    @pytest.mark.parametrize(
        "voice",
        [
            # 原有的 6 个声音
            "alloy",
            "echo",
            "fable",
            "onyx",
            "nova",
            "shimmer",
            # 新增的 7 个声音
            "ash",
            "ballad",
            "coral",
            "sage",
            "verse",
            "marin",
            "cedar",
        ],
    )
    def test_voice_variants(self, voice):
        """测试不同的 voice 变体"""
        test_name = f"test_voice_variants[{voice}]"
        params = {**self.BASE_PARAMS, "voice": voice}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            expected_fields=self.EXPECTED_FIELDS,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="voice",
                param_value=voice,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300

    # ========================================================================
    # 阶段 3: 响应格式变体测试
    # ========================================================================

    @pytest.mark.parametrize(
        "response_format",
        [
            "mp3",
            "opus",
            "aac",
            "flac",
            "wav",
            "pcm",
        ],
    )
    def test_response_format_variants(self, response_format):
        """测试不同的 response_format 变体"""
        test_name = f"test_response_format_variants[{response_format}]"
        params = {**self.BASE_PARAMS, "response_format": response_format}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            expected_fields=self.EXPECTED_FIELDS,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="response_format",
                param_value=response_format,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300

    # ========================================================================
    # 阶段 4: 速度变体测试
    # ========================================================================

    @pytest.mark.parametrize(
        "speed",
        [
            0.25,
            0.5,
            1.0,
            1.5,
            2.0,
            4.0,
        ],
    )
    def test_speed_variants(self, speed):
        """测试不同的 speed 变体"""
        test_name = f"test_speed_variants[{speed}]"
        params = {**self.BASE_PARAMS, "speed": speed}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            expected_fields=self.EXPECTED_FIELDS,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="speed",
                param_value=speed,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300

    # ========================================================================
    # 阶段 5: 高级参数测试 (instructions, stream_format)
    # ========================================================================

    def test_param_instructions(self):
        """测试 instructions 参数"""
        test_name = "test_param_instructions"
        params = {
            **self.BASE_PARAMS,
            "instructions": "Speak in a cheerful and energetic tone.",
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            expected_fields=self.EXPECTED_FIELDS,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="instructions",
                param_value="Speak in a cheerful and energetic tone.",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300

    def test_param_stream_format_audio(self):
        """测试 stream_format 参数(audio 格式)"""
        test_name = "test_param_stream_format_audio"
        params = {**self.BASE_PARAMS, "stream_format": "audio"}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            expected_fields=self.EXPECTED_FIELDS,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="stream_format",
                param_value="audio",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300

    def test_param_stream_format_sse(self):
        """测试 stream_format 参数(sse 格式)"""
        test_name = "test_param_stream_format_sse"
        params = {
            **self.BASE_PARAMS,
            "stream_format": "sse",
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=None
            if 200 <= status_code < 300
            else f"HTTP {status_code}: {response_body}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="stream_format",
                param_value="sse",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
