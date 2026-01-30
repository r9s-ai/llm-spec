"""Anthropic API 参数配置"""

# Messages 参数
MESSAGES_PARAMS = {
    "model": {
        "type": "必需",
        "category": "core",
        "description": "使用的模型，如 claude-3-opus-20240229",
    },
    "messages": {
        "type": "必需",
        "category": "core",
        "description": "消息列表，包含对话历史",
    },
    "messages[].role": {
        "type": "必需",
        "category": "core",
        "description": "消息角色：user 或 assistant",
    },
    "messages[].content": {
        "type": "必需",
        "category": "core",
        "description": "消息内容，可以是文本或内容块数组",
    },
    "max_tokens": {
        "type": "必需",
        "category": "generation",
        "description": "最大生成令牌数",
    },
    "temperature": {
        "type": "可选",
        "category": "generation",
        "description": "采样温度，范围 0-1，默认 1",
    },
    "top_p": {
        "type": "可选",
        "category": "generation",
        "description": "核心采样参数，范围 0-1",
    },
    "top_k": {
        "type": "可选",
        "category": "generation",
        "description": "高频采样参数",
    },
    "stop_sequences": {
        "type": "可选",
        "category": "generation",
        "description": "停止序列数组",
    },
    "system": {
        "type": "可选",
        "category": "system",
        "description": "系统提示词/系统指令",
    },
    "tools": {
        "type": "可选",
        "category": "tools",
        "description": "工具/函数定义数组",
    },
    "tools[].name": {
        "type": "必需",
        "category": "tools",
        "description": "工具名称",
    },
    "tools[].description": {
        "type": "可选",
        "category": "tools",
        "description": "工具描述",
    },
    "tools[].input_schema": {
        "type": "必需",
        "category": "tools",
        "description": "工具输入 JSON Schema",
    },
    "tool_choice": {
        "type": "可选",
        "category": "tools",
        "description": "工具选择策略：auto, any, tool {...}",
    },
    "thinking": {
        "type": "可选",
        "category": "reasoning",
        "description": "启用思考模式（扩展思考）",
    },
    "thinking.type": {
        "type": "必需",
        "category": "reasoning",
        "description": "思考类型：enabled",
    },
    "thinking.budget_tokens": {
        "type": "可选",
        "category": "reasoning",
        "description": "分配给思考的令牌数",
    },
}

# Anthropic 参数分类
ANTHROPIC_PARAM_CATEGORIES = {
    "core": "核心参数",
    "generation": "生成配置",
    "system": "系统提示",
    "tools": "工具参数",
    "reasoning": "推理参数",
}
