"""OpenAI API client implementation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Literal

from llm_spec.core import config as global_config
from llm_spec.core.client import BaseClient
from llm_spec.core.config import ProviderConfig
from llm_spec.core.report import FieldResult, FieldStatus, ValidationReport
from llm_spec.core.validator import SchemaValidator
from llm_spec.providers.openai.schemas import (
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    EmbeddingResponse,
    ImageResponse,
    ImageStreamEvent,
    ResponseObject,
    TranscriptionDiarizedResponse,
    TranscriptionResponse,
    TranscriptionVerboseResponse,
    TranslationResponse,
    TranslationVerboseResponse,
)


class OpenAIClient(BaseClient):
    """Client for OpenAI API."""

    provider_name = "openai"
    default_base_url = "https://api.openai.com/v1"

    def _get_global_config(self) -> ProviderConfig:
        return global_config.openai

    def _build_headers(self) -> dict[str, str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def validate_chat_completion(
        self,
        *,
        model: str = "gpt-4o-mini",
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate chat completion endpoint response against schema.

        Args:
            model: Model to use for the test request
            messages: Optional custom messages, defaults to a simple test message
            **kwargs: Additional parameters to pass to the API

        Returns:
            ValidationReport with field-level results
        """
        if messages is None:
            messages = [{"role": "user", "content": "Say 'test' and nothing else."}]

        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            **kwargs,
        }
        # Only add max_tokens if neither max_tokens nor max_completion_tokens is specified
        if "max_tokens" not in request_body and "max_completion_tokens" not in request_body:
            request_body["max_tokens"] = 150

        try:
            response = self.request("POST", "/chat/completions", json=request_body)

            validator = SchemaValidator(provider=self.provider_name, endpoint="chat/completions")
            report = validator.validate(response, ChatCompletionResponse, request_params=request_body)
            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            # For HTTP failures, still record the test parameters for statistics
            from llm_spec.core.report import ValidationReport, get_collector, get_current_test_name

            # Create a minimal failed report for parameter tracking
            report = ValidationReport(
                provider=self.provider_name,
                endpoint="chat/completions",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )

            # Save to collector for statistics (but don't output to JSON)
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)

            # Re-raise the exception so the test still fails
            raise

    def validate_chat_completion_stream(
        self,
        *,
        model: str = "gpt-4o-mini",
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], ValidationReport]:
        """Validate streaming chat completion endpoint.

        Based on official OpenAI example:
        https://platform.openai.com/docs/api-reference/chat-streaming

        Args:
            model: Model to use for the test request
            messages: Optional custom messages, defaults to a simple test message
            **kwargs: Additional parameters to pass to the API

        Returns:
            Tuple of (list of chunk events, ValidationReport for the stream)
        """
        import json

        if messages is None:
            messages = [{"role": "user", "content": "Say 'test' and nothing else."}]

        request_body = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }

        chunks: list[dict[str, Any]] = []
        all_fields: list[FieldResult] = []
        has_errors = False

        for data in self.stream("POST", "/chat/completions", json=request_body):
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                chunks.append(chunk)

                # Validate each chunk against schema
                validator = SchemaValidator(
                    provider=self.provider_name, endpoint="chat/completions/stream"
                )
                chunk_report = validator.validate(chunk, ChatCompletionStreamResponse)
                if not chunk_report.success:
                    has_errors = True
                    # Only collect error fields to avoid duplicates
                    for f in chunk_report.fields:
                        if f.status != FieldStatus.VALID:
                            all_fields.append(f)
            except json.JSONDecodeError:
                continue

        # Check if we got a complete response
        has_finish_reason = any(
            chunk.get("choices", [{}])[0].get("finish_reason") is not None
            for chunk in chunks
            if chunk.get("choices")
        )

        # Create a summary report for the entire stream
        report = ValidationReport(
            provider=self.provider_name,
            endpoint="chat/completions",
            success=not has_errors and len(chunks) > 0 and has_finish_reason,
            total_fields=len(chunks),  # Number of chunks validated
            valid_count=len(chunks) - len(all_fields),
            invalid_count=len(all_fields),
            fields=all_fields,
            request_params=request_body,
            raw_response={"chunks": chunks, "chunk_count": len(chunks)},
        )

        return chunks, report

    def validate_embeddings(
        self,
        *,
        model: str = "text-embedding-3-small",
        input_text: str | list[str] = "Hello, world!",
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate embeddings endpoint response against schema.

        Args:
            model: Embedding model to use
            input_text: Text to embed (string or list of strings)
            **kwargs: Additional parameters to pass to the API

        Returns:
            ValidationReport with field-level results
        """
        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body = {
            "model": model,
            "input": input_text,
            **kwargs,
        }

        try:
            response = self.request("POST", "/embeddings", json=request_body)

            validator = SchemaValidator(provider=self.provider_name, endpoint="embeddings")
            report = validator.validate(response, EmbeddingResponse, request_params=request_body)
            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            # For HTTP failures, still record the test parameters for statistics
            from llm_spec.core.report import ValidationReport, get_collector, get_current_test_name

            # Create a minimal failed report for parameter tracking
            report = ValidationReport(
                provider=self.provider_name,
                endpoint="embeddings",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )

            # Save to collector for statistics (but don't output to JSON)
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)

            # Re-raise the exception so the test still fails
            raise

    def validate_responses(
        self,
        *,
        model: str = "gpt-4o-mini",
        input_text: str | None = None,
        input_messages: list[dict[str, Any]] | None = None,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate responses endpoint response against schema.

        Args:
            model: Model to use for the test request
            input_text: Simple text input (mutually exclusive with input_messages)
            input_messages: List of messages for conversation input
            instructions: System instructions
            tools: Tool definitions
            **kwargs: Additional parameters to pass to the API

        Returns:
            ValidationReport with field-level results
        """
        if input_messages is not None:
            input_value: str | list[dict[str, Any]] = input_messages
        elif input_text is not None:
            input_value = input_text
        else:
            input_value = "Say 'test' and nothing else."

        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body: dict[str, Any] = {
            "model": model,
            "input": input_value,
            **kwargs,
        }

        if instructions is not None:
            request_body["instructions"] = instructions
        if tools is not None:
            request_body["tools"] = tools

        try:
            response = self.request("POST", "/responses", json=request_body)
            validator = SchemaValidator(provider=self.provider_name, endpoint="responses")
            report = validator.validate(response, ResponseObject, request_params=request_body)
            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            # For HTTP failures, still record the test parameters for statistics
            from llm_spec.core.report import ValidationReport, get_collector, get_current_test_name

            # Create a minimal failed report for parameter tracking
            report = ValidationReport(
                provider=self.provider_name,
                endpoint="responses",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )

            # Save to collector for statistics (but don't output to JSON)
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)

            # Re-raise the exception so the test still fails
            raise

    def validate_responses_stream(
        self,
        *,
        model: str = "gpt-4o-mini",
        input_text: str | None = None,
        input_messages: list[dict[str, Any]] | None = None,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], ValidationReport]:
        """Validate streaming responses endpoint.

        Args:
            model: Model to use for the test request
            input_text: Simple text input (mutually exclusive with input_messages)
            input_messages: List of messages for conversation input
            instructions: System instructions
            tools: Tool definitions
            **kwargs: Additional parameters to pass to the API

        Returns:
            Tuple of (list of events, success boolean)
        """
        import json

        # Determine input
        if input_messages is not None:
            input_value: str | list[dict[str, Any]] = input_messages
        elif input_text is not None:
            input_value = input_text
        else:
            input_value = "Say 'test' and nothing else."

        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body: dict[str, Any] = {
            "model": model,
            "input": input_value,
            "stream": True,
            **kwargs,
        }

        if instructions is not None:
            request_body["instructions"] = instructions
        if tools is not None:
            request_body["tools"] = tools

        events: list[dict[str, Any]] = []
        seen_event_types: set[str] = set()

        try:
            for data in self.stream("POST", "/responses", json=request_body):
                if data.strip() == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    events.append(event)
                    if "type" in event:
                        seen_event_types.add(event["type"])
                except json.JSONDecodeError:
                    continue

            # Check if we got a completed response
            has_completed = "response.completed" in seen_event_types
            has_basic_events = (
                "response.created" in seen_event_types
                and "response.output_text.done" in seen_event_types
            )
            success = has_completed and has_basic_events

            # Create a summary report for the entire stream
            from llm_spec.core.report import ValidationReport

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="responses",
                success=success,
                total_fields=len(events),
                valid_count=len(events) if success else 0,
                invalid_count=0 if success else 1,
                fields=[],
                request_params=request_body,
                raw_response={"events": events, "event_count": len(events)},
                test_param=test_param,
                test_variant=test_variant,
            )

            return events, report
        except Exception as e:
            # For HTTP failures, still record the test parameters for statistics
            from llm_spec.core.report import ValidationReport, get_collector, get_current_test_name

            # Create a minimal failed report for parameter tracking
            report = ValidationReport(
                provider=self.provider_name,
                endpoint="responses",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )

            # Save to collector for statistics (but don't output to JSON)
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)

            # Re-raise the exception so the test still fails
            raise

    # =========================================================================
    # Audio API
    # =========================================================================

    def validate_speech(
        self,
        *,
        model: Literal[
            "tts-1", "tts-1-hd", "gpt-4o-mini-tts", "gpt-4o-mini-tts-2025-12-15"
        ] = "gpt-4o-mini-tts",
        input_text: str = "Hello, this is a test.",
        voice: str = "alloy",
        stream_format: Literal["sse", "audio"] | None = None,
        **kwargs: Any,
    ) -> tuple[bytes, ValidationReport]:
        """Validate speech (TTS) endpoint.

        Note: Speech API returns binary audio data, not JSON.
        Returns the audio bytes and a ValidationReport for parameter tracking.

        Args:
            model: TTS model to use
            input_text: Text to convert to speech
            voice: Voice to use
            stream_format: Optional stream format (sse or audio)
            **kwargs: Additional parameters

        Returns:
            Tuple of (audio_bytes, ValidationReport)
        """
        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body: dict[str, Any] = {
            "model": model,
            "input": input_text,
            "voice": voice,
            **kwargs,
        }
        if stream_format is not None:
            request_body["stream_format"] = stream_format

        try:
            audio_data = self.request_binary("POST", "/audio/speech", json=request_body)

            # Speech returns binary, so we create a simple report
            # Basic validation: check if we got non-empty binary data
            is_valid = len(audio_data) > 0

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="audio/speech",
                success=is_valid,
                total_fields=1,
                valid_count=1 if is_valid else 0,
                invalid_count=0 if is_valid else 1,
                fields=[
                    FieldResult(
                        field="audio_data",
                        status=FieldStatus.VALID if is_valid else FieldStatus.MISSING,
                        expected="binary data",
                        actual=f"{len(audio_data)} bytes" if is_valid else "0 bytes",
                    )
                ],
                request_params=request_body,
                raw_response={"size": len(audio_data)},
                test_param=test_param,
                test_variant=test_variant,
            )
            return audio_data, report
        except Exception as e:
            from llm_spec.core.report import get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="audio/speech",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            return b"", report

    def validate_transcription(
        self,
        *,
        file_path: str | Path,
        model: Literal[
            "whisper-1",
            "gpt-4o-transcribe",
            "gpt-4o-mini-transcribe",
            "gpt-4o-mini-transcribe-2025-12-15",
            "gpt-4o-transcribe-diarize",
        ] = "whisper-1",
        response_format: Literal[
            "json", "text", "srt", "verbose_json", "vtt", "diarized_json"
        ] = "json",
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate transcription endpoint response against schema.

        Args:
            file_path: Path to audio file to transcribe
            model: Transcription model to use
            response_format: Output format (json, text, srt, verbose_json, vtt, or diarized_json)
            **kwargs: Additional parameters (chunking_strategy, include, language, prompt, temperature, etc.)

        Returns:
            ValidationReport with field-level results
        """
        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        file_path = Path(file_path)

        # Build request parameters for reporting
        request_body = {
            "file": file_path.name,
            "model": model,
            "response_format": response_format,
            **kwargs,
        }

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "audio/mpeg")}
                data = {"model": model, "response_format": response_format, **kwargs}

                # Use request_raw because text/srt/vtt formats return strings, not JSON
                response_text = self.request_raw(
                    "POST", "/audio/transcriptions", data=data, files=files
                )

            # Determine if result is JSON or Text
            is_json = response_format in ["json", "verbose_json", "diarized_json"]

            if is_json:
                import json as json_lib
                response_data = json_lib.loads(response_text)

                if response_format == "verbose_json":
                    schema = TranscriptionVerboseResponse
                elif response_format == "diarized_json":
                    schema = TranscriptionDiarizedResponse
                else:
                    schema = TranscriptionResponse

                validator = SchemaValidator(provider=self.provider_name, endpoint="audio/transcriptions")
                report = validator.validate(response_data, schema, request_params=request_body)
            else:
                # Basic validation for text formats: must be non-empty string
                is_valid = len(response_text.strip()) > 0
                report = ValidationReport(
                    provider=self.provider_name,
                    endpoint="audio/transcriptions",
                    success=is_valid,
                    total_fields=1,
                    valid_count=1 if is_valid else 0,
                    invalid_count=0 if is_valid else 1,
                    fields=[
                        FieldResult(
                            field="text_content",
                            status=FieldStatus.VALID if is_valid else FieldStatus.MISSING,
                            expected="non-empty string",
                            actual=f"{len(response_text)} chars" if is_valid else "empty",
                        )
                    ],
                    request_params=request_body,
                    raw_response={"content": response_text[:100] + "..." if len(response_text) > 100 else response_text},
                )

            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            from llm_spec.core.report import get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="audio/transcriptions",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            # Add to collector but don't re-raise, let the test handle it via report.output() and assertion
            return report

    def validate_translation(
        self,
        *,
        file_path: str | Path,
        model: Literal["whisper-1"] = "whisper-1",
        response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = "json",
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate translation endpoint response against schema.

        Args:
            file_path: Path to audio file to translate
            model: Translation model (only whisper-1 supported)
            response_format: Output format
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        file_path = Path(file_path)

        # Build request parameters for reporting
        request_body = {
            "file": file_path.name,
            "model": model,
            "response_format": response_format,
            **kwargs,
        }

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "audio/mpeg")}
                data = {"model": model, "response_format": response_format, **kwargs}

                # Use request_raw for non-JSON formats
                response_text = self.request_raw(
                    "POST", "/audio/translations", data=data, files=files
                )

            is_json = response_format in ["json", "verbose_json"]

            if is_json:
                import json as json_lib
                response_data = json_lib.loads(response_text)

                schema = (
                    TranslationVerboseResponse
                    if response_format == "verbose_json"
                    else TranslationResponse
                )
                validator = SchemaValidator(provider=self.provider_name, endpoint="audio/translations")
                report = validator.validate(response_data, schema, request_params=request_body)
            else:
                # Basic validation for text formats
                is_valid = len(response_text.strip()) > 0
                report = ValidationReport(
                    provider=self.provider_name,
                    endpoint="audio/translations",
                    success=is_valid,
                    total_fields=1,
                    valid_count=1 if is_valid else 0,
                    invalid_count=0 if is_valid else 1,
                    fields=[
                        FieldResult(
                            field="text_content",
                            status=FieldStatus.VALID if is_valid else FieldStatus.MISSING,
                            expected="non-empty string",
                            actual=f"{len(response_text)} chars" if is_valid else "empty",
                        )
                    ],
                    request_params=request_body,
                    raw_response={"content": response_text[:100] + "..." if len(response_text) > 100 else response_text},
                )

            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            from llm_spec.core.report import get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="audio/translations",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            return report

    # =========================================================================
    # Images API
    # =========================================================================

    def validate_image_generation(
        self,
        *,
        prompt: str = "A white cat",
        model: str = "dall-e-2",
        n: int | None = None,
        size: str | None = None,
        response_format: str | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate image generation endpoint response against schema.

        Args:
            prompt: Text description of the image
            model: Model to use
            n: Number of images to generate
            size: Image size
            response_format: Return URL or base64
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            **kwargs,
        }
        if n is not None:
            request_body["n"] = n
        if size is not None:
            request_body["size"] = size
        if response_format is not None:
            request_body["response_format"] = response_format

        try:
            response = self.request("POST", "/images/generations", json=request_body)

            validator = SchemaValidator(provider=self.provider_name, endpoint="images/generations")
            report = validator.validate(response, ImageResponse, request_params=request_body)
            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            from llm_spec.core.report import get_collector, get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="images/generations",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)
            raise

    def validate_image_generation_stream(
        self,
        *,
        prompt: str = "A white cat",
        model: str = "gpt-image-1.5",
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], ValidationReport]:
        """Validate streaming image generation endpoint.

        Args:
            prompt: Text description of the image
            model: Model to use (must support streaming)
            **kwargs: Additional parameters

        Returns:
            Tuple of (list of events, ValidationReport)
        """
        import json

        # Extract special test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        request_body = {
            "prompt": prompt,
            "model": model,
            "stream": True,
            **kwargs,
        }

        events: list[dict[str, Any]] = []
        all_fields: list[FieldResult] = []
        has_errors = False

        try:
            for data in self.stream("POST", "/images/generations", json=request_body):
                if data.strip() == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    events.append(event)

                    # Validate each event against schema
                    validator = SchemaValidator(
                        provider=self.provider_name, endpoint="images/generations/stream"
                    )
                    event_report = validator.validate(event, ImageStreamEvent)
                    if not event_report.success:
                        has_errors = True
                        for f in event_report.fields:
                            if f.status != FieldStatus.VALID:
                                all_fields.append(f)
                except json.JSONDecodeError:
                    continue

            # Check if we got a completed event
            has_completed = any(
                event.get("type") == "image_generation.completed" for event in events
            )

            success = not has_errors and len(events) > 0 and has_completed

            # Create a summary report
            report = ValidationReport(
                provider=self.provider_name,
                endpoint="images/generations",
                success=success,
                total_fields=len(events),
                valid_count=len(events) - len(all_fields),
                invalid_count=len(all_fields),
                fields=all_fields,
                request_params=request_body,
                raw_response={"events": events, "event_count": len(events)},
                test_param=test_param,
                test_variant=test_variant,
            )

            return events, report
        except Exception as e:
            from llm_spec.core.report import get_collector, get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="images/generations",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_body,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)
            raise

    def validate_image_edit(
        self,
        *,
        image_path: str | Path,
        prompt: str,
        mask_path: str | Path | None = None,
        model: Literal["dall-e-2"] = "dall-e-2",
        n: int | None = None,
        size: str | None = None,
        response_format: Literal["url", "b64_json"] | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate image edit endpoint response against schema.

        Args:
            image_path: Path to image to edit (PNG, max 4MB)
            prompt: Description of desired edit
            mask_path: Optional mask image path
            model: Model to use (only dall-e-2)
            n: Number of images
            size: Output size
            response_format: Return URL or base64
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        # Extract test metadata before building request
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        image_path = Path(image_path)

        files: dict[str, Any] = {}
        with open(image_path, "rb") as img_file:
            files["image"] = (image_path.name, img_file.read(), "image/png")

        if mask_path:
            mask_path = Path(mask_path)
            with open(mask_path, "rb") as mask_file:
                files["mask"] = (mask_path.name, mask_file.read(), "image/png")

        # Build data dict - only include parameters if explicitly set
        data: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
        }
        if n is not None:
            data["n"] = str(n)
        if size is not None:
            data["size"] = size
        if response_format is not None:
            data["response_format"] = response_format
        # Add any additional kwargs
        data.update(kwargs)

        # Build request_params for tracking (using schema field names)
        request_params: dict[str, Any] = {
            "image": str(image_path),  # Schema expects 'image', not 'image_path'
            "prompt": prompt,
            "model": model,
        }
        if mask_path:
            request_params["mask"] = str(mask_path)  # Schema expects 'mask', not 'mask_path'
        if n is not None:
            request_params["n"] = n
        if size is not None:
            request_params["size"] = size
        if response_format is not None:
            request_params["response_format"] = response_format
        # Add any additional kwargs
        request_params.update(kwargs)

        try:
            response = self.request("POST", "/images/edits", data=data, files=files)

            validator = SchemaValidator(provider=self.provider_name, endpoint="images/edits")
            report = validator.validate(response, ImageResponse, request_params=request_params)
            report.test_param = test_param
            report.test_variant = test_variant
            return report
        except Exception as e:
            from llm_spec.core.report import get_collector, get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="images/edits",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_params,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)
            raise

    def validate_image_edit_stream(
        self,
        *,
        image_path: str | Path,
        prompt: str,
        mask_path: str | Path | None = None,
        model: Literal["gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"] = "gpt-image-1.5",
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], ValidationReport]:
        """Validate streaming image edit endpoint (GPT image models only)."""
        import json

        # Extract test metadata
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        image_path = Path(image_path)

        files: dict[str, Any] = {}
        with open(image_path, "rb") as img_file:
            files["image"] = (image_path.name, img_file.read(), "image/png")

        if mask_path:
            mask_path = Path(mask_path)
            with open(mask_path, "rb") as mask_file:
                files["mask"] = (mask_path.name, mask_file.read(), "image/png")

        # Build form data for streaming request
        data: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "stream": True,
        }
        # Pass through additional kwargs (e.g., partial_images, background, etc.)
        for k, v in kwargs.items():
            if v is not None:
                data[k] = v

        request_params: dict[str, Any] = {
            "image": str(image_path),
            "prompt": prompt,
            "model": model,
            "stream": True,
            **kwargs,
        }
        if mask_path:
            request_params["mask"] = str(mask_path)

        events: list[dict[str, Any]] = []
        all_fields: list[FieldResult] = []
        has_errors = False

        try:
            for line in self.stream("POST", "/images/edits", data=data, files=files):
                if line.strip() == "[DONE]":
                    break
                try:
                    event = json.loads(line)
                    events.append(event)

                    validator = SchemaValidator(
                        provider=self.provider_name, endpoint="images/edits/stream"
                    )
                    event_report = validator.validate(event, ImageStreamEvent)
                    if not event_report.success:
                        has_errors = True
                        for f in event_report.fields:
                            if f.status != FieldStatus.VALID:
                                all_fields.append(f)
                except json.JSONDecodeError:
                    continue

            has_completed = any(e.get("type") == "image_edit.completed" for e in events)
            success = not has_errors and len(events) > 0 and has_completed

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="images/edits",
                success=success,
                total_fields=len(events),
                valid_count=len(events) - len(all_fields),
                invalid_count=len(all_fields),
                fields=all_fields,
                request_params=request_params,
                raw_response={"events": events, "event_count": len(events)},
                test_param=test_param,
                test_variant=test_variant,
            )
            return events, report
        except Exception as e:
            from llm_spec.core.report import get_collector, get_current_test_name

            report = ValidationReport(
                provider=self.provider_name,
                endpoint="images/edits",
                success=False,
                total_fields=0,
                valid_count=0,
                invalid_count=0,
                fields=[],
                request_params=request_params,
                raw_response=None,
                metadata={"test_name": get_current_test_name(), "error": str(e)},
                test_param=test_param,
                test_variant=test_variant,
            )
            collector = get_collector()
            collector.add(report, test_name=get_current_test_name(), save_to_output=False)
            raise

    def validate_image_variation(
        self,
        *,
        image_path: str | Path,
        model: Literal["dall-e-2"] = "dall-e-2",
        n: int = 1,
        size: str = "256x256",
        response_format: Literal["url", "b64_json"] = "url",
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate image variation endpoint response against schema.

        Note: Only dall-e-2 supports variations.

        Args:
            image_path: Path to image (PNG, max 4MB)
            model: Model to use (only dall-e-2)
            n: Number of variations
            size: Output size
            response_format: Return URL or base64
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        # Extract test metadata before building request
        test_param = kwargs.pop("_test_param", None)
        test_variant = kwargs.pop("_test_variant", None)

        image_path = Path(image_path)

        with open(image_path, "rb") as img_file:
            files = {"image": (image_path.name, img_file.read(), "image/png")}

        data = {
            "model": model,
            "n": str(n),
            "size": size,
            "response_format": response_format,
            **kwargs,
        }

        response = self.request("POST", "/images/variations", data=data, files=files)

        validator = SchemaValidator(provider=self.provider_name, endpoint="images/variations")
        report = validator.validate(response, ImageResponse)
        report.test_param = test_param
        report.test_variant = test_variant
        return report

    # =========================================================================
    # Raw Data Methods (for pipeline tests)
    # =========================================================================

    def generate_image(
        self,
        *,
        prompt: str = "A white cat",
        model: Literal["dall-e-2", "dall-e-3"] = "dall-e-2",
        n: int = 1,
        size: str = "256x256",
        **kwargs: Any,
    ) -> tuple[bytes, ValidationReport]:
        """Generate image and return raw PNG bytes along with validation report.

        Args:
            prompt: Text description of the image
            model: Model to use
            n: Number of images to generate
            size: Image size
            **kwargs: Additional parameters

        Returns:
            Tuple of (png_bytes, ValidationReport)
        """
        request_body = {
            "prompt": prompt,
            "model": model,
            "n": n,
            "size": size,
            "response_format": "b64_json",
            **kwargs,
        }

        response = self.request("POST", "/images/generations", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="images/generations")
        report = validator.validate(response, ImageResponse)

        # Extract first image's base64 data
        b64_data = response.get("data", [{}])[0].get("b64_json", "")
        image_bytes = base64.b64decode(b64_data) if b64_data else b""

        return image_bytes, report

    def edit_image(
        self,
        *,
        image: bytes | str | Path,
        prompt: str,
        mask: bytes | str | Path | None = None,
        model: Literal["dall-e-2"] = "dall-e-2",
        n: int = 1,
        size: str = "256x256",
        **kwargs: Any,
    ) -> tuple[bytes, ValidationReport]:
        """Edit image and return raw PNG bytes along with validation report.

        Args:
            image: PNG image bytes, or path to image file
            prompt: Description of desired edit
            mask: Optional mask (PNG bytes or path)
            model: Model to use (only dall-e-2)
            n: Number of images
            size: Output size
            **kwargs: Additional parameters

        Returns:
            Tuple of (png_bytes, ValidationReport)
        """
        # Handle image input
        if isinstance(image, bytes):
            image_data = image
            image_name = "image.png"
        else:
            image_path = Path(image)
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_name = image_path.name

        files: dict[str, Any] = {
            "image": (image_name, image_data, "image/png"),
        }

        # Handle mask input
        if mask is not None:
            if isinstance(mask, bytes):
                mask_data = mask
                mask_name = "mask.png"
            else:
                mask_path = Path(mask)
                with open(mask_path, "rb") as f:
                    mask_data = f.read()
                mask_name = mask_path.name
            files["mask"] = (mask_name, mask_data, "image/png")

        data = {
            "prompt": prompt,
            "model": model,
            "n": str(n),
            "size": size,
            "response_format": "b64_json",
            **kwargs,
        }

        response = self.request("POST", "/images/edits", data=data, files=files)

        validator = SchemaValidator(provider=self.provider_name, endpoint="images/edits")
        report = validator.validate(response, ImageResponse)

        # Extract first image's base64 data
        b64_data = response.get("data", [{}])[0].get("b64_json", "")
        image_bytes = base64.b64decode(b64_data) if b64_data else b""

        return image_bytes, report

    def create_image_variation(
        self,
        *,
        image: bytes | str | Path,
        model: Literal["dall-e-2"] = "dall-e-2",
        n: int = 1,
        size: str = "256x256",
        **kwargs: Any,
    ) -> tuple[bytes, ValidationReport]:
        """Create image variation and return raw PNG bytes along with validation report.

        Args:
            image: PNG image bytes, or path to image file
            model: Model to use (only dall-e-2)
            n: Number of variations
            size: Output size
            **kwargs: Additional parameters

        Returns:
            Tuple of (png_bytes, ValidationReport)
        """
        # Handle image input
        if isinstance(image, bytes):
            image_data = image
            image_name = "image.png"
        else:
            image_path = Path(image)
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_name = image_path.name

        files = {
            "image": (image_name, image_data, "image/png"),
        }

        data = {
            "model": model,
            "n": str(n),
            "size": size,
            "response_format": "b64_json",
            **kwargs,
        }

        response = self.request("POST", "/images/variations", data=data, files=files)

        validator = SchemaValidator(provider=self.provider_name, endpoint="images/variations")
        report = validator.validate(response, ImageResponse)

        # Extract first image's base64 data
        b64_data = response.get("data", [{}])[0].get("b64_json", "")
        image_bytes = base64.b64decode(b64_data) if b64_data else b""

        return image_bytes, report

    def generate_speech(
        self,
        *,
        input_text: str = "Hello, this is a test.",
        model: Literal["tts-1", "tts-1-hd", "gpt-4o-mini-tts"] = "tts-1",
        voice: str = "alloy",
        response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3",
        **kwargs: Any,
    ) -> bytes:
        """Generate speech and return raw audio bytes.

        Args:
            input_text: Text to convert to speech
            model: TTS model to use
            voice: Voice to use
            response_format: Audio format
            **kwargs: Additional parameters

        Returns:
            Audio bytes in the specified format
        """
        request_body = {
            "model": model,
            "input": input_text,
            "voice": voice,
            "response_format": response_format,
            **kwargs,
        }

        return self.request_binary("POST", "/audio/speech", json=request_body)

    def transcribe_audio(
        self,
        *,
        audio: bytes | str | Path,
        model: Literal[
            "whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"
        ] = "whisper-1",
        response_format: Literal["json", "verbose_json"] = "json",
        **kwargs: Any,
    ) -> tuple[dict[str, Any], ValidationReport]:
        """Transcribe audio and return raw response along with validation report.

        Args:
            audio: Audio bytes, or path to audio file
            model: Transcription model
            response_format: Output format
            **kwargs: Additional parameters

        Returns:
            Tuple of (response_dict, ValidationReport)
        """
        # Handle audio input
        if isinstance(audio, bytes):
            audio_data = audio
            audio_name = "audio.mp3"
        else:
            audio_path = Path(audio)
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            audio_name = audio_path.name

        files = {"file": (audio_name, audio_data, "audio/mpeg")}
        data = {"model": model, "response_format": response_format, **kwargs}

        response = self.request("POST", "/audio/transcriptions", data=data, files=files)

        schema = (
            TranscriptionVerboseResponse
            if response_format == "verbose_json"
            else TranscriptionResponse
        )
        validator = SchemaValidator(provider=self.provider_name, endpoint="audio/transcriptions")
        report = validator.validate(response, schema)

        return response, report
