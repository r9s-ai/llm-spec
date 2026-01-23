"""OpenAI Images API schema definitions.

API Reference:
- Images: https://platform.openai.com/docs/api-reference/images
- Image Streaming: https://platform.openai.com/docs/api-reference/images-streaming
- Generations: /v1/images/generations
- Edits: /v1/images/edits
- Variations: /v1/images/variations (DALL-E 2 only)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# Image Generation Models
# ============================================================================


class ImageGenerationRequest(BaseModel):
    """Request body for POST /v1/images/generations.

    Generates images from a text prompt.
    """

    prompt: str = Field(
        ...,
        description="Text description of the desired image. Max 1000 chars for dall-e-2, 32000 for GPT image models",
    )
    model: Literal[
        "dall-e-2", "dall-e-3", "gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"
    ] | None = Field(default=None, description="Model to use. Default: dall-e-2")
    n: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Number of images to generate. 1-10, dall-e-3 only supports 1",
    )
    quality: Literal["standard", "hd", "high", "medium", "low", "auto"] | None = Field(
        default=None,
        description="Image quality. 'hd' for dall-e-3, 'high/medium/low/auto' for GPT image models",
    )
    response_format: Literal["url", "b64_json"] | None = Field(
        default=None,
        description="Output format. Only for dall-e-2/3. GPT image models always return b64_json",
    )
    size: Literal[
        "256x256",
        "512x512",
        "1024x1024",
        "1792x1024",
        "1024x1792",
        "1536x1024",
        "1024x1536",
        "auto",
    ] | None = Field(
        default=None,
        description="Image size. dall-e-2: 256/512/1024. dall-e-3: 1024/1792x1024/1024x1792. GPT: 1024/1536x1024/1024x1536/auto",
    )
    style: Literal["vivid", "natural"] | None = Field(
        default=None, description="Style for dall-e-3 only. Default: vivid"
    )
    user: str | None = Field(default=None, description="Unique user identifier")
    # GPT image model specific
    output_format: Literal["png", "jpeg", "webp"] | None = Field(
        default=None, description="Output format for GPT image models only"
    )
    background: Literal["transparent", "opaque", "auto"] | None = Field(
        default=None, description="Background transparency for GPT image models only"
    )
    output_compression: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Compression level 0-100% for GPT image models with webp/jpeg",
    )
    moderation: Literal["low", "auto"] | None = Field(
        default=None, description="Moderation level for GPT image models"
    )
    stream: bool | None = Field(
        default=None, description="Generate the image in streaming mode. GPT image models only"
    )
    partial_images: int | None = Field(
        default=None,
        ge=0,
        le=3,
        description="Number of partial images for streaming. 0-3. GPT image models only",
    )


class ImageEditRequest(BaseModel):
    """Request body for POST /v1/images/edits.

    Edits or extends an existing image.
    Note: This is a multipart/form-data request.
    """

    image: str | list[str] = Field(
        ...,
        description="Image file(s) to edit. GPT models: up to 16 images, <50MB each. dall-e-2: 1 square PNG <4MB",
    )
    prompt: str = Field(
        ...,
        description="Description of desired edit. Max 1000 chars for dall-e-2, 32000 for GPT models",
    )
    model: Literal["dall-e-2", "gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5"] | None = Field(
        default=None, description="Model to use"
    )
    mask: str | None = Field(
        default=None,
        description="PNG file with transparent areas indicating where to edit. Must match image dimensions",
    )
    n: int | None = Field(default=None, ge=1, le=10, description="Number of images to generate")
    size: Literal[
        "256x256", "512x512", "1024x1024", "1536x1024", "1024x1536", "auto"
    ] | None = Field(default=None, description="Output image size")
    response_format: Literal["url", "b64_json"] | None = Field(
        default=None, description="Output format. Only for dall-e-2"
    )
    user: str | None = Field(default=None, description="Unique user identifier")
    # GPT image model specific
    quality: Literal["high", "medium", "low", "auto"] | None = Field(
        default=None, description="Image quality for GPT image models"
    )
    output_format: Literal["png", "jpeg", "webp"] | None = Field(
        default=None, description="Output format for GPT image models"
    )
    background: Literal["transparent", "opaque", "auto"] | None = Field(
        default=None, description="Background transparency for GPT image models"
    )
    output_compression: int | None = Field(
        default=None, ge=0, le=100, description="Compression level for webp/jpeg"
    )
    input_fidelity: Literal["high", "low"] | None = Field(
        default=None,
        description="How closely to match input image style/features. gpt-image-1 only",
    )
    # Streaming
    stream: bool | None = Field(default=None, description="Enable streaming mode")
    partial_images: int | None = Field(
        default=None,
        ge=0,
        le=3,
        description="Number of partial images for streaming. 0 = single final image",
    )


class ImageVariationRequest(BaseModel):
    """Request body for POST /v1/images/variations.

    Generates variations of an existing image.
    Note: This is a multipart/form-data request.
    Note: Only supported by dall-e-2.
    """

    image: str = Field(..., description="PNG image file to create variations of. Max 4MB")
    model: Literal["dall-e-2"] | None = Field(
        default=None, description="Model to use. Only dall-e-2 supported"
    )
    n: int | None = Field(default=None, ge=1, le=10, description="Number of variations")
    response_format: Literal["url", "b64_json"] | None = Field(
        default=None, description="Output format"
    )
    size: Literal["256x256", "512x512", "1024x1024"] | None = Field(
        default=None, description="Output size"
    )
    user: str | None = Field(default=None, description="Unique user identifier")


# ============================================================================
# Response Models
# ============================================================================


class ImageData(BaseModel):
    """Single image data in response."""

    b64_json: str | None = Field(default=None, description="Base64-encoded image data")
    url: str | None = Field(
        default=None, description="URL to download image. Valid for 60 minutes"
    )
    revised_prompt: str | None = Field(
        default=None, description="The prompt that was used to generate the image (dall-e-3)"
    )


class ImageUsageDetails(BaseModel):
    """Detailed token usage breakdown for images."""

    image_tokens: int = Field(default=0, description="Tokens for image processing")
    text_tokens: int = Field(default=0, description="Tokens for text processing")


class ImageUsage(BaseModel):
    """Token usage for GPT image models."""

    input_tokens: int = Field(..., description="Input tokens used")
    input_tokens_details: ImageUsageDetails | None = Field(default=None)
    output_tokens: int = Field(..., description="Output tokens used")
    total_tokens: int = Field(..., description="Total tokens used")


class ImageResponse(BaseModel):
    """Response for image generation/edit/variation endpoints."""

    created: int = Field(..., description="Unix timestamp of creation")
    data: list[ImageData] = Field(..., description="List of generated images")
    usage: ImageUsage | None = Field(
        default=None, description="Token usage. Only for GPT image models"
    )


# ============================================================================
# Streaming Response Models (GPT image models only)
# https://platform.openai.com/docs/api-reference/images-streaming
# ============================================================================


class ImageGenerationPartialImageEvent(BaseModel):
    """Emitted when a partial image is available during image generation streaming.

    Event type: image_generation.partial_image
    """

    type: Literal["image_generation.partial_image"] = Field(
        default="image_generation.partial_image", description="Event type"
    )
    b64_json: str = Field(..., description="Base64-encoded partial image data")
    created_at: int = Field(..., description="Unix timestamp when the event was created")
    partial_image_index: int = Field(..., description="0-based index for the partial image")
    background: Literal["transparent", "opaque", "auto"] | None = Field(
        default=None, description="Background setting for the requested image"
    )
    output_format: Literal["png", "jpeg", "webp"] | None = Field(
        default=None, description="Output format for the requested image"
    )
    quality: Literal["high", "medium", "low", "auto"] | None = Field(
        default=None, description="Quality setting for the requested image"
    )
    size: str | None = Field(default=None, description="Size of the requested image")


class ImageGenerationCompletedEvent(BaseModel):
    """Emitted when image generation has completed and the final image is available.

    Event type: image_generation.completed
    """

    type: Literal["image_generation.completed"] = Field(
        default="image_generation.completed", description="Event type"
    )
    b64_json: str = Field(..., description="Base64-encoded final image data")
    created_at: int = Field(..., description="Unix timestamp when the event was created")
    background: Literal["transparent", "opaque", "auto"] | None = Field(
        default=None, description="Background setting for the generated image"
    )
    output_format: Literal["png", "jpeg", "webp"] | None = Field(
        default=None, description="Output format for the generated image"
    )
    quality: Literal["high", "medium", "low", "auto"] | None = Field(
        default=None, description="Quality setting for the generated image"
    )
    size: str | None = Field(default=None, description="Size of the generated image")
    usage: ImageUsage | None = Field(
        default=None, description="Token usage information (GPT image models only)"
    )


class ImageEditPartialImageEvent(BaseModel):
    """Emitted when a partial image is available during image editing streaming.

    Event type: image_edit.partial_image
    """

    type: Literal["image_edit.partial_image"] = Field(
        default="image_edit.partial_image", description="Event type"
    )
    b64_json: str = Field(..., description="Base64-encoded partial image data")
    created_at: int = Field(..., description="Unix timestamp when the event was created")
    partial_image_index: int = Field(..., description="0-based index for the partial image")
    background: Literal["transparent", "opaque", "auto"] | None = Field(default=None)
    output_format: Literal["png", "jpeg", "webp"] | None = Field(default=None)
    quality: Literal["high", "medium", "low", "auto"] | None = Field(default=None)
    size: str | None = Field(default=None)


class ImageEditCompletedEvent(BaseModel):
    """Emitted when image editing has completed and the final image is available.

    Event type: image_edit.completed
    """

    type: Literal["image_edit.completed"] = Field(
        default="image_edit.completed", description="Event type"
    )
    b64_json: str = Field(..., description="Base64-encoded final image data")
    created_at: int = Field(..., description="Unix timestamp when the event was created")
    background: Literal["transparent", "opaque", "auto"] | None = Field(default=None)
    output_format: Literal["png", "jpeg", "webp"] | None = Field(default=None)
    quality: Literal["high", "medium", "low", "auto"] | None = Field(default=None)
    size: str | None = Field(default=None)
    usage: ImageUsage | None = Field(default=None, description="Token usage information")


# Union type for all image streaming events
ImageStreamEvent = (
    ImageGenerationPartialImageEvent
    | ImageGenerationCompletedEvent
    | ImageEditPartialImageEvent
    | ImageEditCompletedEvent
)
