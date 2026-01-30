"""OpenAI API 参数配置"""

# Chat Completions 参数
CHAT_COMPLETIONS_PARAMS = {
    "model": {
        "type": "必需",
        "category": "core",
        "description": "使用的模型，如 gpt-4, gpt-3.5-turbo",
    },
    "messages": {
        "type": "必需",
        "category": "core",
        "description": "消息列表，包含对话历史",
    },
    "messages[].role": {
        "type": "必需",
        "category": "core",
        "description": "消息角色：system, user, assistant",
    },
    "messages[].content": {
        "type": "必需",
        "category": "core",
        "description": "消息内容",
    },
    "temperature": {
        "type": "可选",
        "category": "generation",
        "description": "采样温度，范围 0-2，默认 1",
    },
    "top_p": {
        "type": "可选",
        "category": "generation",
        "description": "核心采样参数，默认 1",
    },
    "max_tokens": {
        "type": "可选",
        "category": "generation",
        "description": "最大生成令牌数",
    },
    "frequency_penalty": {
        "type": "可选",
        "category": "generation",
        "description": "频率惩罚，范围 -2 到 2，默认 0",
    },
    "presence_penalty": {
        "type": "可选",
        "category": "generation",
        "description": "存在惩罚，范围 -2 到 2，默认 0",
    },
    "stop": {
        "type": "可选",
        "category": "generation",
        "description": "停止序列，用于终止生成",
    },
    "tools": {
        "type": "可选",
        "category": "tools",
        "description": "工具/函数定义数组",
    },
    "tools[].type": {
        "type": "必需",
        "category": "tools",
        "description": "工具类型，目前为 'function'",
    },
    "tools[].function": {
        "type": "必需",
        "category": "tools",
        "description": "函数定义对象",
    },
    "tool_choice": {
        "type": "可选",
        "category": "tools",
        "description": "工具选择策略：auto, none, required, {type:function,function:{name:...}}",
    },
    "response_format": {
        "type": "可选",
        "category": "generation",
        "description": "响应格式，如 {type: 'json_object'}",
    },
    "logit_bias": {
        "type": "可选",
        "category": "generation",
        "description": "修改特定令牌的概率",
    },
    "user": {
        "type": "可选",
        "category": "metadata",
        "description": "终端用户的唯一标识符",
    },
}

# Embeddings 参数
EMBEDDINGS_PARAMS = {
    "model": {
        "type": "必需",
        "category": "core",
        "description": "使用的嵌入模型，如 text-embedding-3-large",
    },
    "input": {
        "type": "必需",
        "category": "core",
        "description": "输入文本或文本列表",
    },
    "encoding_format": {
        "type": "可选",
        "category": "format",
        "description": "编码格式：float 或 base64，默认 float",
    },
    "dimensions": {
        "type": "可选",
        "category": "format",
        "description": "嵌入向量维度（某些模型支持）",
    },
    "user": {
        "type": "可选",
        "category": "metadata",
        "description": "终端用户的唯一标识符",
    },
}

# OpenAI 参数分类
OPENAI_PARAM_CATEGORIES = {
    "core": "核心参数",
    "generation": "生成配置",
    "tools": "工具参数",
    "format": "格式参数",
    "metadata": "元数据",
}
