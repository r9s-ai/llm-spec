"""OpenAI API client implementation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Literal

from llm_spec.core import config as global_config
from llm_spec.core.client import BaseClient
from llm_spec.core.config import ProviderConfig
from llm_spec.core.report import ValidationReport
from llm_spec.core.validator import SchemaValidator
from llm_spec.providers.openai.schemas import (
    ChatCompletionResponse,
    EmbeddingResponse,
    ImageResponse,
    ResponseObject,
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
        headers = {"Content-Type": "application/json"}
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

        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": 10,
            **kwargs,
        }

        response = self.request("POST", "/chat/completions", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="chat/completions")
        return validator.validate(response, ChatCompletionResponse)

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
        request_body = {
            "model": model,
            "input": input_text,
            **kwargs,
        }

        response = self.request("POST", "/embeddings", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="embeddings")
        return validator.validate(response, EmbeddingResponse)

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
        # Determine input
        if input_messages is not None:
            input_value: str | list[dict[str, Any]] = input_messages
        elif input_text is not None:
            input_value = input_text
        else:
            input_value = "Say 'test' and nothing else."

        request_body: dict[str, Any] = {
            "model": model,
            "input": input_value,
            **kwargs,
        }

        if instructions is not None:
            request_body["instructions"] = instructions
        if tools is not None:
            request_body["tools"] = tools

        response = self.request("POST", "/responses", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="responses")
        return validator.validate(response, ResponseObject)

    def validate_responses_stream(
        self,
        *,
        model: str = "gpt-4o-mini",
        input_text: str | None = None,
        input_messages: list[dict[str, Any]] | None = None,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], bool]:
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

        return events, has_completed and has_basic_events

    # =========================================================================
    # Audio API
    # =========================================================================

    def validate_speech(
        self,
        *,
        model: Literal["tts-1", "tts-1-hd", "gpt-4o-mini-tts"] = "tts-1",
        input_text: str = "Hello, this is a test.",
        voice: str = "alloy",
        **kwargs: Any,
    ) -> tuple[bytes, bool]:
        """Validate speech (TTS) endpoint.

        Note: Speech API returns binary audio data, not JSON.
        Returns the audio bytes and a boolean indicating if the response
        appears to be valid audio data.

        Args:
            model: TTS model to use
            input_text: Text to convert to speech
            voice: Voice to use
            **kwargs: Additional parameters

        Returns:
            Tuple of (audio_bytes, is_valid)
        """
        request_body = {
            "model": model,
            "input": input_text,
            "voice": voice,
            **kwargs,
        }

        audio_data = self.request_binary("POST", "/audio/speech", json=request_body)

        # Basic validation: check if we got non-empty binary data
        is_valid = len(audio_data) > 0
        return audio_data, is_valid

    def validate_transcription(
        self,
        *,
        file_path: str | Path,
        model: Literal[
            "whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"
        ] = "whisper-1",
        response_format: Literal["json", "verbose_json"] = "json",
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate transcription endpoint response against schema.

        Args:
            file_path: Path to audio file to transcribe
            model: Transcription model to use
            response_format: Output format (json or verbose_json)
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        file_path = Path(file_path)

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "audio/mpeg")}
            data = {"model": model, "response_format": response_format, **kwargs}

            response = self.request("POST", "/audio/transcriptions", data=data, files=files)

        schema = (
            TranscriptionVerboseResponse
            if response_format == "verbose_json"
            else TranscriptionResponse
        )
        validator = SchemaValidator(provider=self.provider_name, endpoint="audio/transcriptions")
        return validator.validate(response, schema)

    def validate_translation(
        self,
        *,
        file_path: str | Path,
        model: Literal["whisper-1"] = "whisper-1",
        response_format: Literal["json", "verbose_json"] = "json",
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
        file_path = Path(file_path)

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "audio/mpeg")}
            data = {"model": model, "response_format": response_format, **kwargs}

            response = self.request("POST", "/audio/translations", data=data, files=files)

        schema = (
            TranslationVerboseResponse
            if response_format == "verbose_json"
            else TranslationResponse
        )
        validator = SchemaValidator(provider=self.provider_name, endpoint="audio/translations")
        return validator.validate(response, schema)

    # =========================================================================
    # Images API
    # =========================================================================

    def validate_image_generation(
        self,
        *,
        prompt: str = "A white cat",
        model: Literal["dall-e-2", "dall-e-3"] = "dall-e-2",
        n: int = 1,
        size: str = "256x256",
        response_format: Literal["url", "b64_json"] = "url",
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
        request_body = {
            "prompt": prompt,
            "model": model,
            "n": n,
            "size": size,
            "response_format": response_format,
            **kwargs,
        }

        response = self.request("POST", "/images/generations", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="images/generations")
        return validator.validate(response, ImageResponse)

    def validate_image_edit(
        self,
        *,
        image_path: str | Path,
        prompt: str,
        mask_path: str | Path | None = None,
        model: Literal["dall-e-2"] = "dall-e-2",
        n: int = 1,
        size: str = "256x256",
        response_format: Literal["url", "b64_json"] = "url",
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
        image_path = Path(image_path)

        files: dict[str, Any] = {}
        with open(image_path, "rb") as img_file:
            files["image"] = (image_path.name, img_file.read(), "image/png")

        if mask_path:
            mask_path = Path(mask_path)
            with open(mask_path, "rb") as mask_file:
                files["mask"] = (mask_path.name, mask_file.read(), "image/png")

        data = {
            "prompt": prompt,
            "model": model,
            "n": str(n),
            "size": size,
            "response_format": response_format,
            **kwargs,
        }

        response = self.request("POST", "/images/edits", data=data, files=files)

        validator = SchemaValidator(provider=self.provider_name, endpoint="images/edits")
        return validator.validate(response, ImageResponse)

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
        return validator.validate(response, ImageResponse)

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
