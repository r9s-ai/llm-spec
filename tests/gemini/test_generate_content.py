"""Google Gemini Generate Content API 测试"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.gemini import GenerateContentResponse
from llm_spec.validation.validator import ResponseValidator


class TestGenerateContent:
    """Generate Content API 测试类"""

    ENDPOINT = "/v1beta/models/gemini-pro:generateContent"

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
    # 阶段 7: 流式响应测试
    # ========================================================================

    def test_streaming_basic(self):
        """测试基本流式响应"""
        import json

        test_name = "test_streaming_basic"
        # Gemini 流式 API: streamGenerateContent + ?alt=sse
        stream_endpoint = self.ENDPOINT.replace(
            ":generateContent", ":streamGenerateContent"
        )
        params = self.BASE_PARAMS

        chunks = []
        complete_content = ""
        raw_lines = []

        try:
            for chunk_bytes in self.client.stream(
                endpoint=stream_endpoint,
                params=params,
            ):
                # 解析 SSE 格式
                chunk_str = chunk_bytes.decode("utf-8")
                raw_lines.append(repr(chunk_str))

                # SSE 格式：每行可能是 "data: ..." 或空行
                for line in chunk_str.split("\n"):
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("data: "):
                        data_str = line[6:]  # 移除 "data: " 前缀
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            chunks.append(chunk_data)

                            # 验证每个 chunk（Gemini 使用相同的 GenerateContentResponse）
                            is_valid, error_msg, missing_fields, expected_fields = (
                                ResponseValidator.validate(
                                    chunk_data, GenerateContentResponse
                                )
                            )

                            # 累积内容
                            if chunk_data.get("candidates"):
                                for candidate in chunk_data["candidates"]:
                                    if candidate.get("content"):
                                        parts = candidate["content"].get("parts", [])
                                        for part in parts:
                                            if part.get("text"):
                                                complete_content += part["text"]
                        except json.JSONDecodeError as je:
                            print(f"JSON解析失败: {data_str[:100]}, 错误: {je}")

            # 调试输出
            print(f"\n收到 {len(raw_lines)} 个原始chunk")
            print(f"解析出 {len(chunks)} 个数据chunk")
            print(f"内容长度: {len(complete_content)}")
            if len(raw_lines) > 0:
                print(f"第一个chunk示例: {raw_lines[0][:200]}")

            # 记录测试结果
            self.collector.record_test(
                test_name=test_name,
                params=params,
                status_code=200,  # 流式响应成功连接
                response_body={"chunks_count": len(chunks), "content": complete_content},
                error=None,
                missing_fields=[],
                expected_fields=["candidates", "usageMetadata"],
            )

            assert len(chunks) > 0, f"应该接收到至少一个chunk，实际收到 {len(raw_lines)} 个原始chunk"
            assert len(complete_content) > 0, "应该有生成的内容"

        except Exception as e:
            print(f"\n异常信息: {type(e).__name__}: {str(e)}")
            print(f"收到的原始chunks数量: {len(raw_lines)}")
            if raw_lines:
                print(f"前3个chunks: {raw_lines[:3]}")

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

