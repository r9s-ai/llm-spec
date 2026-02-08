"""OpenAI API parameter configuration (metadata)."""

# Chat Completions params
CHAT_COMPLETIONS_PARAMS = {
    "model": {
        "type": "Required",
        "category": "core",
        "description": "Model name (e.g. gpt-4, gpt-3.5-turbo)",
    },
    "messages": {
        "type": "Required",
        "category": "core",
        "description": "Message list (conversation history)",
    },
    "messages[].role": {
        "type": "Required",
        "category": "core",
        "description": "Message role: system, user, assistant",
    },
    "messages[].content": {
        "type": "Required",
        "category": "core",
        "description": "Message content",
    },
    "temperature": {
        "type": "Optional",
        "category": "generation",
        "description": "Sampling temperature (0-2, default 1)",
    },
    "top_p": {
        "type": "Optional",
        "category": "generation",
        "description": "Top-p sampling (default 1)",
    },
    "max_tokens": {
        "type": "Optional",
        "category": "generation",
        "description": "Max generated tokens",
    },
    "frequency_penalty": {
        "type": "Optional",
        "category": "generation",
        "description": "Frequency penalty (-2 to 2, default 0)",
    },
    "presence_penalty": {
        "type": "Optional",
        "category": "generation",
        "description": "Presence penalty (-2 to 2, default 0)",
    },
    "stop": {
        "type": "Optional",
        "category": "generation",
        "description": "Stop sequence(s) to terminate generation",
    },
    "tools": {
        "type": "Optional",
        "category": "tools",
        "description": "Tool/function definition list",
    },
    "tools[].type": {
        "type": "Required",
        "category": "tools",
        "description": "Tool type (currently 'function')",
    },
    "tools[].function": {
        "type": "Required",
        "category": "tools",
        "description": "Function definition object",
    },
    "tool_choice": {
        "type": "Optional",
        "category": "tools",
        "description": "Tool selection: auto, none, required, {type:function,function:{name:...}}",
    },
    "response_format": {
        "type": "Optional",
        "category": "generation",
        "description": "Response format (e.g. {type: 'json_object'})",
    },
    "logit_bias": {
        "type": "Optional",
        "category": "generation",
        "description": "Modify likelihood for specific tokens",
    },
    "user": {
        "type": "Optional",
        "category": "metadata",
        "description": "End-user identifier",
    },
}

# Embeddings params
EMBEDDINGS_PARAMS = {
    "model": {
        "type": "Required",
        "category": "core",
        "description": "Embedding model name (e.g. text-embedding-3-large)",
    },
    "input": {
        "type": "Required",
        "category": "core",
        "description": "Input text or list of texts",
    },
    "encoding_format": {
        "type": "Optional",
        "category": "format",
        "description": "Encoding format: float or base64 (default float)",
    },
    "dimensions": {
        "type": "Optional",
        "category": "format",
        "description": "Embedding vector dimensions (model-dependent)",
    },
    "user": {
        "type": "Optional",
        "category": "metadata",
        "description": "End-user identifier",
    },
}

# OpenAI parameter categories
OPENAI_PARAM_CATEGORIES = {
    "core": "Core",
    "generation": "Generation",
    "tools": "Tools",
    "format": "Format",
    "metadata": "Metadata",
}
