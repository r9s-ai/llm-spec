"""API 参数配置 - 定义各个 API 的标准参数"""

# Gemini batchGenerateContent 参数定义
BATCH_GENERATE_CONTENT_PARAMS = {
    # 核心参数 - 必需
    "requests": {
        "type": "必需",
        "category": "core",
        "description": "请求数组，支持 1-20+ 个请求",
    },
    "requests[].contents": {
        "type": "必需",
        "category": "core",
        "description": "会话内容数组",
    },
    "requests[].contents[].parts": {
        "type": "必需",
        "category": "core",
        "description": "内容片段数组",
    },
    "requests[].contents[].parts[].text": {
        "type": "可选",
        "category": "core",
        "description": "文本内容",
    },
    # 生成配置参数
    "requests[].generationConfig": {
        "type": "可选",
        "category": "generation",
        "description": "生成配置容器",
    },
    "requests[].generationConfig.temperature": {
        "type": "可选",
        "category": "generation",
        "description": "温度参数，范围 0-2，默认 1",
    },
    "requests[].generationConfig.maxOutputTokens": {
        "type": "可选",
        "category": "generation",
        "description": "最大输出令牌数，默认 4096",
    },
    "requests[].generationConfig.topP": {
        "type": "可选",
        "category": "generation",
        "description": "核心采样参数",
    },
    "requests[].generationConfig.topK": {
        "type": "可选",
        "category": "generation",
        "description": "高频采样参数",
    },
    "requests[].generationConfig.responseMimeType": {
        "type": "可选",
        "category": "generation",
        "description": "响应格式，如 application/json",
    },
    # 内容参数 - 多模态
    "requests[].contents[].parts[].inlineData": {
        "type": "可选",
        "category": "content",
        "description": "内联数据（base64 编码）",
    },
    "requests[].contents[].parts[].inlineData.mimeType": {
        "type": "必需*",
        "category": "content",
        "description": "MIME 类型，如 image/png",
    },
    "requests[].contents[].parts[].inlineData.data": {
        "type": "必需*",
        "category": "content",
        "description": "Base64 编码的数据",
    },
    # 安全参数
    "requests[].safetySettings": {
        "type": "可选",
        "category": "safety",
        "description": "安全设置数组",
    },
    "requests[].safetySettings[].category": {
        "type": "必需*",
        "category": "safety",
        "description": "伤害类别，如 HARM_CATEGORY_HARASSMENT",
    },
    "requests[].safetySettings[].threshold": {
        "type": "必需*",
        "category": "safety",
        "description": "阈值，如 BLOCK_MEDIUM_AND_ABOVE",
    },
    # 系统指令
    "requests[].systemInstruction": {
        "type": "可选",
        "category": "instruction",
        "description": "系统指令/系统提示词",
    },
    # 工具参数
    "requests[].tools": {
        "type": "可选",
        "category": "tools",
        "description": "工具定义数组",
    },
    "requests[].tools[].functionDeclarations": {
        "type": "可选",
        "category": "tools",
        "description": "函数声明",
    },
    # 批处理配置
    "config": {
        "type": "可选",
        "category": "batch_config",
        "description": "批处理配置",
    },
    "config.displayName": {
        "type": "可选",
        "category": "batch_config",
        "description": "批任务显示名称",
    },
    "config.timeout": {
        "type": "可选",
        "category": "batch_config",
        "description": "批任务超时时间",
    },
}

# 参数分类映射
PARAM_CATEGORIES = {
    "core": "核心参数",
    "generation": "生成配置",
    "content": "内容参数",
    "safety": "安全参数",
    "instruction": "系统指令",
    "tools": "工具参数",
    "batch_config": "批配置",
}
