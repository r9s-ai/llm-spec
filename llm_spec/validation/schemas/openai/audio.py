"""OpenAI Audio API Pydantic schemas.

Reference: OpenAI API Reference (Audio):
- /v1/audio/speech streaming events: speech.audio.delta / speech.audio.done
- /v1/audio/transcriptions streaming events: transcript.text.delta / segment / done
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, RootModel


class AudioUsageDuration(BaseModel):
    """Usage for duration-billed variants (e.g. verbose_json whisper)."""

    type: Literal["duration"]
    seconds: float


class AudioUsageTokensInputDetails(BaseModel):
    text_tokens: int | None = None
    audio_tokens: int | None = None


class AudioUsageTokens(BaseModel):
    """Usage for token-billed variants (gpt-* transcribe/tts)."""

    type: Literal["tokens"] | None = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_token_details: AudioUsageTokensInputDetails | None = None


class AudioLogprob(BaseModel):
    token: str
    logprob: float
    bytes: list[int] | None = None


class AudioTranscriptJSON(BaseModel):
    """Non-streaming transcription/translation JSON shape.

    Notes:
    - response_format=json: { "text": ... }
    - response_format=verbose_json: includes many more fields but still contains text.
    - Some variants include usage (tokens or duration), depending on model/billing.
    """

    text: str
    task: str | None = None
    language: str | None = None
    duration: float | None = None
    segments: list[dict[str, Any]] | None = None
    words: list[dict[str, Any]] | None = None
    logprobs: list[AudioLogprob] | None = None
    usage: AudioUsageTokens | AudioUsageDuration | dict[str, Any] | None = None


class AudioTranscriptionResponse(RootModel[AudioTranscriptJSON | str]):
    """Audio Transcription response.

    Supports:
    - JSON object (default)
    - plain text response (response_format=text/vtt/srt)
    """


class AudioTranslationResponse(RootModel[AudioTranscriptJSON | str]):
    """Audio Translation response.

    Supports:
    - JSON object (response_format=json/verbose_json)
    - plain text response (response_format=text/vtt/srt)
    """


class AudioSpeechResponse(BaseModel):
    """Audio Speech response model (binary audio; no schema validation needed)."""

    pass


class SpeechAudioDeltaEvent(BaseModel):
    type: Literal["speech.audio.delta"]
    audio: str


class SpeechAudioDoneEvent(BaseModel):
    type: Literal["speech.audio.done"]
    usage: dict[str, Any] | AudioUsageTokens | None = None


class TranscriptTextDeltaEvent(BaseModel):
    type: Literal["transcript.text.delta"]
    delta: str
    logprobs: list[AudioLogprob] | None = None
    segment_id: str | None = None


class TranscriptTextSegmentEvent(BaseModel):
    type: Literal["transcript.text.segment"]
    id: str
    start: float
    end: float
    text: str
    speaker: str


class TranscriptTextDoneEvent(BaseModel):
    type: Literal["transcript.text.done"]
    text: str
    logprobs: list[AudioLogprob] | None = None
    usage: AudioUsageTokens | dict[str, Any] | None = None


class AudioStreamEvent(
    RootModel[
        SpeechAudioDeltaEvent
        | SpeechAudioDoneEvent
        | TranscriptTextDeltaEvent
        | TranscriptTextSegmentEvent
        | TranscriptTextDoneEvent
    ]
):
    """Union of OpenAI Audio SSE events.

    Notes:
    - /v1/audio/speech with stream_format=sse emits speech.audio.*
    - /v1/audio/transcriptions with stream=true emits transcript.text.*
    """


# Backward-compatible alias (older configs may reference this name)
class TranscriptionStreamEvent(AudioStreamEvent):
    pass
