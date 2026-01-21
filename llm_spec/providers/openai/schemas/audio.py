"""OpenAI Audio API schema definitions.

API Reference: https://platform.openai.com/docs/api-reference/audio
- Speech (TTS): /v1/audio/speech
- Transcriptions: /v1/audio/transcriptions
- Translations: /v1/audio/translations
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Speech (Text-to-Speech) Models
# ============================================================================


class SpeechRequest(BaseModel):
    """Request body for POST /v1/audio/speech.

    Generates audio from the input text.
    """

    model: Literal["tts-1", "tts-1-hd", "gpt-4o-mini-tts"] = Field(
        ..., description="TTS model to use"
    )
    input: str = Field(..., description="The text to generate audio for", max_length=4096)
    voice: str | dict[str, str] = Field(
        ...,
        description="Voice to use. Built-in: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse. Or custom voice object with 'id'",
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


class TranscriptionResponse(BaseModel):
    """Response for POST /v1/audio/transcriptions (json format)."""

    text: str = Field(..., description="The transcribed text")


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


class TranslationVerboseResponse(BaseModel):
    """Response for POST /v1/audio/translations (verbose_json format)."""

    task: str = Field(..., description="Task type, always 'translate'")
    language: str = Field(..., description="Detected source language")
    duration: float = Field(..., description="Audio duration in seconds")
    text: str = Field(..., description="The translated text in English")
    segments: list[TranscriptionSegment] | None = Field(
        default=None, description="Segment-level data"
    )
