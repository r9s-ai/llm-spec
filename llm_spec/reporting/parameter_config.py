"""API parameter configuration: define standard parameter metadata per API."""

# Gemini batchGenerateContent parameter definitions
BATCH_GENERATE_CONTENT_PARAMS = {
    # Core params - required
    "requests": {
        "type": "Required",
        "category": "core",
        "description": "Requests array (supports ~1-20+ requests)",
    },
    "requests[].contents": {
        "type": "Required",
        "category": "core",
        "description": "Conversation contents array",
    },
    "requests[].contents[].parts": {
        "type": "Required",
        "category": "core",
        "description": "Content parts array",
    },
    "requests[].contents[].parts[].text": {
        "type": "Optional",
        "category": "core",
        "description": "Text content",
    },
    # Generation config params
    "requests[].generationConfig": {
        "type": "Optional",
        "category": "generation",
        "description": "Generation config container",
    },
    "requests[].generationConfig.temperature": {
        "type": "Optional",
        "category": "generation",
        "description": "Sampling temperature (0-2, default 1)",
    },
    "requests[].generationConfig.maxOutputTokens": {
        "type": "Optional",
        "category": "generation",
        "description": "Max output tokens (default 4096)",
    },
    "requests[].generationConfig.topP": {
        "type": "Optional",
        "category": "generation",
        "description": "Top-p sampling parameter",
    },
    "requests[].generationConfig.topK": {
        "type": "Optional",
        "category": "generation",
        "description": "Top-k sampling parameter",
    },
    "requests[].generationConfig.responseMimeType": {
        "type": "Optional",
        "category": "generation",
        "description": "Response MIME type (e.g. application/json)",
    },
    # Content params - multimodal
    "requests[].contents[].parts[].inlineData": {
        "type": "Optional",
        "category": "content",
        "description": "Inline data (base64-encoded)",
    },
    "requests[].contents[].parts[].inlineData.mimeType": {
        "type": "Required*",
        "category": "content",
        "description": "MIME type (e.g. image/png)",
    },
    "requests[].contents[].parts[].inlineData.data": {
        "type": "Required*",
        "category": "content",
        "description": "Base64-encoded data",
    },
    # Safety params
    "requests[].safetySettings": {
        "type": "Optional",
        "category": "safety",
        "description": "Safety settings array",
    },
    "requests[].safetySettings[].category": {
        "type": "Required*",
        "category": "safety",
        "description": "Harm category (e.g. HARM_CATEGORY_HARASSMENT)",
    },
    "requests[].safetySettings[].threshold": {
        "type": "Required*",
        "category": "safety",
        "description": "Threshold (e.g. BLOCK_MEDIUM_AND_ABOVE)",
    },
    # System instruction
    "requests[].systemInstruction": {
        "type": "Optional",
        "category": "instruction",
        "description": "System instruction / system prompt",
    },
    # Tool params
    "requests[].tools": {
        "type": "Optional",
        "category": "tools",
        "description": "Tool definitions array",
    },
    "requests[].tools[].functionDeclarations": {
        "type": "Optional",
        "category": "tools",
        "description": "Function declarations",
    },
    # Batch config
    "config": {
        "type": "Optional",
        "category": "batch_config",
        "description": "Batch config",
    },
    "config.displayName": {
        "type": "Optional",
        "category": "batch_config",
        "description": "Batch display name",
    },
    "config.timeout": {
        "type": "Optional",
        "category": "batch_config",
        "description": "Batch timeout",
    },
}

# Parameter category mapping
PARAM_CATEGORIES = {
    "core": "Core",
    "generation": "Generation",
    "content": "Content",
    "safety": "Safety",
    "instruction": "System",
    "tools": "Tools",
    "batch_config": "Batch",
}
