"""OpenAI Images API Pydantic schemas

Reference:
- Non-streaming Images responses include fields such as `background/output_format/size/quality/usage`
- Images Streaming events: `image_generation.*` / `image_edit.*`
"""

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class ImageData(BaseModel):
    """A single image item."""

    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageUsage(BaseModel):
    """Images token usage (only returned by some models/requests)."""

    total_tokens: int
    input_tokens: int
    output_tokens: int
    input_tokens_details: dict[str, Any] | None = None
    output_tokens_details: dict[str, Any] | None = None


class ImageResponse(BaseModel):
    """Images response model."""

    created: int
    data: list[ImageData]
    background: str | None = None
    output_format: str | None = None
    size: str | None = None
    quality: str | None = None
    usage: ImageUsage | None = None


class ImageStreamEvent(BaseModel):
    """OpenAI /v1/images/* streaming event (SSE JSON 'data: {...}').

    Supported event types (per OpenAI API Reference):
    - image_generation.partial_image
    - image_generation.completed
    - image_edit.partial_image
    - image_edit.completed
    """

    type: Literal[
        "image_generation.partial_image",
        "image_generation.completed",
        "image_edit.partial_image",
        "image_edit.completed",
    ]

    # Common fields
    b64_json: str | None = None
    created_at: int | None = None
    size: str | None = None
    quality: str | None = None
    background: str | None = None
    output_format: str | None = None

    # Partial-only
    partial_image_index: int | None = None

    # Completed-only (optional in docs; present for some models)
    usage: ImageUsage | None = None

    @model_validator(mode="after")
    def _validate_required_fields_by_type(self) -> "ImageStreamEvent":
        required_common = [
            ("b64_json", self.b64_json),
            ("created_at", self.created_at),
            ("size", self.size),
            ("quality", self.quality),
            ("background", self.background),
            ("output_format", self.output_format),
        ]

        if self.type.endswith(".partial_image"):
            missing = [name for name, val in required_common if val is None]
            if self.partial_image_index is None:
                missing.append("partial_image_index")
            if missing:
                raise ValueError(f"{self.type} missing required field(s): {', '.join(missing)}")
            return self

        # completed events
        missing = [name for name, val in required_common if val is None]
        if missing:
            raise ValueError(f"{self.type} missing required field(s): {', '.join(missing)}")
        return self
