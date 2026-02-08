"""Anthropic API parameter configuration (metadata)."""

# Messages params
MESSAGES_PARAMS = {
    "model": {
        "type": "Required",
        "category": "core",
        "description": "Model name (e.g. claude-3-opus-20240229)",
    },
    "messages": {
        "type": "Required",
        "category": "core",
        "description": "Message list (conversation history)",
    },
    "messages[].role": {
        "type": "Required",
        "category": "core",
        "description": "Message role: user or assistant",
    },
    "messages[].content": {
        "type": "Required",
        "category": "core",
        "description": "Message content (text or list of content blocks)",
    },
    "max_tokens": {
        "type": "Required",
        "category": "generation",
        "description": "Max generated tokens",
    },
    "temperature": {
        "type": "Optional",
        "category": "generation",
        "description": "Sampling temperature (0-1, default 1)",
    },
    "top_p": {
        "type": "Optional",
        "category": "generation",
        "description": "Top-p sampling (0-1)",
    },
    "top_k": {
        "type": "Optional",
        "category": "generation",
        "description": "Top-k sampling",
    },
    "stop_sequences": {
        "type": "Optional",
        "category": "generation",
        "description": "Stop sequence list",
    },
    "system": {
        "type": "Optional",
        "category": "system",
        "description": "System prompt / system instruction",
    },
    "tools": {
        "type": "Optional",
        "category": "tools",
        "description": "Tool/function definition list",
    },
    "tools[].name": {
        "type": "Required",
        "category": "tools",
        "description": "Tool name",
    },
    "tools[].description": {
        "type": "Optional",
        "category": "tools",
        "description": "Tool description",
    },
    "tools[].input_schema": {
        "type": "Required",
        "category": "tools",
        "description": "Tool input JSON Schema",
    },
    "tool_choice": {
        "type": "Optional",
        "category": "tools",
        "description": "Tool selection: auto, any, tool {...}",
    },
    "thinking": {
        "type": "Optional",
        "category": "reasoning",
        "description": "Enable thinking mode (extended reasoning)",
    },
    "thinking.type": {
        "type": "Required",
        "category": "reasoning",
        "description": "Thinking type: enabled",
    },
    "thinking.budget_tokens": {
        "type": "Optional",
        "category": "reasoning",
        "description": "Token budget for thinking",
    },
}

# Anthropic param categories
ANTHROPIC_PARAM_CATEGORIES = {
    "core": "Core",
    "generation": "Generation",
    "system": "System",
    "tools": "Tools",
    "reasoning": "Reasoning",
}
