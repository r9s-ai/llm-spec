import httpx

from llm_spec.validation.schemas.openai.audio import (
    AudioStreamEvent,
    AudioTranscriptionResponse,
    AudioTranscriptJSON,
    AudioTranslationResponse,
    TranscriptSegment,
    TranscriptWord,
)
from llm_spec.validation.validator import ResponseValidator

# ---------------------------------------------------------------------------
# AudioTranscriptionResponse
# ---------------------------------------------------------------------------


def test_openai_audio_transcription_response_accepts_json():
    payload = {"text": "hello", "language": "en"}
    AudioTranscriptionResponse.model_validate(payload)


def test_openai_audio_transcription_response_accepts_plain_text():
    payload = "hello"
    AudioTranscriptionResponse.model_validate(payload)


def test_openai_audio_transcription_response_verbose_json():
    """verbose_json format includes duration, language, segments, etc."""
    payload = {
        "task": "transcribe",
        "language": "english",
        "duration": 1.52,
        "text": "Hello, how are you?",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 1.52,
                "text": "Hello, how are you?",
                "tokens": [50364, 2425, 11, 577, 366, 291, 30, 50440],
                "temperature": 0.0,
                "avg_logprob": -0.2345,
                "compression_ratio": 0.85,
                "no_speech_prob": 0.012,
            }
        ],
        "words": [
            {"word": "Hello,", "start": 0.0, "end": 0.32},
            {"word": "how", "start": 0.34, "end": 0.56},
        ],
    }
    resp = AudioTranscriptionResponse.model_validate(payload)
    obj = resp.root
    assert isinstance(obj, AudioTranscriptJSON)
    assert obj.text == "Hello, how are you?"
    assert obj.duration == 1.52
    assert obj.language == "english"
    assert obj.segments is not None
    assert len(obj.segments) == 1
    assert obj.words is not None
    assert len(obj.words) == 2


def test_openai_audio_transcription_response_with_logprobs():
    payload = {
        "text": "hello",
        "logprobs": [
            {"token": "hello", "logprob": -0.05, "bytes": [104, 101, 108, 108, 111]},
        ],
    }
    resp = AudioTranscriptionResponse.model_validate(payload)
    assert isinstance(resp.root, AudioTranscriptJSON)
    assert resp.root.logprobs is not None
    assert resp.root.logprobs[0].token == "hello"


# ---------------------------------------------------------------------------
# AudioTranslationResponse
# ---------------------------------------------------------------------------


def test_openai_audio_translation_response_accepts_json():
    payload = {"text": "Hello, how are you?"}
    AudioTranslationResponse.model_validate(payload)


def test_openai_audio_translation_response_accepts_plain_text():
    AudioTranslationResponse.model_validate("Hello, how are you?")


def test_openai_audio_translation_response_verbose_json():
    payload = {
        "task": "translate",
        "language": "english",
        "duration": 1.52,
        "text": "Hello, how are you?",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 1.52,
                "text": "Hello, how are you?",
                "tokens": [50364, 2425],
                "temperature": 0.0,
                "avg_logprob": -0.30,
                "compression_ratio": 0.82,
                "no_speech_prob": 0.015,
            }
        ],
    }
    resp = AudioTranslationResponse.model_validate(payload)
    assert isinstance(resp.root, AudioTranscriptJSON)
    assert resp.root.task == "translate"
    assert resp.root.duration == 1.52


# ---------------------------------------------------------------------------
# TranscriptSegment / TranscriptWord
# ---------------------------------------------------------------------------


def test_transcript_segment_model():
    seg = TranscriptSegment.model_validate(
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 1.52,
            "text": "Hello",
            "tokens": [50364, 2425],
            "temperature": 0.0,
            "avg_logprob": -0.23,
            "compression_ratio": 0.85,
            "no_speech_prob": 0.01,
        }
    )
    assert seg.text == "Hello"
    assert seg.no_speech_prob == 0.01


def test_transcript_word_model():
    word = TranscriptWord.model_validate({"word": "Hello,", "start": 0.0, "end": 0.32})
    assert word.word == "Hello,"
    assert word.end == 0.32


# ---------------------------------------------------------------------------
# SSE Stream Events
# ---------------------------------------------------------------------------


def test_openai_audio_sse_event_speech_audio_delta():
    payload = {"type": "speech.audio.delta", "audio": "AAAA"}
    AudioStreamEvent.model_validate(payload)


def test_openai_audio_sse_event_speech_audio_done():
    payload = {
        "type": "speech.audio.done",
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    }
    AudioStreamEvent.model_validate(payload)


def test_openai_audio_sse_event_transcript_text_delta():
    payload = {"type": "transcript.text.delta", "delta": "hel"}
    AudioStreamEvent.model_validate(payload)


def test_openai_audio_sse_event_transcript_text_segment_with_speaker():
    """Segment event with speaker field set (diarization mode)."""
    payload = {
        "type": "transcript.text.segment",
        "id": "seg_0",
        "start": 0.0,
        "end": 1.5,
        "text": "Hello",
        "speaker": "speaker_a",
    }
    AudioStreamEvent.model_validate(payload)


def test_openai_audio_sse_event_transcript_text_segment_without_speaker():
    """Segment event without speaker field (non-diarization mode)."""
    payload = {
        "type": "transcript.text.segment",
        "id": "seg_0",
        "start": 0.0,
        "end": 1.5,
        "text": "Hello",
    }
    AudioStreamEvent.model_validate(payload)


def test_openai_audio_sse_event_transcript_text_done():
    payload = {
        "type": "transcript.text.done",
        "text": "hello",
        "usage": {
            "type": "tokens",
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "input_token_details": {"text_tokens": 2, "audio_tokens": 8},
        },
    }
    AudioStreamEvent.model_validate(payload)


# ---------------------------------------------------------------------------
# ResponseValidator integration
# ---------------------------------------------------------------------------


def test_response_validator_falls_back_to_text_for_root_models():
    resp = httpx.Response(
        200, content=b"hello", headers={"content-type": "text/plain; charset=utf-8"}
    )
    result = ResponseValidator.validate_response(resp, AudioTranscriptionResponse)
    assert result.is_valid
