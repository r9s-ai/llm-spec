"""OpenAI Responses API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel

# ============================================================================
# Token Usage Model
# ============================================================================


class ResponseUsage(BaseModel):
    """Token usage statistics"""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_tokens_details: dict[str, Any] | None = None
    output_tokens_details: dict[str, Any] | None = None


# ============================================================================
# Non-streaming Response Model
# ============================================================================


class ResponseObject(BaseModel):
    """Response API non-streaming response model"""

    id: str
    object: Literal["response"]
    created_at: int
    model: str
    status: str | None = None
    background: bool | None = None
    completed_at: int | None = None
    conversation: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    output: list[dict[str, Any]]  # Flexible for polymorphic output items
    output_text: str | None = None
    prompt: dict[str, Any] | None = None
    usage: ResponseUsage | None = None
    metadata: dict[str, str] | None = None
    service_tier: str | None = None
    store: bool | None = None
    # Additional fields from actual response
    billing: dict[str, Any] | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    instructions: str | list[Any] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    text: dict[str, Any] | None = None
    reasoning: dict[str, Any] | None = None
    truncation: str | None = None
    previous_response_id: str | None = None
    prompt_cache_key: str | None = None
    prompt_cache_retention: str | None = None
    safety_identifier: str | None = None
    user: str | None = None
    incomplete_details: dict[str, Any] | None = None
    top_logprobs: int | None = None


# A lighter-weight response snapshot used in streaming events like response.queued/in_progress,
# where the API may omit fields such as `output`.
class ResponseSnapshot(BaseModel):
    id: str
    object: Literal["response"] | str | None = "response"
    status: str | None = None
    created_at: int | str | None = None
    updated_at: int | str | None = None
    completed_at: int | str | None = None
    model: str | None = None
    output: list[dict[str, Any]] | None = None
    usage: ResponseUsage | None = None


# ============================================================================
# Streaming Response Model
# ============================================================================


class ResponseChunkObject(BaseModel):
    """Response API streaming chunk model"""

    id: str
    object: Literal["response.chunk"]
    created: int
    model: str
    delta: dict[str, Any] | None = None  # Incremental changes
    usage: ResponseUsage | None = None  # Only in final chunk
    metadata: dict[str, str] | None = None
    system_fingerprint: str | None = None


# ============================================================================
# Streaming Event Model (SSE JSON events for /v1/responses)
# ============================================================================


class ResponseOutputItem(BaseModel):
    """Responses SSE output item (minimal shape).

    Note: /v1/responses streaming emits polymorphic output items (message/reasoning/tool_call/...).
    We only require id + type here and allow extra fields.
    """

    id: str
    type: str


class ResponseContentPart(BaseModel):
    """Responses SSE content part (minimal shape).

    For text output this is typically {type:"output_text", text:"..."}.
    """

    type: str
    text: str | None = None
    annotations: list[dict[str, Any]] | None = None


class ResponsesStreamEvent(BaseModel):
    """OpenAI /v1/responses streaming event chunk (SSE JSON 'data: {...}').

    Real streams are event-shaped objects with a required top-level `type` (e.g. response.created,
    response.output_text.delta) plus event-specific fields.
    This schema keeps required fields minimal (type) while still modeling common fields we validate/log.
    """

    type: str
    sequence_number: int | None = None
    event_id: str | None = None
    response_id: str | None = None

    # Events that carry a full response snapshot (created/in_progress/completed)
    response: ResponseObject | ResponseSnapshot | None = None

    # Output item lifecycle events (output_item.added/done)
    item: ResponseOutputItem | None = None
    output_index: int | None = None

    # Message content events (content_part.added/done, output_text.*)
    item_id: str | None = None
    content_index: int | None = None
    part: ResponseContentPart | None = None

    # Text / reasoning / refusal streaming events
    delta: Any | None = None
    text: str | None = None
    refusal: str | None = None
    logprobs: list[Any] | None = None
    obfuscation: str | None = None

    # Tool call argument streaming events
    call_id: str | None = None
    name: str | None = None
    arguments: str | None = None
    input: Any | None = None

    # Image generation call events (may appear in /v1/responses streams)
    b64_json: str | None = None
    partial_image_index: int | None = None

    # Error payload for response.failed / error events
    error: dict[str, Any] | None = None
