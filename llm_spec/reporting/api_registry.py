"""API parameter config registry."""

# API parameter configs
# Shape: "endpoint_key": {"module": "...", "params_var": "...", "categories_var": "..."}
# endpoint_key is matched as a substring of the endpoint (can be full or partial path).

API_PARAMETER_CONFIGS = {
    # Gemini batchGenerateContent
    "batchGenerateContent": {
        "provider": "gemini",
        "api_name": "Batch Generate Content",
        "module": "llm_spec.reporting.parameter_config",
        "params_var": "BATCH_GENERATE_CONTENT_PARAMS",
        "categories_var": "PARAM_CATEGORIES",
        "enabled": True,
    },
    # OpenAI Chat Completions
    "chat/completions": {
        "provider": "openai",
        "api_name": "Chat Completions",
        "module": "llm_spec.reporting.openai_params",
        "params_var": "CHAT_COMPLETIONS_PARAMS",
        "categories_var": "OPENAI_PARAM_CATEGORIES",
        "enabled": True,
    },
    # OpenAI Embeddings
    "embeddings": {
        "provider": "openai",
        "api_name": "Embeddings",
        "module": "llm_spec.reporting.openai_params",
        "params_var": "EMBEDDINGS_PARAMS",
        "categories_var": "OPENAI_PARAM_CATEGORIES",
        "enabled": True,
    },
    # Anthropic Messages
    "messages": {
        "provider": "anthropic",
        "api_name": "Messages",
        "module": "llm_spec.reporting.anthropic_params",
        "params_var": "MESSAGES_PARAMS",
        "categories_var": "ANTHROPIC_PARAM_CATEGORIES",
        "enabled": True,
    },
}


def find_api_config(endpoint: str) -> dict | None:
    """Find API config by endpoint.

    Args:
        endpoint: API endpoint path, e.g. "/v1beta/models/...:batchGenerateContent"

    Returns:
        Config dict if found, otherwise None.
    """
    for endpoint_key, config in API_PARAMETER_CONFIGS.items():
        if not config.get("enabled", False):
            # Skip disabled configs
            continue

        if endpoint_key in endpoint:
            return config

    return None


def get_all_enabled_apis() -> list[str]:
    """Return all enabled API keys."""
    return [key for key, config in API_PARAMETER_CONFIGS.items() if config.get("enabled", False)]
