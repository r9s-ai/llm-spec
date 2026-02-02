"""Google Gemini StreamGenerateContent API 测试

测试 Gemini 的流式内容生成功能。
StreamGenerateContent 支持所有 GenerateContent 的功能，但以 SSE 流式方式返回。
"""

import json
from base64 import b64encode
from pathlib import Path

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

    # Gemini 3 Flash Preview - 主要文本生成模型
    # 支持: 基础参数, thinkingConfig (4级别), mediaResolution, 工具调用
    ENDPOINT_FLASH = "/v1beta/models/gemini-3-flash-preview:streamGenerateContent"

    # Gemini 2.5 Flash TTS - 语音生成模型
    # 支持: speechConfig, voiceConfig (单/多说话人), responseModalities[AUDIO]
    ENDPOINT_TTS = "/v1beta/models/gemini-2.5-flash-preview-tts:streamGenerateContent"

    # Gemini 2.5 Flash Image - 基础图像生成模型
    # 支持: imageConfig.aspectRatio (10种比例), responseModalities[IMAGE]
    ENDPOINT_IMAGE = "/v1beta/models/gemini-2.5-flash-image:streamGenerateContent"

    # Gemini 3 Pro Image Preview - 高级图像生成模型
    # 支持: imageConfig (aspectRatio + imageSize: 1K/2K/4K)
    ENDPOINT_IMAGE_PRO = "/v1beta/models/gemini-3-pro-image-preview:streamGenerateContent"

    # 默认使用 Gemini 3 Flash
    ENDPOINT = ENDPOINT_FLASH

    # 基线参数
    BASE_PARAMS = {
        "contents": [{"parts": [{"text": "Say hello"}]}],
    }

    # 测试用音频文件路径
    AUDIO_EN = "test_assets/audio/hello_en.mp3"
    AUDIO_ZH = "test_assets/audio/hello_zh.mp3"

    @staticmethod
    def _load_audio_base64(file_path: str) -> str:
        """加载音频文件并转换为 base64 编码"""
        audio_path = Path(file_path)
        with audio_path.open("rb") as f:
            return b64encode(f.read()).decode("utf-8")

    @pytest.fixture(scope="class", autouse=True)
    def setup_collector(self, request: pytest.FixtureRequest, gemini_client: GeminiAdapter):
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

        # Some gateways return true SSE ("data: {...}\n\n"), while others return plain JSON
        # objects per chunk (no "data:" prefix). Support both.
        buffer = ""

        def _consume_chunk_obj(chunk_data: dict) -> None:
            nonlocal complete_content
            chunks.append(chunk_data)
            if chunk_data.get("candidates"):
                for candidate in chunk_data["candidates"]:
                    if candidate.get("content"):
                        parts = candidate["content"].get("parts", [])
                        for part in parts:
                            if part.get("text"):
                                complete_content += part["text"]

        for chunk_bytes in self.client.stream(endpoint=endpoint, params=params):
            chunk_str = chunk_bytes.decode("utf-8")
            buffer += chunk_str

            # Fast path: if the accumulated buffer looks like a full JSON object and does not contain SSE markers,
            # try to parse it as plain JSON chunk.
            if "data:" not in buffer:
                candidate = buffer.strip()
                # Heuristic: must start/end like a JSON object
                if candidate.startswith("{") and candidate.endswith("}"):
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            _consume_chunk_obj(obj)
                            buffer = ""
                            continue
                    except json.JSONDecodeError:
                        # not complete yet
                        pass

            # SSE path: split by event boundary (blank line)
            events = buffer.split("\n\n")
            buffer = events.pop()  # keep last partial

            for event in events:
                data_lines: list[str] = []
                for line in event.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())

                if not data_lines:
                    continue

                data_str = "\n".join(data_lines)
                if data_str == "[DONE]":
                    buffer = ""
                    break

                try:
                    chunk_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if isinstance(chunk_data, dict):
                    _consume_chunk_obj(chunk_data)

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
            # generationConfig.* 这类新增参数，额外标记 generationConfig 本体，保持报告一致性
            name = str(unsupported_param.get("name", ""))
            if name.startswith("generationConfig."):
                self.collector.add_unsupported_param(
                    param_name="generationConfig",
                    param_value="object",
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
        assert is_valid

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
        assert is_valid

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
        assert is_valid

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
        assert is_valid

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
        assert is_valid

    def test_streaming_code_execution(self):
        """测试代码执行功能"""
        test_name = "test_streaming_code_execution"
        params = {
            "contents": [{"parts": [{"text": "What is the sum of the first 50 prime numbers?"}]}],
            "tools": [{"codeExecution": {}}],
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

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
        assert is_valid

    def test_streaming_frequency_penalty(self):
        """测试 frequencyPenalty 参数（基于频率的token惩罚）"""
        test_name = "test_streaming_frequency_penalty"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"frequencyPenalty": 0.5},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_seed(self):
        """测试 seed 参数（确保生成结果可重复）"""
        test_name = "test_streaming_seed"
        params = {
            **self.BASE_PARAMS,
            "generationConfig": {"seed": 42},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
        assert is_valid

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
        assert is_valid

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
        assert is_valid

    # ========================================================================
    # 阶段 9: 特定场景参数
    # ========================================================================

    def test_streaming_audio_timestamp(self):
        """测试 audioTimestamp 参数（音频内容时间戳）"""
        test_name = "test_streaming_audio_timestamp"

        # 加载音频文件为 base64
        audio_base64 = self._load_audio_base64(self.AUDIO_EN)

        params = {
            "contents": [
                {
                    "parts": [
                        {"text": "Transcribe this audio with timestamps"},
                        {
                            "inlineData": {
                                "mimeType": "audio/mpeg",
                                "data": audio_base64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"audioTimestamp": True},
        }
        chunks, _, is_valid = self._run_streaming_test(test_name, params)
        assert len(chunks) > 0
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
        assert is_valid

    # ========================================================================
    # 阶段 10: 响应模态控制
    # ========================================================================

    def test_streaming_response_modalities_text(self):
        """测试 responseModalities 参数 - TEXT 模态"""
        test_name = "test_streaming_response_modalities_text"
        modalities = ["TEXT"]

        endpoint = self.ENDPOINT_FLASH  # TEXT 使用普通模型

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
        assert is_valid

    def test_streaming_response_modalities_image(self):
        """测试 responseModalities 参数 - IMAGE 模态"""
        test_name = "test_streaming_response_modalities_image"
        modalities = ["IMAGE"]

        endpoint = self.ENDPOINT_IMAGE  # IMAGE 使用图像生成模型

        params = {
            "contents": [{"parts": [{"text": "Generate a beautiful landscape"}]}],
            "generationConfig": {"responseModalities": modalities},
        }

        chunks, _, is_valid = self._run_streaming_test(
            test_name,
            params,
            endpoint=endpoint,
            unsupported_param={"name": "generationConfig.responseModalities", "value": modalities},
        )
        assert len(chunks) > 0
        assert is_valid

    def test_streaming_response_modalities_audio(self):
        """测试 responseModalities 参数 - AUDIO 模态"""
        test_name = "test_streaming_response_modalities_audio"
        modalities = ["AUDIO"]

        endpoint = self.ENDPOINT_TTS  # AUDIO 使用语音生成模型

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
        assert is_valid

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

        endpoint = self.ENDPOINT_TTS  # 使用 TTS 模型

        params = {
            **self.BASE_PARAMS,
            "generationConfig": {
                "responseModalities": ["AUDIO"],  # TTS 必需设置 AUDIO 模态
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
        assert is_valid

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
        assert is_valid

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

        endpoint = self.ENDPOINT_IMAGE  # 使用基础图像生成模型

        params = {
            "contents": [{"parts": [{"text": "Generate an image of a sunset"}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],  # 图像生成必需
                "imageConfig": {
                    "aspectRatio": aspect_ratio
                }
            },
        }

        chunks, _, is_valid = self._run_streaming_test(test_name, params, endpoint=endpoint)
        assert len(chunks) > 0
        assert is_valid

    @pytest.mark.skip(reason="暂时跳过 Pro 图像生成模型测试")
    @pytest.mark.parametrize(
        "image_size",
        [
            "1K",
            "2K",
            "4K",
        ],
    )
    def test_streaming_image_config_size(self, image_size):
        """测试 imageConfig.imageSize 参数（图像生成尺寸，Pro 专属）"""
        test_name = f"test_streaming_image_config_size[{image_size}]"

        endpoint = self.ENDPOINT_IMAGE_PRO  # 使用 Pro 图像生成模型（支持 imageSize）

        params = {
            "contents": [{"parts": [{"text": "Generate an image of mountains"}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],  # 图像生成必需
                "imageConfig": {
                    "imageSize": image_size
                }
            },
        }

        chunks, _, is_valid = self._run_streaming_test(test_name, params, endpoint=endpoint)
        assert len(chunks) > 0
        assert is_valid

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
        assert is_valid
