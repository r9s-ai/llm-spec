import httpx

from llm_spec.validation.schemas.openai.audio import AudioStreamEvent, AudioTranscriptionResponse
from llm_spec.validation.validator import ResponseValidator


def test_openai_audio_transcription_response_accepts_json():
    payload = {"text": "hello", "language": "en"}
    AudioTranscriptionResponse.model_validate(payload)


def test_openai_audio_transcription_response_accepts_plain_text():
    payload = "hello"
    AudioTranscriptionResponse.model_validate(payload)


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


def test_response_validator_falls_back_to_text_for_root_models():
    resp = httpx.Response(
        200, content=b"hello", headers={"content-type": "text/plain; charset=utf-8"}
    )
    result = ResponseValidator.validate_response(resp, AudioTranscriptionResponse)
    assert result.is_valid
