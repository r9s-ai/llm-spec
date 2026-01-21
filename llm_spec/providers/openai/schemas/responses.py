"""OpenAI Responses API schema definitions.

API Reference: https://platform.openai.com/docs/api-reference/responses
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class ResponseInputMessageContent(BaseModel):
    """Content item in a response input message."""

    type: Literal["input_text", "input_image", "input_file"] = Field(
        ..., description="Content type"
    )
    text: str | None = Field(default=None, description="Text content for input_text type")
    image_url: str | None = Field(default=None, description="Image URL for input_image type")
    file_id: str | None = Field(default=None, description="File ID for input_file type")


class ResponseInputMessage(BaseModel):
    """Input message for Responses API."""

    role: Literal["user", "assistant", "system", "developer"] = Field(
        ..., description="Message role"
    )
    content: str | list[ResponseInputMessageContent] = Field(..., description="Message content")
    type: Literal["message"] | None = Field(default=None, description="Message type")


# ============================================================================
# Tool Definitions
# ============================================================================


class FunctionTool(BaseModel):
    """Function tool definition."""

    type: Literal["function"] = Field(default="function", description="Tool type")
    name: str = Field(..., description="Function name")
    description: str | None = Field(default=None, description="Function description")
    parameters: dict[str, Any] | None = Field(
        default=None, description="JSON Schema for parameters"
    )
    strict: bool | None = Field(default=None, description="Enable strict schema adherence")


class WebSearchTool(BaseModel):
    """Web search tool definition."""

    type: Literal["web_search"] = Field(default="web_search", description="Tool type")


class CodeInterpreterTool(BaseModel):
    """Code interpreter tool definition."""

    type: Literal["code_interpreter"] = Field(default="code_interpreter", description="Tool type")
    container: dict[str, Any] | None = Field(default=None, description="Container configuration")


class McpTool(BaseModel):
    """MCP (Model Context Protocol) tool definition."""

    type: Literal["mcp"] = Field(default="mcp", description="Tool type")
    server_label: str = Field(..., description="Server label identifier")
    server_url: str = Field(..., description="MCP server URL")
    require_approval: Literal["never", "always"] | None = Field(default=None)
    headers: dict[str, str] | None = Field(default=None, description="Custom headers")


class ImageGenerationTool(BaseModel):
    """Image generation tool definition."""

    type: Literal["image_generation"] = Field(default="image_generation", description="Tool type")


class ReasoningConfig(BaseModel):
    """Reasoning configuration for reasoning models."""

    effort: Literal["low", "medium", "high", "none"] | str | None = Field(
        default=None, description="Reasoning effort level"
    )
    summary: str | None = Field(default=None, description="Reasoning summary")


class ResponseRequest(BaseModel):
    """Request body for POST /v1/responses."""

    model: str = Field(..., description="Model ID to use")
    input: str | list[ResponseInputMessage] = Field(..., description="Input text or messages")
    instructions: str | None = Field(default=None, description="System instructions")
    previous_response_id: str | None = Field(
        default=None, description="Previous response ID for conversation chaining"
    )
    tools: list[dict[str, Any]] | None = Field(
        default=None,
        description="Available tools (function, web_search, code_interpreter, mcp, image_generation)",
    )
    tool_choice: str | dict[str, Any] | None = Field(default=None, description="Tool choice")
    temperature: float | None = Field(default=None, ge=0, le=2, description="Sampling temperature")
    top_p: float | None = Field(default=None, ge=0, le=1, description="Nucleus sampling")
    max_output_tokens: int | None = Field(default=None, description="Maximum output tokens")
    stream: bool | None = Field(default=None, description="Enable streaming")
    store: bool | None = Field(default=None, description="Store the response (default true)")
    metadata: dict[str, str] | None = Field(default=None, description="Custom metadata")
    include: list[str] | None = Field(
        default=None, description="Additional fields to include (e.g., reasoning.encrypted_content)"
    )
    reasoning: ReasoningConfig | None = Field(default=None, description="Reasoning configuration")
    text: dict[str, Any] | None = Field(
        default=None, description="Text format configuration for structured outputs"
    )
    truncation: str | None = Field(default=None, description="Truncation strategy")
    user: str | None = Field(default=None, description="User identifier")


# ============================================================================
# Response Models
# ============================================================================


class OutputTextContent(BaseModel):
    """Text content in response output."""

    type: Literal["output_text"] = Field(default="output_text", description="Content type")
    text: str = Field(..., description="Generated text")
    annotations: list[dict[str, Any]] = Field(default_factory=list, description="Text annotations")
    logprobs: list[dict[str, Any]] | None = Field(
        default=None, description="Log probabilities for tokens"
    )


class OutputMessage(BaseModel):
    """Message output in response."""

    id: str = Field(..., description="Message ID")
    type: Literal["message"] = Field(default="message", description="Output type")
    role: Literal["assistant"] = Field(default="assistant", description="Always assistant")
    status: str | None = Field(default=None, description="Message status")
    content: list[OutputTextContent] = Field(..., description="Message content")


class FunctionCallOutput(BaseModel):
    """Function call output in response."""

    type: Literal["function_call"] = Field(default="function_call", description="Output type")
    id: str = Field(..., description="Function call ID")
    call_id: str = Field(..., description="Call ID for providing results")
    name: str = Field(..., description="Function name")
    arguments: str = Field(..., description="JSON string of arguments")
    status: str | None = Field(default=None, description="Call status")


class WebSearchCallOutput(BaseModel):
    """Web search call output in response."""

    type: Literal["web_search_call"] = Field(default="web_search_call", description="Output type")
    id: str = Field(..., description="Web search call ID")
    status: str | None = Field(default=None, description="Call status")


class FileSearchCallOutput(BaseModel):
    """File search call output in response."""

    type: Literal["file_search_call"] = Field(default="file_search_call", description="Output type")
    id: str = Field(..., description="File search call ID")
    status: str | None = Field(default=None, description="Call status")
    queries: list[str] | None = Field(default=None, description="Search queries used")
    results: list[dict[str, Any]] | None = Field(default=None, description="Search results")


class ResponseInputTokensDetails(BaseModel):
    """Detailed token breakdown for input."""

    cached_tokens: int | None = Field(default=None, description="Tokens from cache")
    audio_tokens: int | None = Field(default=None, description="Tokens used for audio")


class ResponseOutputTokensDetails(BaseModel):
    """Detailed token breakdown for output."""

    reasoning_tokens: int = Field(default=0, description="Tokens used for reasoning")
    audio_tokens: int | None = Field(default=None, description="Tokens used for audio")
    accepted_prediction_tokens: int | None = Field(default=None)
    rejected_prediction_tokens: int | None = Field(default=None)


class ResponseUsage(BaseModel):
    """Token usage for Responses API."""

    input_tokens: int = Field(..., description="Tokens in the input")
    output_tokens: int = Field(..., description="Tokens in the output")
    total_tokens: int = Field(..., description="Total tokens used")
    input_tokens_details: ResponseInputTokensDetails | None = Field(default=None)
    output_tokens_details: ResponseOutputTokensDetails | None = Field(default=None)


class ResponseObject(BaseModel):
    """Response body for POST /v1/responses (non-streaming)."""

    id: str = Field(..., description="Response ID (e.g., resp_xxx)")
    object: Literal["response"] = Field(default="response", description="Object type")
    created_at: float = Field(..., description="Unix timestamp (float)")
    model: str = Field(..., description="Model used")
    status: Literal["completed", "failed", "in_progress", "incomplete"] = Field(
        ..., description="Response status"
    )
    output: list[
        OutputMessage | FunctionCallOutput | WebSearchCallOutput | FileSearchCallOutput | dict[str, Any]
    ] = Field(..., description="Output items (messages, function calls, web search, file search, etc.)")
    output_text: str | None = Field(default=None, description="Convenience field for text output")
    usage: ResponseUsage | None = Field(default=None, description="Token usage")

    # Configuration echo
    temperature: float | None = Field(default=None)
    top_p: float | None = Field(default=None)
    max_output_tokens: int | None = Field(default=None)
    previous_response_id: str | None = Field(default=None)
    parallel_tool_calls: bool | None = Field(default=None)
    tool_choice: str | dict[str, Any] | None = Field(default=None)
    tools: list[dict[str, Any]] | None = Field(default=None)

    # Additional fields
    error: dict[str, Any] | None = Field(default=None, description="Error details if failed")
    incomplete_details: dict[str, Any] | None = Field(
        default=None, description="Details if incomplete"
    )
    instructions: str | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)
    reasoning: ReasoningConfig | dict[str, Any] | None = Field(
        default=None, description="Reasoning details"
    )
    text: dict[str, Any] | None = Field(default=None)
    truncation: str | None = Field(default=None)
    user: str | None = Field(default=None)

    # New fields (2024-2025 API updates)
    background: bool | None = Field(default=None, description="Background execution flag")
    billing: dict[str, Any] | None = Field(default=None, description="Billing information")
    completed_at: int | None = Field(default=None, description="Completion timestamp")
    content_filters: list[dict[str, Any]] | None = Field(
        default=None, description="Content filter results"
    )
    frequency_penalty: float | None = Field(default=None, description="Frequency penalty")
    presence_penalty: float | None = Field(default=None, description="Presence penalty")
    service_tier: str | None = Field(default=None, description="Service tier")
    store: bool | None = Field(default=None, description="Store flag")
    top_logprobs: int | None = Field(default=None, description="Top log probabilities count")
    max_tool_calls: int | None = Field(default=None, description="Maximum tool calls")
    prompt_cache_key: str | None = Field(default=None, description="Prompt cache key")
    prompt_cache_retention: int | None = Field(default=None, description="Prompt cache retention")
    safety_identifier: str | None = Field(default=None, description="Safety identifier")


# ============================================================================
# Streaming Models
# ============================================================================


class ResponseStreamEvent(BaseModel):
    """Base model for response stream events."""

    type: str = Field(..., description="Event type")


class ResponseCreatedEvent(ResponseStreamEvent):
    """Event when response is created."""

    type: Literal["response.created"] = Field(default="response.created")
    response: ResponseObject = Field(..., description="Initial response object")


class ResponseInProgressEvent(ResponseStreamEvent):
    """Event when response is in progress."""

    type: Literal["response.in_progress"] = Field(default="response.in_progress")
    response: ResponseObject = Field(..., description="Response object")


class ResponseCompletedEvent(ResponseStreamEvent):
    """Event when response is completed."""

    type: Literal["response.completed"] = Field(default="response.completed")
    response: ResponseObject = Field(..., description="Final response object")


class ResponseFailedEvent(ResponseStreamEvent):
    """Event when response fails."""

    type: Literal["response.failed"] = Field(default="response.failed")
    response: ResponseObject = Field(..., description="Response object with error")


class OutputItemAddedEvent(ResponseStreamEvent):
    """Event when output item is added."""

    type: Literal["response.output_item.added"] = Field(default="response.output_item.added")
    output_index: int = Field(..., description="Index of the output item")
    item: dict[str, Any] = Field(..., description="The added item")


class OutputItemDoneEvent(ResponseStreamEvent):
    """Event when output item is complete."""

    type: Literal["response.output_item.done"] = Field(default="response.output_item.done")
    output_index: int = Field(..., description="Index of the output item")
    item: dict[str, Any] = Field(..., description="The completed item")


class ContentPartAddedEvent(ResponseStreamEvent):
    """Event when content part is added."""

    type: Literal["response.content_part.added"] = Field(default="response.content_part.added")
    output_index: int = Field(..., description="Output item index")
    content_index: int = Field(..., description="Content part index")
    part: dict[str, Any] = Field(..., description="The added content part")


class ContentPartDoneEvent(ResponseStreamEvent):
    """Event when content part is complete."""

    type: Literal["response.content_part.done"] = Field(default="response.content_part.done")
    output_index: int = Field(..., description="Output item index")
    content_index: int = Field(..., description="Content part index")
    part: dict[str, Any] = Field(..., description="The completed content part")


class OutputTextDeltaEvent(ResponseStreamEvent):
    """Event for text delta in streaming."""

    type: Literal["response.output_text.delta"] = Field(default="response.output_text.delta")
    output_index: int = Field(..., description="Output item index")
    content_index: int = Field(..., description="Content part index")
    delta: str = Field(..., description="Text delta")


class OutputTextDoneEvent(ResponseStreamEvent):
    """Event when text output is complete."""

    type: Literal["response.output_text.done"] = Field(default="response.output_text.done")
    output_index: int = Field(..., description="Output item index")
    content_index: int = Field(..., description="Content part index")
    text: str = Field(..., description="Complete text")
