"""API 参数配置注册表 - 管理所有 API 的参数定义"""

# API 参数配置注册表
# 格式: "endpoint_key": {"module": "...", "params_var": "...", "categories_var": "..."}
# endpoint_key 用于在 endpoint 中匹配，可以是完整路径或部分路径

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
    """根据 endpoint 查找对应的 API 配置

    Args:
        endpoint: API 端点路径，如 "/v1beta/models/gemini-3-flash-preview:batchGenerateContent"

    Returns:
        API 配置字典，如果未找到则返回 None
    """
    for endpoint_key, config in API_PARAMETER_CONFIGS.items():
        if not config.get("enabled", False):
            # 跳过未启用的配置
            continue

        if endpoint_key in endpoint:
            return config

    return None


def get_all_enabled_apis() -> list[str]:
    """获取所有已启用的 API"""
    return [
        key
        for key, config in API_PARAMETER_CONFIGS.items()
        if config.get("enabled", False)
    ]
