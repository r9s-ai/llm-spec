"""Integration tests for OpenAI API validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_spec.providers.openai import OpenAIClient
from tests.base import assert_report_valid

# =============================================================================
# Chat Completions API Tests
# =============================================================================


@pytest.mark.integration
class TestChatCompletions:
    """Tests for /v1/chat/completions endpoint.

    Test Strategy: Single-parameter testing
    - Each test validates exactly one parameter on top of a baseline
    - Baseline: model, messages, max_tokens (minimum required)
    - Makes parameter coverage tracking clear and precise
    """

    # =========================================================================
    # Baseline Test
    # =========================================================================

    def test_baseline(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Baseline test with only required parameters.

        Tests: model, messages, max_tokens
        This is the foundation for all single-parameter tests.
        """
        report = openai_client.validate_chat_completion(**baseline_params)
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 1: Independent Parameters (Core)
    # =========================================================================

    def test_param_temperature(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test temperature parameter (controls randomness, 0-2).

        Higher values = more random, lower values = more deterministic.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            temperature=0.7,
        )
        report.output()
        assert_report_valid(report)

    def test_param_top_p(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test top_p parameter (nucleus sampling, 0-1).

        Alternative to temperature for controlling randomness.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            top_p=0.9,
        )
        report.output()
        assert_report_valid(report)

    def test_param_presence_penalty(
        self, openai_client: OpenAIClient, baseline_params: dict
    ) -> None:
        """Test presence_penalty parameter (-2.0 to 2.0).

        Positive values penalize tokens that have appeared, encouraging new topics.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            presence_penalty=0.5,
        )
        report.output()
        assert_report_valid(report)

    def test_param_frequency_penalty(
        self, openai_client: OpenAIClient, baseline_params: dict
    ) -> None:
        """Test frequency_penalty parameter (-2.0 to 2.0).

        Positive values penalize tokens based on frequency, reducing repetition.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            frequency_penalty=0.5,
        )
        report.output()
        assert_report_valid(report)

    def test_param_n(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test n parameter (number of completion choices).

        Validates that the API returns exactly n choices.
        """
        n_value = 2
        report = openai_client.validate_chat_completion(
            **baseline_params,
            n=n_value,
            _test_param="n",
            _test_variant="multiple choices",
        )
        report.output()
        assert_report_valid(report)

        # Additional validation: verify n choices returned
        if report.raw_response:
            choices = report.raw_response.get("choices", [])
            assert len(choices) == n_value, f"Expected {n_value} choices, got {len(choices)}"

    def test_param_max_completion_tokens(self, openai_client: OpenAIClient) -> None:
        """Test max_completion_tokens parameter (alternative to max_tokens).

        Note: Uses model+messages only, no max_tokens (mutually exclusive).
        """
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'test'."}],
            max_completion_tokens=50,
            _test_param="max_completion_tokens",
            _test_variant="standard",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 2: Advanced Parameters
    # =========================================================================

    def test_param_stop(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test stop parameter (stop sequence).

        API stops generating when it encounters any of the stop sequences.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            stop=[".", "!"],
            _test_param="stop",
            _test_variant="sequence list",
        )
        report.output()
        assert_report_valid(report)

    def test_param_response_format_json(self, openai_client: OpenAIClient) -> None:
        """Test response_format parameter (JSON mode).

        Forces the model to output valid JSON.
        Note: Requires system message to instruct JSON output.
        """
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You respond in JSON format."},
                {
                    "role": "user",
                    "content": "Return a JSON object with a 'status' field set to 'ok'.",
                },
            ],
            max_tokens=50,
            response_format={"type": "json_object"},
            _test_param="response_format",
            _test_variant="json_object",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 2: Logprobs Parameters (Dependent)
    # =========================================================================

    def test_param_logprobs(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test logprobs parameter (returns token probabilities).

        This is the baseline for top_logprobs parameter.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            logprobs=True,
        )
        report.output()
        assert_report_valid(report)

    def test_param_top_logprobs(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test top_logprobs parameter (number of top tokens to return).

        Depends on: logprobs=True
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            logprobs=True,  # dependency
            top_logprobs=2,
        )
        report.output()
        assert_report_valid(report)

    def test_param_logit_bias(self, openai_client: OpenAIClient, baseline_params: dict) -> None:
        """Test logit_bias parameter (modify token probabilities).

        Used to suppress or encourage specific tokens.
        """
        report = openai_client.validate_chat_completion(
            **baseline_params,
            logit_bias={"15496": -100},  # Suppress "Hello" token
            _test_param="logit_bias",
            _test_variant="standard",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 3: Message Role Parameters
    # =========================================================================

    def test_param_system_message(self, openai_client: OpenAIClient) -> None:
        """Test system role in messages.

        System messages set the assistant's behavior.
        """
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'test'."},
            ],
            max_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    def test_param_developer_message(self, openai_client: OpenAIClient) -> None:
        """Test developer role in messages.

        Developer messages are similar to system messages.
        """
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'test'."},
            ],
            max_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    def test_param_multi_turn_conversation(self, openai_client: OpenAIClient) -> None:
        """Test multi-turn conversation in messages.

        Tests alternating user/assistant messages.
        """
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice!"},
                {"role": "user", "content": "What's my name?"},
            ],
            max_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 4: Advanced Features (Tools, Vision, Streaming)
    # =========================================================================

    def test_param_tools(self, openai_client: OpenAIClient) -> None:
        """Test tools parameter (function calling baseline).

        This is the baseline for tool_choice and parallel_tool_calls.
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                        },
                        "required": ["location"],
                    },
                },
            },
        ]
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "What's the weather in Boston?"}],
            max_tokens=150,
            tools=tools,
            _test_param="tools",
            _test_variant="function calling",
        )
        report.output()
        assert_report_valid(report)

    def test_param_tool_choice(self, openai_client: OpenAIClient) -> None:
        """Test tool_choice parameter (control function calling).

        Depends on: tools parameter
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                        },
                        "required": ["location"],
                    },
                },
            },
        ]
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "What's the weather in Boston?"}],
            max_tokens=150,
            tools=tools,  # dependency
            tool_choice="auto",
            _test_param="tool_choice",
            _test_variant="auto",
        )
        report.output()
        assert_report_valid(report)

    def test_param_parallel_tool_calls(self, openai_client: OpenAIClient) -> None:
        """Test parallel_tool_calls parameter (multiple tools in one response).

        Depends on: tools parameter (with multiple tools)
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                            },
                        },
                        "required": ["location"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current time in a given timezone",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {
                                "type": "string",
                                "description": "The timezone, e.g. America/New_York",
                            },
                        },
                        "required": ["timezone"],
                    },
                },
            },
        ]
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "What's the weather and current time in Boston?"}
            ],
            max_tokens=150,
            tools=tools,  # dependency
            tool_choice="auto",
            parallel_tool_calls=True,
            _test_param="parallel_tool_calls",
            _test_variant="true",
        )
        report.output()
        assert_report_valid(report)

    def test_param_vision(self, openai_client: OpenAIClient) -> None:
        """Test vision capability (image_url in messages).

        Tests multimodal input with images.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What is in this image?",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://img95.699pic.com/photo/60018/8119.jpg_wh860.jpg"
                        },
                    },
                ],
            }
        ]
        report = openai_client.validate_chat_completion(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            _test_param="messages",
            _test_variant="vision input",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 5: Streaming Parameters
    # =========================================================================

    def test_param_stream(self, openai_client: OpenAIClient) -> None:
        """Test stream parameter (streaming responses).

        This is the baseline for stream_options parameter.
        Uses different schema: ChatCompletionStreamResponse
        """
        messages = [
            {"role": "user", "content": "Say hello."},
        ]

        chunks, report = openai_client.validate_chat_completion_stream(
            model="gpt-4o-mini",
            messages=messages,
        )

        report.output()

        # Verify we got chunks
        assert len(chunks) > 0, "Should receive at least one chunk"

        # Verify first chunk structure
        first_chunk = chunks[0]
        assert first_chunk.get("object") == "chat.completion.chunk"

        # Find chunk with finish_reason
        finish_chunk = next(
            (
                c
                for c in chunks
                if c.get("choices") and c["choices"][0].get("finish_reason") == "stop"
            ),
            None,
        )
        assert finish_chunk is not None, "Should have a chunk with finish_reason='stop'"

        assert report.success, "Streaming should complete successfully"

    def test_param_stream_options(self, openai_client: OpenAIClient) -> None:
        """Test stream_options parameter (include usage in stream).

        Depends on: stream=True
        """
        messages = [
            {"role": "developer", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello."},
        ]

        chunks, report = openai_client.validate_chat_completion_stream(
            model="gpt-4o-mini",
            messages=messages,
            stream_options={"include_usage": True},  # dependency: stream=True
        )

        report.output()

        print(f"\nReceived {len(chunks)} chunks")

        # Verify we got chunks
        assert len(chunks) > 0, "Should receive at least one chunk"

        # Verify all chunks have consistent id
        chunk_ids = {c.get("id") for c in chunks}
        assert len(chunk_ids) == 1, "All chunks should have same id"

        # Find the usage chunk (should have usage field when stream_options.include_usage=true)
        usage_chunk = next(
            (c for c in chunks if c.get("usage") is not None),
            None,
        )
        assert usage_chunk is not None, (
            "Should have a chunk with usage when stream_options.include_usage=true"
        )

        # Verify usage structure
        usage = usage_chunk["usage"]
        assert "prompt_tokens" in usage, "Usage should have prompt_tokens"
        assert "completion_tokens" in usage, "Usage should have completion_tokens"
        assert "total_tokens" in usage, "Usage should have total_tokens"

        assert report.success, "Streaming should complete successfully"


# =============================================================================
# Responses API Tests
# =============================================================================


@pytest.mark.integration
class TestResponses:
    """Tests for /v1/responses endpoint.

    Test Strategy: Single-parameter testing
    - Each test validates exactly one parameter on top of a baseline
    - Baseline: model, input_text, max_output_tokens
    """

    # =========================================================================
    # Baseline Test
    # =========================================================================

    def test_baseline(self, openai_client: OpenAIClient, baseline_responses_params: dict) -> None:
        """Baseline test with only required parameters.

        Tests: model, input (text), max_output_tokens
        """
        report = openai_client.validate_responses(**baseline_responses_params)
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 1: Independent Parameters (Core)
    # =========================================================================

    def test_param_temperature(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test temperature parameter (0-2)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            temperature=0.7,
        )
        report.output()
        assert_report_valid(report)

    def test_param_top_p(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test top_p parameter (0-1)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            top_p=0.9,
        )
        report.output()
        assert_report_valid(report)

    def test_param_top_logprobs(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test top_logprobs parameter (0-20)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            top_logprobs=2,
        )
        report.output()
        assert_report_valid(report)

    def test_param_store(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test store parameter (boolean)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            store=True,
        )
        report.output()
        assert_report_valid(report)

    def test_param_metadata(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test metadata parameter (map)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            metadata={"test_run": "true", "env": "dev"},
        )
        report.output()
        assert_report_valid(report)

    def test_param_truncation(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test truncation parameter (auto/disabled)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            truncation="auto",
        )
        report.output()
        assert_report_valid(report)

    def test_param_service_tier(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test service_tier parameter (auto/default/flex)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            service_tier="default",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 2: Input & Context
    # =========================================================================

    def test_param_instructions(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test instructions parameter (system message)."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            instructions="You are a helpful assistant.",
        )
        report.output()
        assert_report_valid(report)

    MAX_RETRIES = 3

    def test_param_input_list(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test input parameter as array of strings."""
        report = openai_client.validate_responses(
            **baseline_responses_params,
            input=["Hello", "World"],
            _test_param="input",
            _test_variant="string array",
        )
        report.output()
        assert_report_valid(report)

    def test_param_input_image(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test input parameter with image inputs."""
        input_items = [
            {"type": "input_text", "text": "What is in this image?"},
            {
                "type": "input_image",
                "image_url": "https://img95.699pic.com/photo/60021/9579.jpg_wh860.jpg",
            },
        ]
        report = openai_client.validate_responses(
            **baseline_responses_params,
            input=input_items,
            _test_param="input",
            _test_variant="image input",
        )
        report.output()
        assert_report_valid(report)

    def test_param_input_file(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test input parameter with file inputs."""
        input_items = [
            {"type": "input_text", "text": "What is in this file?"},
            {
                "type": "input_file",
                "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
            },
        ]
        report = openai_client.validate_responses(
            **baseline_responses_params,
            input=input_items,
            _test_param="input",
            _test_variant="file input",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 3: Tools
    # =========================================================================

    def test_param_tools(self, openai_client: OpenAIClient) -> None:
        """Test tools parameter (function calling)."""
        tools = [
            {
                "type": "function",
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]
        report = openai_client.validate_responses(
            model="gpt-4o-mini",
            input="What's the weather in Boston?",
            tools=tools,
            max_output_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    def test_param_tool_choice(self, openai_client: OpenAIClient) -> None:
        """Test tool_choice parameter."""
        tools = [
            {
                "type": "function",
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]
        report = openai_client.validate_responses(
            model="gpt-4o-mini",
            input="What's the weather in Boston?",
            tools=tools,
            tool_choice="required",
            max_output_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    def test_param_parallel_tool_calls(self, openai_client: OpenAIClient) -> None:
        """Test parallel_tool_calls parameter."""
        tools = [
            {
                "type": "function",
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]
        report = openai_client.validate_responses(
            model="gpt-4o-mini",
            input="What's the weather in Boston?",
            tools=tools,
            parallel_tool_calls=False,
            max_output_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 4: Response Configuration
    # =========================================================================

    def test_param_include(self, openai_client: OpenAIClient) -> None:
        """Test include parameter (e.g. logprobs with message)."""
        # Note: 'message.output_text.logprobs' is a valid include value
        report = openai_client.validate_responses(
            model="gpt-4o-mini",
            input="Say hi.",
            include=["message.output_text.logprobs"],
            max_output_tokens=50,
        )
        report.output()
        assert_report_valid(report)

    def test_param_text_json_schema(self, openai_client: OpenAIClient) -> None:
        """Test text parameter with JSON schema (Structured Outputs)."""
        report = openai_client.validate_responses(
            model="gpt-4o-mini",
            input="Generate a person.",
            text={
                "type": "json_schema",
                "json_schema": {
                    "name": "person",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                        "required": ["name", "age"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            max_output_tokens=150,
        )
        report.output()
        assert_report_valid(report)

    def test_param_reasoning(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test reasoning parameter (o-series models)."""
        # Exclude model from baseline since we need to override it
        params = {k: v for k, v in baseline_responses_params.items() if k != "model"}
        report = openai_client.validate_responses(
            **params,
            reasoning={"effort": "low"},
            model="o3-mini",
            _test_param="reasoning",
            _test_variant="o3-mini",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 5: Streaming
    # =========================================================================

    def test_param_stream(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test stream parameter."""
        events, report = openai_client.validate_responses_stream(
            **baseline_responses_params,
            _test_param="stream",
            _test_variant="true",
        )
        report.output()
        assert_report_valid(report)

    def test_param_stream_options(
        self, openai_client: OpenAIClient, baseline_responses_params: dict
    ) -> None:
        """Test stream_options parameter."""
        events, report = openai_client.validate_responses_stream(
            **baseline_responses_params,
            stream_options={"include_usage": True},
            _test_param="stream_options",
            _test_variant="include_usage",
        )
        report.output()
        assert_report_valid(report)

        # Verify usage in events
        has_usage = any(e.get("usage") for e in events)
        assert has_usage, "Should receive usage when stream_options.include_usage=True"


# =============================================================================
# Embeddings API Tests
# =============================================================================


@pytest.mark.integration
class TestEmbeddings:
    """Tests for /v1/embeddings endpoint.

    Test Strategy: Single-parameter testing
    - Each test validates exactly one parameter on top of a baseline
    - Baseline: model, input (minimum required)
    - Makes parameter coverage tracking clear and precise

    Official API Parameters (as of 2024):
    - input (required): string | array of strings | array of tokens | array of token arrays
    - model (required): string
    - dimensions (optional): integer
    - encoding_format (optional): "float" | "base64"
    - user (deprecated): unique identifier for end-user
    """

    # =========================================================================
    # Baseline Test
    # =========================================================================

    def test_baseline(self, openai_client: OpenAIClient, baseline_embedding_params: dict) -> None:
        """Baseline test with only required parameters.

        Tests: model, input (single string)
        This is the foundation for all single-parameter tests.
        """
        report = openai_client.validate_embeddings(**baseline_embedding_params)
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 1: Input Format Variations (Required Parameter)
    # =========================================================================

    def test_input_array_of_strings(
        self, openai_client: OpenAIClient, baseline_embedding_params: dict
    ) -> None:
        """Test input parameter with array of strings (batch embedding).

        Official docs: "To embed multiple inputs in a single request, pass an array of strings."
        Limit: Maximum 300,000 tokens summed across all inputs.
        """
        report = openai_client.validate_embeddings(
            model=baseline_embedding_params["model"],
            input_text=["Hello", "World", "Test"],  # Array of strings
            _test_param="input",
            _test_variant="array of strings",
        )
        report.output()
        assert_report_valid(report)

        # Additional validation: verify we got embeddings for each input
        if report.raw_response:
            data = report.raw_response.get("data", [])
            assert len(data) == 3, f"Expected 3 embeddings, got {len(data)}"

    # Note: array of tokens and array of token arrays testing would require tokenization
    # which is model-specific. Skipping for now as it's less common.

    # =========================================================================
    # Tier 2: Optional Parameters
    # =========================================================================

    def test_param_dimensions(
        self, openai_client: OpenAIClient, baseline_embedding_params: dict
    ) -> None:
        """Test dimensions parameter (output embedding dimensions).

        Official docs: "Only supported in text-embedding-3 and later models."
        Common values: 512, 1024, 1536 (model-dependent)
        """
        report = openai_client.validate_embeddings(
            **baseline_embedding_params,
            dimensions=512,
            _test_param="dimensions",
            _test_variant="custom value",
        )
        report.output()
        assert_report_valid(report)

        # Additional validation: verify embedding dimensions
        if report.raw_response:
            data = report.raw_response.get("data", [])
            if data and isinstance(data[0].get("embedding"), list):
                actual_dims = len(data[0]["embedding"])
                assert actual_dims == 512, f"Expected 512 dimensions, got {actual_dims}"

    def test_param_encoding_format_float(
        self, openai_client: OpenAIClient, baseline_embedding_params: dict
    ) -> None:
        """Test encoding_format parameter with 'float' (default).

        Official docs: "Can be either float or base64."
        Float format returns embedding as list[float].
        """
        report = openai_client.validate_embeddings(
            **baseline_embedding_params,
            encoding_format="float",
            _test_param="encoding_format",
            _test_variant="float",
        )
        report.output()
        assert_report_valid(report)

        # Additional validation: verify embedding is list of floats
        if report.raw_response:
            data = report.raw_response.get("data", [])
            if data:
                embedding = data[0].get("embedding")
                assert isinstance(embedding, list), f"Expected list, got {type(embedding)}"
                if embedding:
                    assert isinstance(embedding[0], (int, float)), (
                        f"Expected numeric values, got {type(embedding[0])}"
                    )

    def test_param_encoding_format_base64(
        self, openai_client: OpenAIClient, baseline_embedding_params: dict
    ) -> None:
        """Test encoding_format parameter with 'base64'.

        Official docs: "Can be either float or base64."
        Base64 format returns embedding as base64-encoded string (more compact).
        """
        report = openai_client.validate_embeddings(
            **baseline_embedding_params,
            encoding_format="base64",
            _test_param="encoding_format",
            _test_variant="base64",
        )
        report.output()
        assert_report_valid(report)

        # Additional validation: verify embedding is base64 string
        if report.raw_response:
            data = report.raw_response.get("data", [])
            if data:
                embedding = data[0].get("embedding")
                assert isinstance(embedding, str), (
                    f"Expected string (base64), got {type(embedding)}"
                )

    # =========================================================================
    # Tier 3: Model Variations
    # =========================================================================

    # def test_model_text_embedding_3_large(self, openai_client: OpenAIClient) -> None:
    #     """Test with text-embedding-3-large model.

    #     Official docs: "text-embedding-3-large" is the larger and more capable embedding model.
    #     Default dimensions: 3072
    #     """
    #     report = openai_client.validate_embeddings(
    #         model="text-embedding-3-large",
    #         input_text="Hello, world!",
    #     )
    #     report.output()
    #     assert_report_valid(report)

    # def test_model_text_embedding_ada_002(self, openai_client: OpenAIClient) -> None:
    #     """Test with text-embedding-ada-002 model (legacy).

    #     Official docs: "text-embedding-ada-002" is the previous generation model.
    #     Fixed dimensions: 1536 (does not support 'dimensions' parameter)
    #     """
    #     report = openai_client.validate_embeddings(
    #         model="text-embedding-ada-002",
    #         input_text="Hello, world!",
    #     )
    #     report.output()
    #     assert_report_valid(report)


# =============================================================================
# Audio API Tests
# =============================================================================


@pytest.mark.integration
class TestAudioSpeech:
    """Tests for /v1/audio/speech endpoint (TTS).

    Test Strategy: Single-parameter testing
    - Each test validates exactly one parameter on top of a baseline
    - Baseline: model, input, voice
    """

    # =========================================================================
    # Baseline Test
    # =========================================================================

    def test_baseline(self, openai_client: OpenAIClient, baseline_speech_params: dict) -> None:
        """Baseline test with only required parameters.

        Tests: model, input, voice
        """
        audio_data, report = openai_client.validate_speech(**baseline_speech_params)
        report.output()
        assert report.success, "Should return valid audio data"
        assert len(audio_data) > 0, "Audio data should not be empty"

    # =========================================================================
    # Tier 1: Core Parameters
    # =========================================================================

    @pytest.mark.parametrize(
        "voice",
        [
            "ash",
            "ballad",
            "coral",
            "echo",
            "fable",
            "onyx",
            "nova",
            "sage",
            "shimmer",
            "verse",
            "marin",
            "cedar",
        ],
    )
    def test_param_voice(
        self, openai_client: OpenAIClient, baseline_speech_params: dict, voice: str
    ) -> None:
        """Test TTS with various supported voices."""
        params = {**baseline_speech_params, "voice": voice}
        audio_data, report = openai_client.validate_speech(
            **params,
            _test_param="voice",
            _test_variant=voice,
        )
        report.output()
        assert report.success, f"Voice '{voice}' should return valid audio"

    @pytest.mark.parametrize("model", ["gpt-4o-mini-tts"])
    def test_param_model(
        self, openai_client: OpenAIClient, baseline_speech_params: dict, model: str
    ) -> None:
        """Test TTS with various models."""
        params = {**baseline_speech_params, "model": model}
        audio_data, report = openai_client.validate_speech(
            **params,
            _test_param="model",
            _test_variant=model,
        )
        report.output()
        assert report.success, f"Model '{model}' should return valid audio"

    # =========================================================================
    # Tier 2: Output Options
    # =========================================================================

    @pytest.mark.parametrize("fmt", ["mp3", "opus", "aac", "flac", "wav", "pcm"])
    def test_param_response_format(
        self, openai_client: OpenAIClient, baseline_speech_params: dict, fmt: str
    ) -> None:
        """Test various audio output formats."""
        audio_data, report = openai_client.validate_speech(
            **baseline_speech_params,
            response_format=fmt,
            _test_param="response_format",
            _test_variant=fmt,
        )
        report.output()
        assert report.success, f"Format '{fmt}' should return valid audio"

    @pytest.mark.parametrize("stream_fmt", ["sse", "audio"])
    def test_param_stream_format(
        self, openai_client: OpenAIClient, baseline_speech_params: dict, stream_fmt: str
    ) -> None:
        """Test various stream formats."""
        audio_data, report = openai_client.validate_speech(
            **baseline_speech_params,
            stream_format=stream_fmt,
            _test_param="stream_format",
            _test_variant=stream_fmt,
        )
        report.output()
        assert report.success, f"Stream format '{stream_fmt}' should return valid audio"

    def test_param_speed(self, openai_client: OpenAIClient, baseline_speech_params: dict) -> None:
        """Test speed parameter (0.25 to 4.0)."""
        audio_data, report = openai_client.validate_speech(
            **baseline_speech_params,
            speed=1.5,
            _test_param="speed",
            _test_variant="1.5x",
        )
        report.output()
        assert report.success, "Speed 1.5 should return valid audio"

    # =========================================================================
    # Tier 3: Advanced Options
    # =========================================================================

    def test_param_instructions(
        self, openai_client: OpenAIClient, baseline_speech_params: dict
    ) -> None:
        """Test instructions parameter (voice style control).

        Requires gpt-4o-mini-tts or gpt-4o-audio-preview (if supported in tts).
        Official docs say: "Does not work with tts-1 or tts-1-hd".
        """
        audio_data, report = openai_client.validate_speech(
            input_text="Hello, I am excited!",
            model="gpt-4o-mini-tts",
            voice="alloy",
            instructions="Whisper your response.",
            _test_param="instructions",
            _test_variant="whisper",
        )
        report.output()
        assert report.success, "Instructions should work with gpt-4o-mini-tts"


@pytest.mark.integration
class TestAudioTranscriptions:
    """Tests for /v1/audio/transcriptions endpoint.

    Test Strategy: Single-parameter testing
    - Baseline: file (generated), model='whisper-1'
    """

    def test_baseline(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Baseline test for transcriptions."""
        report = openai_client.validate_transcription(file_path=audio_file_en, model="whisper-1")
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize(
        "model",
        [
            "whisper-1",
            "gpt-4o-transcribe",
        ],
    )
    def test_param_model(
        self, openai_client: OpenAIClient, audio_file_en: Path, model: str
    ) -> None:
        """Test various transcription models."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model=model,
            _test_param="model",
            _test_variant=model,
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("fmt", ["json", "verbose_json", "text", "srt", "vtt"])
    def test_param_response_format(
        self, openai_client: OpenAIClient, audio_file_en: Path, fmt: str
    ) -> None:
        """Test various response formats."""
        # Note: gpt-4o models only support json
        model = "whisper-1"
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model=model,
            response_format=fmt,
            _test_param="response_format",
            _test_variant=fmt,
        )
        report.output()
        assert_report_valid(report)

    def test_param_chunking_strategy(
        self, openai_client: OpenAIClient, audio_file_en: Path
    ) -> None:
        """Test chunking_strategy parameter."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model="gpt-4o-transcribe",
            chunking_strategy="auto",
            _test_param="chunking_strategy",
            _test_variant="auto",
        )
        report.output()
        assert_report_valid(report)

    def test_param_include_logprobs(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Test include=['logprobs'] parameter."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model="gpt-4o-transcribe",
            include=["logprobs"],
            response_format="json",
            _test_param="include",
            _test_variant="logprobs",
        )
        report.output()
        assert_report_valid(report)

    def test_param_diarization(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Test speaker diarization (using available model)."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model="gpt-4o-transcribe",
            response_format="json",
            known_speaker_names=["speaker_a"],
            _test_param="known_speaker_names",
        )
        report.output()
        assert_report_valid(report)

    def test_param_stream(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Test stream parameter."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model="gpt-4o-transcribe",
            stream=True,
            _test_param="stream",
            _test_variant="true",
        )
        report.output()
        assert_report_valid(report)

    def test_param_language(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Test language parameter (ISO-639-1)."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            language="en",
            _test_param="language",
            _test_variant="en",
        )
        report.output()
        assert_report_valid(report)

    def test_param_prompt(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Test prompt parameter (guide style)."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            prompt="The transcription should be about an emergency broadcast.",
            _test_param="prompt",
        )
        report.output()
        assert_report_valid(report)

    def test_param_temperature(self, openai_client: OpenAIClient, audio_file_en: Path) -> None:
        """Test temperature parameter."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            temperature=0.0,
            _test_param="temperature",
        )
        report.output()
        assert_report_valid(report)

    def test_param_timestamp_granularities(
        self, openai_client: OpenAIClient, audio_file_en: Path
    ) -> None:
        """Test timestamp_granularities parameter."""
        report = openai_client.validate_transcription(
            file_path=audio_file_en,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            _test_param="timestamp_granularities",
            _test_variant="word+segment",
        )
        report.output()
        assert_report_valid(report)


@pytest.mark.integration
class TestAudioTranslations:
    """Tests for /v1/audio/translations endpoint.

    Test Strategy: Translating Chinese audio to English.
    """

    def test_baseline(self, openai_client: OpenAIClient, audio_file_zh: Path) -> None:
        """Baseline translation test (Chinese to English)."""
        report = openai_client.validate_translation(file_path=audio_file_zh, model="whisper-1")
        report.output()
        assert_report_valid(report)

    def test_param_prompt(self, openai_client: OpenAIClient, audio_file_zh: Path) -> None:
        """Test translation with prompt."""
        report = openai_client.validate_translation(
            file_path=audio_file_zh,
            prompt="Translate the Chinese text carefully.",
            _test_param="prompt",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("fmt", ["json", "verbose_json", "text", "srt", "vtt"])
    def test_param_response_format(
        self, openai_client: OpenAIClient, audio_file_zh: Path, fmt: str
    ) -> None:
        """Test translation with various response formats."""
        report = openai_client.validate_translation(
            file_path=audio_file_zh,
            response_format=fmt,
            _test_param="response_format",
            _test_variant=fmt,
        )
        report.output()
        assert_report_valid(report)

    def test_param_temperature(self, openai_client: OpenAIClient, audio_file_zh: Path) -> None:
        """Test translation with temperature."""
        report = openai_client.validate_translation(
            file_path=audio_file_zh,
            temperature=0.0,
            _test_param="temperature",
        )
        report.output()
        assert_report_valid(report)


# =============================================================================
# Images API Tests
# =============================================================================


@pytest.mark.integration
class TestImageGeneration:
    """Tests for /v1/images/generations endpoint.

    Test Strategy: Parameterized testing
    - Uses @pytest.mark.parametrize to test multiple values for each parameter
    - Follows Audio API testing pattern
    - Each test validates exactly one parameter on top of a baseline
    - Only tests supported models: dall-e-2, gpt-image-1.5
    - Model-specific parameters are tested separately (dall-e-2, GPT)
    """

    # =========================================================================
    # Baseline Test
    # =========================================================================

    def test_baseline(
        self, openai_client: OpenAIClient, baseline_image_params: dict
    ) -> None:
        """Baseline test with only required parameters."""
        report = openai_client.validate_image_generation(**baseline_image_params)
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 1: Core Parameters (dall-e-2)
    # =========================================================================

    def test_param_n(
        self, openai_client: OpenAIClient, baseline_image_params: dict
    ) -> None:
        """Test n parameter (number of images, 1-10)."""
        # Remove 'n' from baseline to avoid parameter conflict
        params = {k: v for k, v in baseline_image_params.items() if k != "n"}

        report = openai_client.validate_image_generation(
            **params,
            n=2,
            _test_param="n",
            _test_variant="multiple images",
        )
        report.output()
        assert_report_valid(report)

        # Verify 2 images returned
        if report.raw_response:
            data = report.raw_response.get("data", [])
            assert len(data) == 2

    @pytest.mark.parametrize(
        "size",
        ["256x256", "512x512", "1024x1024"],
    )
    def test_param_size_dalle2(
        self, openai_client: OpenAIClient, size: str
    ) -> None:
        """Test size parameter for dall-e-2 (supports 256x256, 512x512, 1024x1024)."""
        report = openai_client.validate_image_generation(
            prompt="A simple geometric shape.",
            model="dall-e-2",
            size=size,
            _test_param="size",
            _test_variant=f"dall-e-2 {size}",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize(
        "size",
        ["1024x1024", "1536x1024", "1024x1536", "auto"],
    )
    def test_param_size_gpt(
        self, openai_client: OpenAIClient, size: str
    ) -> None:
        """Test size parameter for GPT models (supports 1024x1024, 1536x1024, 1024x1536, auto)."""
        report = openai_client.validate_image_generation(
            prompt="A simple geometric shape.",
            model="gpt-image-1.5",
            size=size,
            _test_param="size",
            _test_variant=f"gpt {size}",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize(
        "response_format",
        ["url", "b64_json"],
    )
    def test_param_response_format(
        self, openai_client: OpenAIClient, baseline_image_params: dict, response_format: str
    ) -> None:
        """Test response_format parameter for dall-e-2/3 (url, b64_json)."""
        report = openai_client.validate_image_generation(
            **baseline_image_params,
            response_format=response_format,
            _test_param="response_format",
            _test_variant=response_format,
        )
        report.output()
        assert_report_valid(report)

        # Verify correct format is present
        if report.raw_response:
            data = report.raw_response.get("data", [{}])
            assert response_format in data[0], f"Expected {response_format} in response"

    def test_param_user(
        self, openai_client: OpenAIClient, baseline_image_params: dict
    ) -> None:
        """Test user parameter (tracking)."""
        report = openai_client.validate_image_generation(
            **baseline_image_params,
            user="test-user-123",
            _test_param="user",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 2: GPT Model Specific
    # =========================================================================

    @pytest.mark.parametrize(
        "background",
        ["transparent", "opaque", "auto"],
    )
    def test_param_background(
        self, openai_client: OpenAIClient, background: str
    ) -> None:
        """Test background parameter for GPT models (transparent, opaque, auto)."""
        report = openai_client.validate_image_generation(
            prompt="A red circle.",
            model="gpt-image-1.5",
            background=background,
            output_format="png",  # png/webp support transparency
            _test_param="background",
            _test_variant=background,
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize(
        "output_format",
        ["png", "jpeg", "webp"],
    )
    def test_param_output_format(
        self, openai_client: OpenAIClient, output_format: str
    ) -> None:
        """Test output_format parameter for GPT models (png, jpeg, webp)."""
        report = openai_client.validate_image_generation(
            prompt="A red circle.",
            model="gpt-image-1.5",
            output_format=output_format,
            _test_param="output_format",
            _test_variant=output_format,
        )
        report.output()
        assert_report_valid(report)

    def test_param_output_compression(
        self, openai_client: OpenAIClient
    ) -> None:
        """Test output_compression parameter. GPT models only."""
        report = openai_client.validate_image_generation(
            prompt="A red circle.",
            model="gpt-image-1.5",
            output_format="jpeg",  # compression supported for jpeg/webp
            output_compression=50,
            _test_param="output_compression",
            _test_variant="50%",
        )
        report.output()
        assert_report_valid(report)

    def test_param_moderation(self, openai_client: OpenAIClient) -> None:
        """Test moderation parameter. GPT models only."""

        report = openai_client.validate_image_generation(
            prompt="A red circle.",
            model="gpt-image-1.5",
            moderation="low",
            _test_param="moderation",
            _test_variant="low",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize(
        "quality",
        ["high", "medium", "low", "auto"],
    )
    def test_param_quality_gpt(
        self, openai_client: OpenAIClient, quality: str
    ) -> None:
        """Test quality parameter for GPT models (high, medium, low, auto)."""
        report = openai_client.validate_image_generation(
            prompt="A red circle.",
            model="gpt-image-1.5",
            quality=quality,
            _test_param="quality",
            _test_variant=f"gpt {quality}",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 3: Streaming (gpt-image-1.5)
    # =========================================================================

    def test_param_stream(self, openai_client: OpenAIClient) -> None:
        """Test stream parameter. GPT models only."""

        events, report = openai_client.validate_image_generation_stream(
            prompt="A red circle.",
            model="gpt-image-1.5",
            _test_param="stream",
            _test_variant="true",
        )
        report.output()
        assert len(events) > 0
        assert report.success

    def test_param_partial_images(self, openai_client: OpenAIClient) -> None:
        """Test partial_images parameter. GPT models only with stream."""

        events, report = openai_client.validate_image_generation_stream(
            prompt="A red circle.",
            model="gpt-image-1.5",
            partial_images=2,
            _test_param="partial_images",
            _test_variant="2 partial images",
        )
        report.output()
        assert len(events) > 0
        assert report.success



# =============================================================================
# Image Edit API Tests
# =============================================================================


@pytest.mark.integration
class TestImageEdit:
    """Tests for /v1/images/edits endpoint.

    Test Strategy: Single-parameter testing
    - Each test validates exactly one parameter on top of a baseline
    - Baseline: image_path, prompt, model, size (minimum required)
    - Tests both dall-e-2 and gpt-image-1.5 models
    """

    # =========================================================================
    # Baseline Test
    # =========================================================================

    def test_baseline(
        self, openai_client: OpenAIClient, baseline_image_edit_params: dict
    ) -> None:
        """Baseline test with only required parameters.

        Tests: image_path, prompt, model=dall-e-2, size=256x256
        This is the foundation for all single-parameter tests.
        """
        report = openai_client.validate_image_edit(**baseline_image_edit_params)
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 1: Core Parameters (dall-e-2)
    # =========================================================================

    def test_param_n(
        self, openai_client: OpenAIClient, baseline_image_edit_params: dict
    ) -> None:
        """Test n parameter (number of edited images, 1-10).

        Validates that the API returns exactly n edited images.
        """
        n_value = 2
        # Remove 'n' from baseline to avoid conflicts
        params = {k: v for k, v in baseline_image_edit_params.items() if k != "n"}

        report = openai_client.validate_image_edit(
            **params,
            n=n_value,
            _test_param="n",
            _test_variant="multiple edits",
        )
        report.output()
        assert_report_valid(report)

        # Additional validation: verify n images returned
        if report.raw_response:
            data = report.raw_response.get("data", [])
            assert len(data) == n_value, f"Expected {n_value} images, got {len(data)}"

    @pytest.mark.parametrize("size", ["256x256", "512x512", "1024x1024"])
    def test_param_size_dalle2(
        self, openai_client: OpenAIClient, test_image_png: Path, size: str
    ) -> None:
        """Test size parameter for dall-e-2 (supports 256x256, 512x512, 1024x1024)."""
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="dall-e-2",
            size=size,
            _test_param="size",
            _test_variant=f"dall-e-2 {size}",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("response_format", ["url", "b64_json"])
    def test_param_response_format(
        self, openai_client: OpenAIClient, baseline_image_edit_params: dict, response_format: str
    ) -> None:
        """Test response_format parameter for dall-e-2 (url, b64_json)."""
        report = openai_client.validate_image_edit(
            **baseline_image_edit_params,
            response_format=response_format,
            _test_param="response_format",
            _test_variant=response_format,
        )
        report.output()
        assert_report_valid(report)

        # Verify correct format is present
        if report.raw_response:
            data = report.raw_response.get("data", [{}])
            assert response_format in data[0], f"Expected {response_format} in response"

    def test_param_user(
        self, openai_client: OpenAIClient, baseline_image_edit_params: dict
    ) -> None:
        """Test user parameter (tracking identifier)."""
        report = openai_client.validate_image_edit(
            **baseline_image_edit_params,
            user="test-user-image-edit-123",
            _test_param="user",
        )
        report.output()
        assert_report_valid(report)

    def test_param_mask(
        self, openai_client: OpenAIClient, test_image_png: Path, temp_dir: Path
    ) -> None:
        """Test mask parameter (selective editing with transparency mask).

        Creates a simple mask with transparent center for selective editing.
        """
        from PIL import Image

        # Create a simple mask: opaque edges, transparent center
        mask_path = temp_dir / "test_mask.png"
        mask = Image.new("RGBA", (256, 256), (0, 0, 0, 255))  # Black opaque
        # Make center transparent (will be edited)
        for x in range(64, 192):
            for y in range(64, 192):
                mask.putpixel((x, y), (0, 0, 0, 0))  # Transparent
        mask.save(mask_path)

        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add a red circle in the center",
            model="dall-e-2",
            size="256x256",
            mask_path=mask_path,
            _test_param="mask",
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 2: GPT Model Specific Parameters
    # =========================================================================

    @pytest.mark.parametrize("size", ["1024x1024", "1536x1024", "1024x1536", "auto"])
    def test_param_size_gpt(
        self, openai_client: OpenAIClient, test_image_png: Path, size: str
    ) -> None:
        """Test size parameter for GPT models (supports 1024x1024, 1536x1024, 1024x1536, auto)."""
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            size=size,
            _test_param="size",
            _test_variant=f"gpt {size}",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("quality", ["high", "medium", "low", "auto"])
    def test_param_quality(
        self, openai_client: OpenAIClient, test_image_png: Path, quality: str
    ) -> None:
        """Test quality parameter for GPT models (high, medium, low, auto)."""
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            quality=quality,
            _test_param="quality",
            _test_variant=f"gpt {quality}",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("output_format", ["png", "jpeg", "webp"])
    def test_param_output_format(
        self, openai_client: OpenAIClient, test_image_png: Path, output_format: str
    ) -> None:
        """Test output_format parameter for GPT models (png, jpeg, webp)."""
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            output_format=output_format,
            _test_param="output_format",
            _test_variant=output_format,
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("background", ["transparent", "opaque", "auto"])
    def test_param_background(
        self, openai_client: OpenAIClient, test_image_png: Path, background: str
    ) -> None:
        """Test background parameter for GPT models (transparent, opaque, auto)."""
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            background=background,
            output_format="png",  # png/webp support transparency
            _test_param="background",
            _test_variant=background,
        )
        report.output()
        assert_report_valid(report)

    def test_param_output_compression(
        self, openai_client: OpenAIClient, test_image_png: Path
    ) -> None:
        """Test output_compression parameter for GPT models (0-100%).

        Compression is supported for jpeg and webp formats.
        """
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            output_format="jpeg",  # compression supported for jpeg/webp
            output_compression=50,
            _test_param="output_compression",
            _test_variant="50%",
        )
        report.output()
        assert_report_valid(report)

    @pytest.mark.parametrize("input_fidelity", ["high", "low"])
    def test_param_input_fidelity(
        self, openai_client: OpenAIClient, test_image_png: Path, input_fidelity: str
    ) -> None:
        """Test input_fidelity parameter (high, low).

        Controls how closely the edit matches the input image style/features.
        Note: Only supported by gpt-image-1, may not work with gpt-image-1.5.
        """
        report = openai_client.validate_image_edit(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            input_fidelity=input_fidelity,
            _test_param="input_fidelity",
            _test_variant=input_fidelity,
        )
        report.output()
        assert_report_valid(report)

    # =========================================================================
    # Tier 3: Streaming Parameters (Requires validate_image_edit_stream)
    # =========================================================================

    def test_param_stream(
        self, openai_client: OpenAIClient, test_image_png: Path
    ) -> None:
        """Test stream parameter (enable streaming mode).

        Validates streaming edit for GPT image models.
        """
        events, report = openai_client.validate_image_edit_stream(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
            stream=True,
            _test_param="stream",
            _test_variant="true",
        )
        report.output()
        assert len(events) > 0
        assert any(e.get("type") == "image_edit.completed" for e in events)
        assert report.success

    def test_param_partial_images(
        self, openai_client: OpenAIClient, test_image_png: Path
    ) -> None:
        """Test partial_images parameter (0-3 partial images during streaming).

        Validates partial images during streaming edits.
        """
        events, report = openai_client.validate_image_edit_stream(
            image_path=test_image_png,
            prompt="Add colorful borders around the edges",
            model="gpt-image-1.5",
                stream=True,
            partial_images=2,
            _test_param="partial_images",
            _test_variant="2 partial images",
        )
        report.output()
        assert len(events) > 0
        assert any(e.get("type") == "image_edit.partial_image" for e in events)
        assert any(e.get("type") == "image_edit.completed" for e in events)
        assert report.success



# =============================================================================
# Summary Tests (run all basic validations)
# =============================================================================


@pytest.mark.integration
class TestAllEndpoints:
    """Quick validation of all endpoints with minimal parameters."""

    def test_all_json_endpoints(self, openai_client: OpenAIClient) -> None:
        """Run basic validation on all JSON-returning endpoints."""
        results = []

        # Chat completions
        report = openai_client.validate_chat_completion()
        results.append(("chat/completions", report))

        # Responses
        report = openai_client.validate_responses()
        results.append(("responses", report))

        # Embeddings
        report = openai_client.validate_embeddings()
        results.append(("embeddings", report))

        # Print summary
        print("\n" + "=" * 60)
        print("OpenAI API Validation Summary")
        print("=" * 60)

        all_passed = True
        for endpoint, report in results:
            status = "PASS" if report.success else "FAIL"
            print(f"  {endpoint}: {status} ({report.valid_count}/{report.total_fields})")
            if not report.success:
                all_passed = False

        print("=" * 60)

        assert all_passed, "Some endpoint validations failed"
