from llm_spec.validation.schemas.openai.images import ImageResponse, ImageStreamEvent


def test_openai_images_response_schema_accepts_official_shape():
    payload = {
        "created": 1720000000,
        "data": [{"b64_json": "AAAA", "revised_prompt": "A cute cat"}],
        "background": "transparent",
        "output_format": "png",
        "size": "1024x1024",
        "quality": "high",
        "usage": {
            "total_tokens": 100,
            "input_tokens": 50,
            "output_tokens": 50,
            "input_tokens_details": {"text_tokens": 10, "image_tokens": 40},
        },
    }

    ImageResponse(**payload)


def test_openai_images_stream_event_partial_image_schema():
    payload = {
        "type": "image_generation.partial_image",
        "b64_json": "AAAA",
        "created_at": 1720000000,
        "size": "1024x1024",
        "quality": "high",
        "background": "transparent",
        "output_format": "png",
        "partial_image_index": 0,
    }

    ImageStreamEvent(**payload)


def test_openai_images_stream_event_completed_schema():
    payload = {
        "type": "image_generation.completed",
        "b64_json": "AAAA",
        "created_at": 1720000000,
        "size": "1024x1024",
        "quality": "high",
        "background": "transparent",
        "output_format": "png",
        "usage": {
            "total_tokens": 100,
            "input_tokens": 50,
            "output_tokens": 50,
            "input_tokens_details": {"text_tokens": 10, "image_tokens": 40},
        },
    }

    ImageStreamEvent(**payload)


def test_openai_images_stream_event_edit_types_are_accepted():
    payload = {
        "type": "image_edit.partial_image",
        "b64_json": "AAAA",
        "created_at": 1720000000,
        "size": "1024x1024",
        "quality": "high",
        "background": "transparent",
        "output_format": "png",
        "partial_image_index": 1,
    }

    ImageStreamEvent(**payload)
