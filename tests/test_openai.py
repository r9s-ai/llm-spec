"""Integration tests for OpenAI API validation."""

from __future__ import annotations

import pytest

from llm_spec.providers.openai import OpenAIClient
from tests.base import assert_report_valid, print_report_summary


# =============================================================================
# Chat Completions API Tests
# =============================================================================


@pytest.mark.integration
class TestChatCompletions:
    """Tests for /v1/chat/completions endpoint."""

    def test_basic_completion(self, openai_client: OpenAIClient) -> None:
        """Test basic chat completion with common parameters."""
        report = openai_client.validate_chat_completion(
            temperature=0.5,
            max_tokens=50,
        )
        report.print()
        assert_report_valid(report)

    def test_with_system_message(self, openai_client: OpenAIClient) -> None:
        """Test chat completion with system message."""
        report = openai_client.validate_chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'test'."},
            ]
        )
        report.print()
        assert_report_valid(report)

    def test_multi_turn_conversation(self, openai_client: OpenAIClient) -> None:
        """Test multi-turn conversation."""
        report = openai_client.validate_chat_completion(
            messages=[
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Hello Alice!"},
                {"role": "user", "content": "What is my name?"},
            ]
        )
        report.print()
        assert_report_valid(report)

    @pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-4o"])
    def test_different_models(self, openai_client: OpenAIClient, model: str) -> None:
        """Test chat completion with different models."""
        report = openai_client.validate_chat_completion(model=model)
        report.print()
        assert_report_valid(report)

    def test_with_tool_definition(self, openai_client: OpenAIClient) -> None:
        """Test chat completion with tool/function definition."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather in a location",
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
                },
            }
        ]
        report = openai_client.validate_chat_completion(
            messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
            tools=tools,
        )
        report.print()
        assert_report_valid(report)

    def test_with_image_input(self, openai_client: OpenAIClient) -> None:
        """Test chat completion with image input (vision).

        Based on official OpenAI example:
        https://platform.openai.com/docs/api-reference/chat/create
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
        )
        report.print()
        assert_report_valid(report)


# =============================================================================
# Responses API Tests
# =============================================================================


@pytest.mark.integration
class TestResponses:
    """Tests for /v1/responses endpoint."""

    def test_basic_response(self, openai_client: OpenAIClient) -> None:
        """Test basic responses API call."""
        report = openai_client.validate_responses()
        report.print()
        assert_report_valid(report)

    @pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-4o"])
    def test_different_models(self, openai_client: OpenAIClient, model: str) -> None:
        """Test responses API with different models."""
        report = openai_client.validate_responses(model=model)
        report.print()
        assert_report_valid(report)

    def test_with_instructions(self, openai_client: OpenAIClient) -> None:
        """Test responses API with instructions."""
        report = openai_client.validate_responses(
            input_text="What is 2+2?",
            instructions="Answer concisely with just the number.",
        )
        report.print()
        assert_report_valid(report)

    def test_with_tool_definition(self, openai_client: OpenAIClient) -> None:
        """Test responses API with tool definition that triggers function_call output.

        Based on official OpenAI example:
        https://platform.openai.com/docs/api-reference/responses
        """
        tools = [
            {
                "type": "function",
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
                    "required": ["location", "unit"],
                },
            }
        ]
        report = openai_client.validate_responses(
            input_text="What is the weather like in Boston today?",
            tools=tools,
            tool_choice="auto",
        )
        report.print()
        assert_report_valid(report)

    def test_with_web_search(self, openai_client: OpenAIClient) -> None:
        """Test responses API with web_search_preview tool (from official docs).

        This test validates the web_search_call output type.
        """
        tools = [{"type": "web_search_preview"}]
        report = openai_client.validate_responses(
            model="gpt-4o",
            input_text="What was a positive news story from today?",
            tools=tools,
        )
        report.print()
        assert_report_valid(report)

    def test_with_file_search(self, openai_client: OpenAIClient) -> None:
        """Test responses API with file_search tool (from official docs).

        Based on official OpenAI example:
        https://platform.openai.com/docs/api-reference/responses

        Note: This test requires a pre-created vector_store_id.
        The vector_store must contain indexed files for search.
        """
        # Default vector_store_id from official example
        # In real usage, create vector store via /v1/vector_stores API first
        vector_store_id = "vs_1234567890"

        tools = [
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
                "max_num_results": 20,
            }
        ]
        report = openai_client.validate_responses(
            model="gpt-4.1",
            input_text="What are the attributes of an ancient brown dragon?",
            tools=tools,
        )
        report.print()
        assert_report_valid(report)

    def test_with_image_input(self, openai_client: OpenAIClient) -> None:
        """Test responses API with image input (vision).

        Note: This test requires a model that supports vision.
        """
        input_messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "What is in this image?"},
                    {
                        "type": "input_image",
                        "image_url": "https://img95.699pic.com/photo/60021/9579.jpg_wh860.jpg",
                    },
                ],
            }
        ]
        report = openai_client.validate_responses(
            model="gpt-4o",
            input_messages=input_messages,
        )
        report.print()
        assert_report_valid(report)

    def test_with_file_input(self, openai_client: OpenAIClient) -> None:
        """Test responses API with file input (PDF).

        Based on official OpenAI example:
        https://platform.openai.com/docs/api-reference/responses
        """
        input_messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "what is in this file?"},
                    {
                        "type": "input_file",
                        "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                    },
                ],
            }
        ]
        report = openai_client.validate_responses(
            model="gpt-4o",
            input_messages=input_messages,
        )
        report.print()
        assert_report_valid(report)

    def test_with_conversation_history(self, openai_client: OpenAIClient) -> None:
        """Test responses API with multi-turn conversation."""
        input_messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Hello Alice! How can I help you today?"},
            {"role": "user", "content": "What's my name?"},
        ]
        report = openai_client.validate_responses(
            input_messages=input_messages,
        )
        report.print()
        assert_report_valid(report)

    def test_with_reasoning(self, openai_client: OpenAIClient) -> None:
        """Test responses API with reasoning configuration.

        Based on official OpenAI example for o3-mini/o1 models.
        """
        report = openai_client.validate_responses(
            model="o3-mini",
            input_text="How much wood would a woodchuck chuck?",
            reasoning={"effort": "high"},
        )
        report.print()
        assert_report_valid(report)

    def test_bedtime_story(self, openai_client: OpenAIClient) -> None:
        """Test responses API with simple text input (from official docs)."""
        report = openai_client.validate_responses(
            model="gpt-4o-mini",
            input_text="Tell me a three sentence bedtime story about a unicorn.",
        )
        report.print()
        assert_report_valid(report)

    def test_streaming_response(self, openai_client: OpenAIClient) -> None:
        """Test streaming responses API (from official docs).

        Validates that streaming returns the expected event types:
        - response.created
        - response.in_progress
        - response.output_item.added
        - response.content_part.added
        - response.output_text.delta
        - response.output_text.done
        - response.content_part.done
        - response.output_item.done
        - response.completed
        """
        events, success = openai_client.validate_responses_stream(
            model="gpt-4o-mini",
            input_text="Hello!",
            instructions="You are a helpful assistant.",
        )

        # Print event types received
        event_types = [e.get("type") for e in events if "type" in e]
        print(f"\nReceived {len(events)} events")
        print(f"Event types: {set(event_types)}")

        assert success, f"Streaming should complete successfully. Got event types: {set(event_types)}"
        assert len(events) > 0, "Should receive at least one event"

        # Verify key event types are present
        assert "response.created" in event_types, "Should have response.created event"
        assert "response.completed" in event_types, "Should have response.completed event"


# =============================================================================
# Embeddings API Tests
# =============================================================================


@pytest.mark.integration
class TestEmbeddings:
    """Tests for /v1/embeddings endpoint."""

    def test_single_text(self, openai_client: OpenAIClient) -> None:
        """Test embedding a single text."""
        report = openai_client.validate_embeddings()
        report.print()
        assert_report_valid(report)

    def test_batch_texts(self, openai_client: OpenAIClient) -> None:
        """Test embedding multiple texts."""
        report = openai_client.validate_embeddings(
            input_text=["Hello", "World", "Test"]
        )
        report.print()
        assert_report_valid(report)

    @pytest.mark.parametrize(
        "model", ["text-embedding-3-small", "text-embedding-3-large"]
    )
    def test_different_models(self, openai_client: OpenAIClient, model: str) -> None:
        """Test embeddings with different models."""
        report = openai_client.validate_embeddings(model=model)
        report.print()
        assert_report_valid(report)

    def test_with_dimensions(self, openai_client: OpenAIClient) -> None:
        """Test embeddings with custom dimensions (text-embedding-3 only)."""
        report = openai_client.validate_embeddings(
            model="text-embedding-3-small",
            dimensions=512,
        )
        report.print()
        assert_report_valid(report)

    def test_base64_encoding(self, openai_client: OpenAIClient) -> None:
        """Test embeddings with base64 encoding format."""
        report = openai_client.validate_embeddings(
            encoding_format="base64",
        )
        report.print()
        assert_report_valid(report)


# =============================================================================
# Audio API Tests
# =============================================================================


@pytest.mark.integration
class TestAudioSpeech:
    """Tests for /v1/audio/speech endpoint (TTS)."""

    def test_basic_speech(self, openai_client: OpenAIClient) -> None:
        """Test basic text-to-speech."""
        audio_data, is_valid = openai_client.validate_speech()
        assert is_valid, "Should return valid audio data"
        assert len(audio_data) > 0, "Audio data should not be empty"

    @pytest.mark.parametrize("voice", ["alloy", "echo", "nova", "shimmer"])
    def test_different_voices(self, openai_client: OpenAIClient, voice: str) -> None:
        """Test TTS with different voices."""
        audio_data, is_valid = openai_client.validate_speech(voice=voice)
        assert is_valid, f"Voice '{voice}' should return valid audio"

    @pytest.mark.parametrize("model", ["tts-1", "tts-1-hd"])
    def test_different_models(self, openai_client: OpenAIClient, model: str) -> None:
        """Test TTS with different models."""
        audio_data, is_valid = openai_client.validate_speech(model=model)
        assert is_valid, f"Model '{model}' should return valid audio"


# =============================================================================
# Images API Tests
# =============================================================================


@pytest.mark.integration
class TestImageGeneration:
    """Tests for /v1/images/generations endpoint."""

    def test_basic_generation(
        self, openai_client: OpenAIClient, run_expensive: bool
    ) -> None:
        """Test basic image generation."""
        if not run_expensive:
            pytest.skip("Image generation is expensive, use --run-expensive to run")

        report = openai_client.validate_image_generation(
            prompt="A simple red circle on white background",
            model="dall-e-2",
            size="256x256",
            n=1,
        )
        report.print()
        assert_report_valid(report)

    def test_b64_json_format(
        self, openai_client: OpenAIClient, run_expensive: bool
    ) -> None:
        """Test image generation with base64 response format."""
        if not run_expensive:
            pytest.skip("Image generation is expensive, use --run-expensive to run")

        report = openai_client.validate_image_generation(
            prompt="A simple blue square",
            response_format="b64_json",
            size="256x256",
        )
        report.print()
        assert_report_valid(report)


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
