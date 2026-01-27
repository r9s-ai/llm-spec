"""OpenAI Audio Speech API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector


class TestAudioSpeech:
    """Audio Speech API 测试类"""

    ENDPOINT = "/v1/audio/speech"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "model": "tts-1",
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
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}"

    @pytest.mark.parametrize(
        "voice",
        [
            "alloy",
            "echo",
            "fable",
            "onyx",
            "nova",
            "shimmer",
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
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="voice",
                param_value=voice,
                test_name=test_name,
                reason=f"HTTP {status_code}",
            )

        assert 200 <= status_code < 300

    def test_param_response_format(self):
        """测试 response_format 参数"""
        test_name = "test_param_response_format"
        params = {**self.BASE_PARAMS, "response_format": "mp3"}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="response_format",
                param_value="mp3",
                test_name=test_name,
                reason=f"HTTP {status_code}",
            )

        assert 200 <= status_code < 300

    def test_param_speed(self):
        """测试 speed 参数"""
        test_name = "test_param_speed"
        params = {**self.BASE_PARAMS, "speed": 1.0}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="speed",
                param_value=1.0,
                test_name=test_name,
                reason=f"HTTP {status_code}",
            )

        assert 200 <= status_code < 300
