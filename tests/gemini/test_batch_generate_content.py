"""Google Gemini Batch Generate Content API 测试 - 仅创建端点"""

import pytest

from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.gemini import BatchCreateResponse
from llm_spec.validation.validator import ResponseValidator


from llm_spec.providers.gemini import GeminiAdapter

class TestBatchGenerateContent:
    """Batch Generate Content API 测试类"""

    client: GeminiAdapter

    collector: ReportCollector

    # ========================================================================
    # Endpoint 配置 - 仅创建端点
    # ========================================================================

    # 创建批任务端点
    ENDPOINT = "/v1beta/models/gemini-3-flash-preview:batchGenerateContent"

    # 基线参数：最小批请求（单个请求）
    BASE_PARAMS = {
        "requests": [
            {
                "contents": [{"parts": [{"text": "Hello"}]}],
            }
        ]
    }

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
    # 测试用例
    # ========================================================================

    def test_batch_baseline(self):
        """测试基线：单个请求的最小批"""
        test_name = "test_batch_baseline"

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        # baseline 失败也需要记录：把必需参数标为不支持（无对照基线可用）
        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests",
                param_value="array",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert result.is_valid, f"响应验证失败: {result.error_message}"
        assert isinstance(response_body, dict), "Expected JSON response"
        assert response_body.get("name"), "批任务名称缺失"
        assert response_body.get("state"), "批任务状态缺失"

    def test_batch_multiple_requests(self):
        """测试多个请求的批"""
        test_name = "test_batch_multiple_requests"
        params = {
            "requests": [
                {"contents": [{"parts": [{"text": "Hello"}]}]},
                {"contents": [{"parts": [{"text": "How are you?"}]}]},
                {"contents": [{"parts": [{"text": "Tell me a joke"}]}]},
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_display_name(self):
        """测试 config.displayName 参数"""
        test_name = "test_batch_with_display_name"
        params = {
            "requests": [{"contents": [{"parts": [{"text": "Hello"}]}]}],
            "config": {"displayName": "test-batch-001"},
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="config.displayName",
                param_value="test-batch-001",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )
            self.collector.add_unsupported_param(
                param_name="config",
                param_value="object",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_generation_config(self):
        """测试 generationConfig 参数（temperature、maxOutputTokens）"""
        test_name = "test_batch_with_generation_config"
        params = {
            "requests": [
                {
                    "contents": [{"parts": [{"text": "Hello"}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 100},
                }
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests[0].generationConfig",
                param_value="temperature+maxOutputTokens",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_safety_settings(self):
        """测试 safetySettings 参数"""
        test_name = "test_batch_with_safety_settings"
        params = {
            "requests": [
                {
                    "contents": [{"parts": [{"text": "Hello"}]}],
                    "safetySettings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                        }
                    ],
                }
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests[0].safetySettings",
                param_value="harassment_medium",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_system_instruction(self):
        """测试 systemInstruction 参数"""
        test_name = "test_batch_with_system_instruction"
        params = {
            "requests": [
                {
                    "contents": [{"parts": [{"text": "Hello"}]}],
                    "systemInstruction": {
                        "parts": [{"text": "You are a helpful assistant."}]
                    },
                }
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests[0].systemInstruction",
                param_value="system_prompt",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_text_content(self):
        """测试纯文本内容的批请求"""
        test_name = "test_batch_with_text_content"
        params = {
            "requests": [
                {
                    "contents": [
                        {"parts": [{"text": "What is the capital of France?"}]}
                    ]
                },
                {
                    "contents": [
                        {"parts": [{"text": "What is the capital of Japan?"}]}
                    ]
                },
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_inline_image(self):
        """测试包含内联图像的批请求"""
        test_name = "test_batch_with_inline_image"
        # 1x1 透明 PNG (base64)
        sample_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        params = {
            "requests": [
                {
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
                    ]
                }
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests[0].contents[0].parts[].inlineData",
                param_value="image",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_function_calling(self):
        """测试包含函数调用的批请求"""
        test_name = "test_batch_with_function_calling"
        params = {
            "requests": [
                {
                    "contents": [{"parts": [{"text": "What's the weather in Tokyo?"}]}],
                    "tools": [
                        {
                            "functionDeclarations": [
                                {
                                    "name": "get_weather",
                                    "description": "Get the current weather",
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
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests[0].tools",
                param_value="function_calling",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_with_json_response_format(self):
        """测试 JSON 响应格式的批请求"""
        test_name = "test_batch_with_json_response_format"
        params = {
            "requests": [
                {
                    "contents": [{"parts": [{"text": "List 3 colors"}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                }
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests[0].generationConfig.responseMimeType",
                param_value="application/json",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    @pytest.mark.parametrize(
        "request_count",
        [1, 3, 5, 10],
    )
    def test_batch_size_variants(self, request_count):
        """测试不同大小的批（请求数量变体）"""
        test_name = f"test_batch_size_variants[{request_count}]"

        requests = [
            {"contents": [{"parts": [{"text": f"Request {i}"}]}]}
            for i in range(request_count)
        ]
        params = {"requests": requests}

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="requests",
                param_value=f"{request_count}_requests",
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_mixed_parameters(self):
        """测试混合不同参数的批请求"""
        test_name = "test_batch_mixed_parameters"
        params = {
            "requests": [
                {
                    "contents": [{"parts": [{"text": "Hello"}]}],
                    "generationConfig": {"temperature": 0.5},
                },
                {
                    "contents": [{"parts": [{"text": "Hi"}]}],
                    "generationConfig": {"temperature": 0.9},
                },
                {
                    "contents": [{"parts": [{"text": "Hey"}]}],
                    "generationConfig": {"maxOutputTokens": 50},
                },
            ]
        }

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        result = ResponseValidator.validate_response(response, BatchCreateResponse)

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=result.error_message if not result.is_valid else None,
            missing_fields=result.missing_fields,
            expected_fields=result.expected_fields,
        )

        assert 200 <= status_code < 300
        assert result.is_valid

    def test_batch_response_required_fields(self):
        """验证批创建响应的必需字段"""
        test_name = "test_batch_response_required_fields"

        response = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        status_code = response.status_code
        response_body = self.collector.response_body_from_httpx(response)

        assert 200 <= status_code < 300

        # 验证必需字段
        required_fields = ["name", "state", "createTime", "updateTime"]
        for field in required_fields:
            assert (
                field in response_body
            ), f"响应缺失必需字段: {field}"

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
        )
