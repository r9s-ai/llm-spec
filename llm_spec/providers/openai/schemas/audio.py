"""OpenAI Audio API schema definitions.

API Reference: https://platform.openai.com/docs/api-reference/audio
- Speech (TTS): /v1/audio/speech
- Transcriptions: /v1/audio/transcriptions
- Translations: /v1/audio/translations
"""

from __future__ import annotations

from typing import Any, Literal

import pydantic
from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Speech (Text-to-Speech) Models
# ============================================================================


class SpeechRequest(BaseModel):
    """Request body for POST /v1/audio/speech.

    Generates audio from the input text.
    """

    model: Literal["tts-1", "tts-1-hd", "gpt-4o-mini-tts", "gpt-4o-mini-tts-2025-12-15"] = Field(
        ..., description="TTS model to use"
    )
    input: str = Field(..., description="The text to generate audio for", max_length=4096)
    voice: str | dict[str, str] = Field(
        ...,
        description="Voice to use. Built-in: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar. Or custom voice object with 'id'",
    )
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] | None = Field(
        default=None, description="Audio output format. Default: mp3"
    )
    speed: float | None = Field(
        default=None, ge=0.25, le=4.0, description="Speed of audio. Range: 0.25-4.0. Default: 1.0"
    )
    instructions: str | None = Field(
        default=None,
        description="Instructions for voice style. Not supported for tts-1 or tts-1-hd",
    )
    stream_format: Literal["sse", "audio"] | None = Field(
        default=None,
        description="The format to stream the audio in. sse is not supported for tts-1 or tts-1-hd. Default: audio",
    )


# Speech response is binary audio data, no JSON schema needed


# ============================================================================
# Transcription Models
# ============================================================================


class ServerVadConfig(BaseModel):
    """Server-side Voice Activity Detection configuration."""

    type: Literal["server_vad"] = Field(default="server_vad")
    threshold: float | None = Field(
        default=None, ge=0, le=1, description="VAD threshold. Default: 0.5"
    )
    prefix_padding_ms: int | None = Field(
        default=None, description="Padding before speech in milliseconds"
    )
    silence_duration_ms: int | None = Field(
        default=None, description="Silence duration to end speech in milliseconds"
    )


class TranscriptionRequest(BaseModel):
    """Request body for POST /v1/audio/transcriptions.

    Transcribes audio into the input language.
    Note: This is a multipart/form-data request, not JSON.
    """

    # Required fields
    file: str = Field(
        ...,
        description="Audio file path. Formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm",
    )
    model: Literal[
        "whisper-1",
        "gpt-4o-transcribe",
        "gpt-4o-mini-transcribe",
        "gpt-4o-mini-transcribe-2025-12-15",
        "gpt-4o-transcribe-diarize",
    ] = Field(..., description="Transcription model to use")

    # Optional fields
    language: str | None = Field(
        default=None, description="Input audio language in ISO-639-1 format (e.g., 'en')"
    )
    prompt: str | None = Field(
        default=None,
        description="Optional text to guide the model's style or continue a previous segment",
    )
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt", "diarized_json"] | None = Field(
        default=None,
        description="Output format. whisper-1 supports all; gpt-4o models support json/text; diarize model uses diarized_json",
    )
    temperature: float | None = Field(
        default=None, ge=0, le=1, description="Sampling temperature between 0 and 1"
    )
    timestamp_granularities: list[Literal["word", "segment"]] | None = Field(
        default=None,
        description="Timestamp granularities. Requires response_format=verbose_json",
    )
    stream: bool | None = Field(default=None, description="Enable streaming transcription")
    chunking_strategy: Literal["auto"] | ServerVadConfig | None = Field(
        default=None,
        description="How to chunk audio. 'auto' uses VAD. Required for diarize model with >30s audio",
    )
    include: list[Literal["logprobs"]] | None = Field(
        default=None,
        description="Additional data to include. logprobs requires response_format=json",
    )
    known_speaker_names: list[str] | None = Field(
        default=None, description="Optional list of speaker names for diarization. Up to 4 speakers."
    )
    known_speaker_references: list[str] | None = Field(
        default=None,
        description="Optional list of audio samples (data URLs) matching known_speaker_names.",
    )

    @pydantic.model_validator(mode="after")
    def validate_constraints(self) -> TranscriptionRequest:
        """Validate parameter constraints according to official docs."""
        # 1. response_format constraints
        if self.model in ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]:
            if self.response_format and self.response_format != "json":
                raise ValueError(f"Model {self.model} only supports response_format='json'")
        
        if self.model == "gpt-4o-transcribe-diarize":
            if self.response_format and self.response_format not in ["json", "text", "diarized_json"]:
                raise ValueError(f"Model {self.model} only supports 'json', 'text', or 'diarized_json'")

        # 2. include constraints
        if self.include:
            if self.response_format != "json":
                raise ValueError("'include' only works with response_format='json'")
            if self.model not in ["gpt-4o-transcribe", "gpt-4o-mini-transcribe", "gpt-4o-mini-transcribe-2025-12-15"]:
                raise ValueError(f"'include' is not supported for model {self.model}")

        # 3. stream constraints
        if self.stream and self.model == "whisper-1":
            # Note: Docs say "ignored", but we can warn or validate
            pass 

        # 4. prompt constraints
        if self.prompt and self.model == "gpt-4o-transcribe-diarize":
            raise ValueError("'prompt' is not supported for gpt-4o-transcribe-diarize")

        # 5. timestamp_granularities constraints
        if self.timestamp_granularities:
            if self.response_format != "verbose_json":
                raise ValueError("'timestamp_granularities' requires response_format='verbose_json'")
            if self.model == "gpt-4o-transcribe-diarize":
                raise ValueError("'timestamp_granularities' not available for diarize model")
        
        # 6. speaker diarization constraints
        if self.known_speaker_names and len(self.known_speaker_names) > 4:
            raise ValueError("Up to 4 known_speaker_names are supported")
            
        return self


class TranscriptionWord(BaseModel):
    """Word-level transcription with timestamp."""

    word: str = Field(..., description="The transcribed word")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")


class TranscriptionSegment(BaseModel):
    """Segment-level transcription with timestamp."""

    id: int = Field(..., description="Segment ID")
    seek: int = Field(..., description="Seek position")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Segment text")
    tokens: list[int] = Field(..., description="Token IDs")
    temperature: float = Field(..., description="Temperature used")
    avg_logprob: float = Field(..., description="Average log probability")
    compression_ratio: float = Field(..., description="Compression ratio")
    no_speech_prob: float = Field(..., description="Probability of no speech")


class AudioUsage(BaseModel):
    """Usage statistics for audio requests."""

    type: str | None = Field(default=None, description="Usage type, usually 'duration'")
    seconds: float | None = Field(default=None, description="Audio duration in seconds")


class TranscriptionResponse(BaseModel):
    """Response for POST /v1/audio/transcriptions (json format)."""

    text: str = Field(..., description="The transcribed text")
    usage: AudioUsage | None = Field(default=None, description="Usage statistics")


class TranscriptionVerboseResponse(BaseModel):
    """Response for POST /v1/audio/transcriptions (verbose_json format)."""

    task: str = Field(..., description="Task type, always 'transcribe'")
    language: str = Field(..., description="Detected language")
    duration: float = Field(..., description="Audio duration in seconds")
    text: str = Field(..., description="The transcribed text")
    words: list[TranscriptionWord] | None = Field(
        default=None, description="Word-level timestamps if requested"
    )
    segments: list[TranscriptionSegment] | None = Field(
        default=None, description="Segment-level timestamps"
    )
    usage: AudioUsage | None = Field(default=None, description="Usage statistics")


class DiarizedSegment(BaseModel):
    """Segment with speaker diarization."""

    id: str = Field(..., description="Unique segment identifier")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Segment text")
    speaker: str = Field(..., description="Speaker label")


class TranscriptionDiarizedResponse(BaseModel):
    """Response for POST /v1/audio/transcriptions (diarized_json format)."""

    text: str = Field(..., description="Concatenated transcript text")
    duration: float = Field(..., description="Audio duration in seconds")
    segments: list[DiarizedSegment] = Field(..., description="Speaker-labeled segments")
    usage: AudioUsage | None = Field(default=None, description="Usage statistics")


# ============================================================================
# Translation Models
# ============================================================================


class TranslationRequest(BaseModel):
    """Request body for POST /v1/audio/translations.

    Translates audio into English.
    Note: This is a multipart/form-data request, not JSON.
    """

    file: str = Field(
        ...,
        description="Audio file path. Formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm",
    )
    model: Literal["whisper-1"] = Field(..., description="Model to use. Only whisper-1 supported")
    prompt: str | None = Field(
        default=None, description="Optional text to guide the model's style"
    )
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] | None = Field(
        default=None, description="Output format"
    )
    temperature: float | None = Field(
        default=None, ge=0, le=1, description="Sampling temperature"
    )


class TranslationResponse(BaseModel):
    """Response for POST /v1/audio/translations."""

    text: str = Field(..., description="The translated text in English")
    usage: AudioUsage | None = Field(default=None, description="Usage statistics")


class TranslationVerboseResponse(BaseModel):
    """Response for POST /v1/audio/translations (verbose_json format)."""

    task: str = Field(..., description="Task type, always 'translate'")
    language: str = Field(..., description="Detected source language")
    duration: float = Field(..., description="Audio duration in seconds")
    text: str = Field(..., description="The translated text in English")
    segments: list[TranscriptionSegment] | None = Field(
        default=None, description="Segment-level data"
    )
    usage: AudioUsage | None = Field(default=None, description="Usage statistics")
