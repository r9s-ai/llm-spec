"""Google Gemini StreamGenerateContent API 测试

测试 Gemini 的流式内容生成功能。
StreamGenerateContent 支持所有 GenerateContent 的功能，但以 SSE 流式方式返回。
"""

import json

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.gemini import GenerateContentResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.gemini import GeminiAdapter

class TestStreamGenerateContent:
    """StreamGenerateContent API 测试类"""

    client: GeminiAdapter

    collector: ReportCollector

    # ========================================================================
    # 模型 Endpoint 配置
    # ========================================================================

    # Gemini 3 Flash - 主要测试模型
    # 支持: 基础参数, thinkingConfig (4级别), responseModalities (TEXT, IMAGE)
    ENDPOINT_FLASH = "/v1beta/models/gemini-3-flash-preview:streamGenerateContent"

    # # Gemini 3 Pro - Pro 级别模型
    # # 支持: 基础参数, thinkingConfig (2级别: low, high)
    # ENDPOINT_PRO = "/v1beta/models/gemini-3-pro:streamGenerateContent"

    # # Gemini 3 Pro Image (Nano Banana Pro) - 图像生成模型
    # # 支持: imageConfig, responseModalities[IMAGE], 1K/2K/4K 图像生成
    # ENDPOINT_IMAGE = "/v1beta/models/gemini-3-pro-image-preview:streamGenerateContent"

    # # Gemini 2.5 Flash TTS - 语音生成模型
    # # 支持: speechConfig, voiceConfig, 文本转语音
    # ENDPOINT_TTS_FLASH = "/v1beta/models/gemini-2.5-flash-preview-tts:streamGenerateContent"

    # # Gemini 2.5 Pro TTS - Pro 级语音生成模型
    # # 支持: speechConfig, voiceConfig, 文本转语音
    # ENDPOINT_TTS_PRO = "/v1beta/models/gemini-2.5-pro-preview-tts:streamGenerateContent"

    # 默认使用 Gemini 3 Flash
    ENDPOINT = ENDPOINT_FLASH

    # 基线参数
    BASE_PARAMS = {
        "contents": [{"parts": [{"text": "Say hello"}]}],
    }

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, gemini_client: GeminiAdapter):
        """为整个测试类设置报告收集器"""
        collector = ReportCollector(
            provider="gemini",
            endpoint=self.ENDPOINT,
            base_url=gemini_client.get_base_url(),
        )

        self.__class__.client = gemini_client
        self.__class__.collector = collector

        yield

        output_dir = getattr(request.config, "run_reports_dir", "./reports")
        report_path = collector.finalize(output_dir)
        print(f"\n报告已生成: {report_path}")

    # ========================================================================
    # 辅助方法：通用流式测试模板
    # ========================================================================

    def _run_streaming_test(
        self,
        test_name: str,
        params: dict,
        endpoint: str | None = None,
        unsupported_param: dict[str, object] | None = None,
    ) -> tuple[list[dict], str, bool]:
        """通用流式测试方法，减少代码重复

        Args:
            test_name: 用例名
            params: 请求参数
            endpoint: 可覆盖默认 endpoint
            unsupported_param: 可选 {"name": str, "value": Any}，在失败时记录 unsupported
        """
        if endpoint is None:
            endpoint = self.ENDPOINT

        chunks: list[dict] = []
        complete_content = ""

        for chunk_bytes in self.client.stream(endpoint=endpoint, params=params):
            chunk_str = chunk_bytes.decode("utf-8")

            for line in chunk_str.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    chunk_data: dict = json.loads(data_str)
                    chunks.append(chunk_data)

                    if chunk_data.get("candidates"):
                        for candidate in chunk_data["candidates"]:
                            if candidate.get("content"):
                                parts = candidate["content"].get("parts", [])
                                for part in parts:
                                    if part.get("text"):
                                        complete_content += part["text"]
                except json.JSONDecodeError:
                    pass

        if chunks:
            # Validate the last chunk's JSON structure
            result = ResponseValidator.validate_json(chunks[-1], GenerateContentResponse)
        else:
            result = ResponseValidator.validate_json({"candidates": []}, GenerateContentResponse)
            result = result.__class__(
                is_valid=False,
                error_message="No chunks received",
                missing_fields=[],
                expected_fields=["candidates"],
            )

        status_code = 200 if chunks else 500

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body={
                "chunks_count": len(chunks),
                "content_length": len(complete_content),
            },
            error=result.error_message if (result.error_message or not result.is_valid) else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        # 失败时记录不支持的参数
        if unsupported_param and (not chunks or not result.is_valid):
            self.collector.add_unsupported_param(
                param_name=str(unsupported_param["name"]),
                param_value=unsupported_param["value"],
                test_name=test_name,
                reason=result.error_message or "Streaming validation failed",
            )

        return chunks, complete_content, result.is_valid

    # ========================================================================
    # 阶段 1: 基线测试
    # ========================================================================

    def test_streaming_baseline(self):
        """测试基本流式响应"""
        test_name = "test_streaming_baseline"
        params = self.BASE_PARAMS
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    # ========================================================================
    # 阶段 2: 基础参数测试
    # ========================================================================

    def test_streaming_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_streaming_temperature"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"temperature": 0.7},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_max_output_tokens(self):
        """测试 maxOutputTokens 参数"""
        test_name = "test_streaming_max_output_tokens"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"maxOutputTokens": 100},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_top_p(self):
        """测试 topP 参数"""
        test_name = "test_streaming_top_p"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"topP": 0.9},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_top_k(self):
        """测试 topK 参数"""
        test_name = "test_streaming_top_k"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"topK": 40},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_candidate_count(self):
        """测试 candidateCount 参数（生成多个候选响应）"""
        test_name = "test_streaming_candidate_count"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"candidateCount": 2},
        }
        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            unsupported_param={"name": "generationConfig.candidateCount", "value": 2},
        )
        if not chunks:
            self.collector.add_unsupported_param(
                param_name="generationConfig.candidateCount",
                param_value=2,
                test_name=test_name,
                reason="No chunks received",
            )
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_stop_sequences(self):
        """测试 stopSequences 参数"""
        test_name = "test_streaming_stop_sequences"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"stopSequences": ["END", "STOP"]},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    # ========================================================================
    # 阶段 3: 响应格式测试
    # ========================================================================

    def test_streaming_response_format_json(self):
        """测试 JSON 响应格式"""
        test_name = "test_streaming_response_format_json"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"responseMimeType": "application/json"},
        }
        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            unsupported_param={
                "name": "generationConfig.responseMimeType",
                "value": "application/json",
            },
        )
        assert len(chunks) > 0
        assert result.is_valid

    def test_streaming_response_schema(self):
        """测试带 schema 的 JSON 响应格式"""
        test_name = "test_streaming_response_schema"
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
        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            unsupported_param={"name": "generationConfig.responseSchema", "value": "json_schema"},
        )
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 4: 安全设置测试
    # ========================================================================

    def test_streaming_safety_settings(self):
        """测试 safetySettings 参数"""
        test_name = "test_streaming_safety_settings"
        params = {
            **self.BASE_PARAMS,
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                }
            ],
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    @pytest.mark.parametrize(
        "threshold",
        [
            "BLOCK_NONE",
            "BLOCK_ONLY_HIGH",
            "BLOCK_MEDIUM_AND_ABOVE",
            "BLOCK_LOW_AND_ABOVE",
        ],
    )
    def test_streaming_safety_threshold_variants(self, threshold):
        """测试不同的安全阈值变体"""
        test_name = f"test_streaming_safety_threshold_variants[{threshold}]"
        params = {
            **self.BASE_PARAMS,
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": threshold,
                }
            ],
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 5: 系统指令测试
    # ========================================================================

    def test_streaming_system_instruction(self):
        """测试 systemInstruction 参数"""
        test_name = "test_streaming_system_instruction"
        params = {
            **self.BASE_PARAMS,
            "systemInstruction": {
                "parts": [{"text": "You are a helpful and friendly assistant."}]
            },
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 6: 工具调用测试
    # ========================================================================

    def test_streaming_function_calling(self):
        """测试函数调用功能"""
        test_name = "test_streaming_function_calling"
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
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    def test_streaming_code_execution(self):
        """测试代码执行功能"""
        test_name = "test_streaming_code_execution"
        params = {
            "contents": [{"parts": [{"text": "What is the sum of the first 50 prime numbers?"}]}],
            "tools": [{"codeExecution": {}}],
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 7: 生成控制进阶参数
    # ========================================================================

    def test_streaming_presence_penalty(self):
        """测试 presencePenalty 参数（对已出现token的惩罚）"""
        test_name = "test_streaming_presence_penalty"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"presencePenalty": 0.5},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    def test_streaming_frequency_penalty(self):
        """测试 frequencyPenalty 参数（基于频率的token惩罚）"""
        test_name = "test_streaming_frequency_penalty"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"frequencyPenalty": 0.5},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    def test_streaming_seed(self):
        """测试 seed 参数（确保生成结果可重复）"""
        test_name = "test_streaming_seed"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"seed": 42},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 8: 概率信息参数
    # ========================================================================

    def test_streaming_response_logprobs(self):
        """测试 responseLogprobs 参数（返回token的对数概率）"""
        test_name = "test_streaming_response_logprobs"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"responseLogprobs": True},
        }
        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            unsupported_param={"name": "generationConfig.responseLogprobs", "value": True},
        )
        assert len(chunks) > 0
        assert result.is_valid

    def test_streaming_logprobs(self):
        """测试 logprobs 参数（与 responseLogprobs 配合使用）"""
        test_name = "test_streaming_logprobs"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {
                "responseLogprobs": True,
                "logprobs": 3,
            },
        }
        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            unsupported_param={"name": "generationConfig.logprobs", "value": 3},
        )
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 9: 特定场景参数
    # ========================================================================

    def test_streaming_audio_timestamp(self):
        """测试 audioTimestamp 参数（音频内容时间戳）"""
        test_name = "test_streaming_audio_timestamp"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"audioTimestamp": True},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid

    @pytest.mark.parametrize(
        "resolution",
        [
            "media_resolution_low",
            "media_resolution_medium",
            "media_resolution_high",
            "media_resolution_ultra_high",
        ],
    )
    def test_streaming_media_resolution(self, resolution):
        """测试 mediaResolution 参数（控制图片/视频处理质量）"""
        test_name = f"test_streaming_media_resolution[{resolution}]"

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

        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            unsupported_param={"name": "generationConfig.mediaResolution", "value": resolution},
        )
        assert len(chunks) > 0
        assert result.is_valid

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
    def test_streaming_response_modalities(self, modalities):
        """测试 responseModalities 参数（控制响应模态类型）"""
        test_name = f"test_streaming_response_modalities[{','.join(modalities)}]"

        endpoint = self.ENDPOINT_FLASH  

        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"responseModalities": modalities},
        }

        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            endpoint=endpoint,
            unsupported_param={"name": "generationConfig.responseModalities", "value": modalities},
        )
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 11: 语音配置（使用 TTS 模型）
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
    def test_streaming_speech_config(self, voice_name):
        """测试 speechConfig.voiceConfig 参数（语音输出配置）"""
        test_name = f"test_streaming_speech_config[{voice_name}]"

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

        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            endpoint=endpoint,
            unsupported_param={
                "name": "generationConfig.speechConfig.voiceConfig",
                "value": voice_name,
            },
        )

        if not chunks:
            self.collector.add_unsupported_param(
                param_name="generationConfig.speechConfig.voiceConfig",
                param_value=voice_name,
                test_name=test_name,
                reason="No chunks received",
            )

        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 12: 思考配置（Gemini 3）
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
    def test_streaming_thinking_config(self, thinking_level):
        """测试 thinkingConfig.thinkingLevel 参数（Gemini 3思考深度）"""
        test_name = f"test_streaming_thinking_config[{thinking_level}]"

        # Gemini 3 Flash 支持所有 4 个级别
        endpoint = self.ENDPOINT_FLASH

        params = {
            **self.BASE_PARAMS,
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingLevel": thinking_level
                }
            },
        }

        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            endpoint=endpoint,
            unsupported_param={
                "name": "generationConfig.thinkingConfig.thinkingLevel",
                "value": thinking_level,
            },
        )
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 13: 图像配置
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
    def test_streaming_image_config_aspect_ratio(self, aspect_ratio):
        """测试 imageConfig.aspectRatio 参数（图像生成宽高比）"""
        test_name = f"test_streaming_image_config_aspect_ratio[{aspect_ratio}]"

        endpoint = self.ENDPOINT_FLASH

        params = {
            "contents": [{"parts": [{"text": "Generate an image of a sunset"}]}],
            "generationConfig": {
                "imageConfig": {
                    "aspectRatio": aspect_ratio
                }
            },
        }

        chunks, _, is_valid = self._run_streaming_test(test_name, params, endpoint=endpoint)
        assert len(chunks) > 0
        assert result.is_valid

    @pytest.mark.parametrize(
        "image_size",
        [
            "1K",
            "2K",
            "4K",
        ],
    )
    def test_streaming_image_config_size(self, image_size):
        """测试 imageConfig.imageSize 参数（图像生成尺寸）"""
        test_name = f"test_streaming_image_config_size[{image_size}]"

        endpoint = self.ENDPOINT_FLASH

        params = {
            "contents": [{"parts": [{"text": "Generate an image of mountains"}]}],
            "generationConfig": {
                "imageConfig": {
                    "imageSize": image_size
                }
            },
        }

        chunks, _, is_valid = self._run_streaming_test(test_name, params, endpoint=endpoint)
        assert len(chunks) > 0
        assert result.is_valid

    # ========================================================================
    # 阶段 14: 增强功能参数
    # ========================================================================

    def test_streaming_enable_enhanced_civic_answers(self):
        """测试 enableEnhancedCivicAnswers 参数（增强公民问答）"""
        test_name = "test_streaming_enable_enhanced_civic_answers"
        params = {
            "contents": [{"parts": [{"text": "Who is the current president of the United States?"}]}],
            "generationConfig": {"enableEnhancedCivicAnswers": True},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert result.is_valid
