"""Google Gemini Generate Content API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.gemini import GenerateContentResponse
from llm_spec.validation.validator import ResponseValidator


class TestGenerateContent:
    """Generate Content API 测试类"""

    # ========================================================================
    # 模型 Endpoint 配置
    # ========================================================================

    # Gemini 3 Flash Preview- 主要测试模型
    # 支持: 基础参数, thinkingConfig (4级别), responseModalities (TEXT, IMAGE)
    ENDPOINT_FLASH = "/v1beta/models/gemini-3-flash-preview:generateContent"

    # Gemini 3 Pro - Pro 级别模型
    # 支持: 基础参数, thinkingConfig (2级别: low, high)
    # ENDPOINT_PRO = "/v1beta/models/gemini-3-pro:generateContent"

    # Gemini 3 Pro Image (Nano Banana Pro) - 图像生成模型
    # 支持: imageConfig, responseModalities[IMAGE], 1K/2K/4K 图像生成
    # ENDPOINT_IMAGE = "/v1beta/models/gemini-3-pro-image-preview:generateContent"

    # Gemini 2.5 Flash TTS - 语音生成模型
    # 支持: speechConfig, voiceConfig, 文本转语音
    # ENDPOINT_TTS_FLASH = "/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"

    # Gemini 2.5 Pro TTS - Pro 级语音生成模型
    # 支持: speechConfig, voiceConfig, 文本转语音
    # ENDPOINT_TTS_PRO = "/v1beta/models/gemini-2.5-pro-preview-tts:generateContent"

    # 默认使用 Gemini 3 Flash
    ENDPOINT = ENDPOINT_FLASH

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "contents": [{"parts": [{"text": "Hello"}]}],
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, gemini_client):
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
            response_body, GenerateContentResponse
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

    def test_param_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_param_temperature"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"temperature": 0.7},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.temperature",
                param_value=0.7,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_max_output_tokens(self):
        """测试 maxOutputTokens 参数"""
        test_name = "test_param_max_output_tokens"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"maxOutputTokens": 100},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.maxOutputTokens",
                param_value=100,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 2: 基础参数测试 (控制变量法)
    # ========================================================================

    def test_param_top_p(self):
        """测试 topP 参数"""
        test_name = "test_param_top_p"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"topP": 0.9},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.topP",
                param_value=0.9,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_top_k(self):
        """测试 topK 参数"""
        test_name = "test_param_top_k"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"topK": 40},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.topK",
                param_value=40,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_candidate_count(self):
        """测试 candidateCount 参数（生成多个候选响应）"""
        test_name = "test_param_candidate_count"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"candidateCount": 2},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.candidateCount",
                param_value=2,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_stop_sequences(self):
        """测试 stopSequences 参数"""
        test_name = "test_param_stop_sequences"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"stopSequences": ["END", "STOP"]},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.stopSequences",
                param_value=["END", "STOP"],
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 3: 响应格式测试
    # ========================================================================

    def test_response_format_json(self):
        """测试 JSON 响应格式"""
        test_name = "test_response_format_json"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"responseMimeType": "application/json"},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.responseMimeType",
                param_value="application/json",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_response_format_json_with_schema(self):
        """测试带 schema 的 JSON 响应格式"""
        test_name = "test_response_format_json_with_schema"
        params = {
            "contents": [{"parts": [{"text": "List 3 popular cookie recipes."}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "recipes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                },
                            },
                        }
                    },
                },
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.responseSchema",
                param_value="json_schema",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 4: 安全设置测试
    # ========================================================================

    def test_param_safety_settings(self):
        """测试 safetySettings 参数"""
        test_name = "test_param_safety_settings"
        params = {
            **self.BASE_PARAMS,
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                }
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="safetySettings",
                param_value="harassment_medium",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize(
        "threshold",
        [
            "BLOCK_NONE",
            "BLOCK_ONLY_HIGH",
            "BLOCK_MEDIUM_AND_ABOVE",
            "BLOCK_LOW_AND_ABOVE",
        ],
    )
    def test_safety_threshold_variants(self, threshold):
        """测试不同的安全阈值变体"""
        test_name = f"test_safety_threshold_variants[{threshold}]"
        params = {
            **self.BASE_PARAMS,
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": threshold,
                }
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="safetySettings.threshold",
                param_value=threshold,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 5: 系统指令测试
    # ========================================================================

    def test_param_system_instruction(self):
        """测试 systemInstruction 参数"""
        test_name = "test_param_system_instruction"
        params = {
            **self.BASE_PARAMS,
            "systemInstruction": {
                "parts": [{"text": "You are a helpful and friendly assistant."}]
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="systemInstruction",
                param_value="system_prompt",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 6: 工具调用测试
    # ========================================================================

    def test_param_function_calling(self):
        """测试函数调用功能"""
        test_name = "test_param_function_calling"
        params = {
            "contents": [{"parts": [{"text": "What's the weather in Tokyo?"}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "get_weather",
                            "description": "Get the current weather for a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "The city name",
                                    }
                                },
                                "required": ["location"],
                            },
                        }
                    ]
                }
            ],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="tools.functionDeclarations",
                param_value="function_calling",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_code_execution(self):
        """测试代码执行功能"""
        test_name = "test_param_code_execution"
        params = {
            "contents": [{"parts": [{"text": "What is the sum of the first 50 prime numbers?"}]}],
            "tools": [{"codeExecution": {}}],
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="tools.codeExecution",
                param_value="code_execution",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 7: 生成控制进阶参数（惩罚和种子）
    # ========================================================================

    def test_param_presence_penalty(self):
        """测试 presencePenalty 参数（对已出现token的惩罚）"""
        test_name = "test_param_presence_penalty"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"presencePenalty": 0.5},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.presencePenalty",
                param_value=0.5,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_frequency_penalty(self):
        """测试 frequencyPenalty 参数（基于频率的token惩罚）"""
        test_name = "test_param_frequency_penalty"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"frequencyPenalty": 0.5},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.frequencyPenalty",
                param_value=0.5,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_seed(self):
        """测试 seed 参数（确保生成结果可重复）"""
        test_name = "test_param_seed"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"seed": 42},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.seed",
                param_value=42,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 8: 概率信息参数
    # ========================================================================

    def test_param_response_logprobs(self):
        """测试 responseLogprobs 参数（返回token的对数概率）"""
        test_name = "test_param_response_logprobs"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"responseLogprobs": True},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.responseLogprobs",
                param_value=True,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    def test_param_logprobs(self):
        """测试 logprobs 参数（与 responseLogprobs 配合使用）"""
        test_name = "test_param_logprobs"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {
                "responseLogprobs": True,  # 依赖参数
                "logprobs": 3,
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.logprobs",
                param_value=3,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 9: 特定场景参数
    # ========================================================================

    def test_param_audio_timestamp(self):
        """测试 audioTimestamp 参数（音频内容时间戳）"""
        test_name = "test_param_audio_timestamp"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"audioTimestamp": True},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.audioTimestamp",
                param_value=True,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize(
        "resolution",
        [
            "media_resolution_low",
            "media_resolution_medium",
            "media_resolution_high",
            "media_resolution_ultra_high",
        ],
    )
    def test_param_media_resolution(self, resolution):
        """测试 mediaResolution 参数（控制图片/视频处理质量）"""
        test_name = f"test_param_media_resolution[{resolution}]"

        # 1x1 透明 PNG (base64)
        sample_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        params = {
            "contents": [
                {
                    "parts": [
                        {"text": "Describe this image"},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": sample_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"mediaResolution": resolution},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.mediaResolution",
                param_value=resolution,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 10: 响应模态控制
    # ========================================================================

    @pytest.mark.parametrize(
        "modalities",
        [
            ["TEXT"],
            ["IMAGE"],
            ["AUDIO"],
        ],
    )
    def test_param_response_modalities(self, modalities):
        """测试 responseModalities 参数（控制响应模态类型）"""
        test_name = f"test_param_response_modalities[{','.join(modalities)}]"

        endpoint = self.ENDPOINT_FLASH  

        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"responseModalities": modalities},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=endpoint,  # 使用选择的 endpoint
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.responseModalities",
                param_value=modalities,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 11: 语音配置（speechConfig + voiceConfig）
    # ========================================================================

    @pytest.mark.parametrize(
        "voice_name",
        [
            "Kore",
            "Puck",
            "Charon",
            "Fenrir",
        ],
    )
    def test_param_speech_config(self, voice_name):
        """测试 speechConfig.voiceConfig 参数（语音输出配置）"""
        test_name = f"test_param_speech_config[{voice_name}]"

        endpoint = self.ENDPOINT_FLASH

        params = {
            **self.BASE_PARAMS,
            "generationConfig": {
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=endpoint,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.speechConfig.voiceConfig",
                param_value=voice_name,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 12: 思考配置（thinkingConfig - Gemini 3）
    # ========================================================================

    @pytest.mark.parametrize(
        "thinking_level",
        [
            "minimal",
            "low",
            "medium",
            "high",
        ],
    )
    def test_param_thinking_config(self, thinking_level):
        """测试 thinkingConfig.thinkingLevel 参数（Gemini 3思考深度）"""
        test_name = f"test_param_thinking_config[{thinking_level}]"

        # Gemini 3 Flash 支持所有 4 个级别
        # Gemini 3 Pro 仅支持 low 和 high
        endpoint = self.ENDPOINT_FLASH

        params = {
            **self.BASE_PARAMS,
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingLevel": thinking_level
                }
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=endpoint,  # 使用 Flash 支持所有级别
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.thinkingConfig.thinkingLevel",
                param_value=thinking_level,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 13: 图像配置（imageConfig）
    # ========================================================================

    @pytest.mark.parametrize(
        "aspect_ratio",
        [
            "1:1",
            "2:3",
            "3:2",
            "3:4",
            "4:3",
            "4:5",
            "5:4",
            "9:16",
            "16:9",
            "21:9",
        ],
    )
    def test_param_image_config_aspect_ratio(self, aspect_ratio):
        """测试 imageConfig.aspectRatio 参数（图像生成宽高比）"""
        test_name = f"test_param_image_config_aspect_ratio[{aspect_ratio}]"

        endpoint = self.ENDPOINT_IMAGE

        params = {
            "contents": [{"parts": [{"text": "Generate an image of a sunset"}]}],
            "generationConfig": {
                "imageConfig": {
                    "aspectRatio": aspect_ratio
                }
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=endpoint,  # 使用图像生成模型
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.imageConfig.aspectRatio",
                param_value=aspect_ratio,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize(
        "image_size",
        [
            "1K",
            "2K",
            "4K",
        ],
    )
    def test_param_image_config_size(self, image_size):
        """测试 imageConfig.imageSize 参数（图像生成尺寸）"""
        test_name = f"test_param_image_config_size[{image_size}]"

        endpoint = self.ENDPOINT_IMAGE

        params = {
            "contents": [{"parts": [{"text": "Generate an image of mountains"}]}],
            "generationConfig": {
                "imageConfig": {
                    "imageSize": image_size
                }
            },
        }

        status_code, headers, response_body = self.client.request(
            endpoint=endpoint,  # 使用图像生成模型
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.imageConfig.imageSize",
                param_value=image_size,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    # ========================================================================
    # 阶段 14: 增强功能参数
    # ========================================================================

    def test_param_enable_enhanced_civic_answers(self):
        """测试 enableEnhancedCivicAnswers 参数（增强公民问答）"""
        test_name = "test_param_enable_enhanced_civic_answers"
        params = {
            "contents": [{"parts": [{"text": "Who is the current president of the United States?"}]}],
            "generationConfig": {"enableEnhancedCivicAnswers": True},
        }

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields, expected_fields = ResponseValidator.validate(
            response_body, GenerateContentResponse
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
                param_name="generationConfig.enableEnhancedCivicAnswers",
                param_value=True,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
