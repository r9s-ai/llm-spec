# Gemini API OpenAPI 规范文档

本目录包含 Google Gemini API 的 OpenAPI 3.1.0 格式规范文档。

## 📋 文件列表

| 文件 | 端点 | 描述 |
|------|------|------|
| [gemini-generate-content.yaml](./gemini-generate-content.yaml) | `/models/{model}:generateContent` | 文本生成、多模态理解、函数调用 |
| [gemini-stream-generate-content.yaml](./gemini-stream-generate-content.yaml) | `/models/{model}:streamGenerateContent` | 流式内容生成（SSE） |
| [gemini-embed-content.yaml](./gemini-embed-content.yaml) | `/models/{model}:embedContent`<br>`/models/{model}:batchEmbedContents` | 嵌入向量生成 |
| [gemini-count-tokens.yaml](./gemini-count-tokens.yaml) | `/models/{model}:countTokens` | Token计数 |

---

## 🚀 GenerateContent API

**文件**: `gemini-generate-content.yaml`

### 核心功能
- ✅ 文本生成
- ✅ 多模态输入（文本、图片、视频、音频、PDF）
- ✅ 多轮对话
- ✅ 函数调用（Function Calling）
- ✅ 代码执行（Code Execution）
- ✅ JSON模式输出（Structured Output）
- ✅ 安全设置（Safety Settings）
- ✅ 系统指令（System Instruction）
- ✅ 流式响应（Streaming）

### 主要Schema
- `GenerateContentRequest` - 请求体
- `GenerateContentResponse` - 响应体
- `Content` - 内容结构
- `Part` - 内容部分（文本、图片、函数调用等）
- `Tool` - 工具定义
- `GenerationConfig` - 生成配置
- `SafetySetting` - 安全设置

### 示例请求

**简单文本生成**:
```bash
POST /v1beta/models/gemini-pro:generateContent
Content-Type: application/json
x-goog-api-key: {API_KEY}

{
  "contents": [{
    "parts": [{
      "text": "Write a poem about the ocean"
    }]
  }],
  "generationConfig": {
    "temperature": 0.9,
    "topP": 0.95,
    "maxOutputTokens": 1024
  }
}
```

**函数调用**:
```json
{
  "contents": [{
    "parts": [{
      "text": "What's the weather in San Francisco?"
    }]
  }],
  "tools": [{
    "functionDeclarations": [{
      "name": "get_weather",
      "description": "Get current weather",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        },
        "required": ["location"]
      }
    }]
  }]
}
```

---

## 🌊 StreamGenerateContent API

**文件**: `gemini-stream-generate-content.yaml`

### 核心功能
- ✅ 流式文本生成（逐token输出）
- ✅ 多模态理解流式输出（图片/视频分析的文字结果）
- ✅ 函数调用参数逐步构建
- ✅ 代码执行结果流式返回
- ✅ JSON模式流式输出
- ✅ 降低首字延迟（TTFB）
- ❌ 不支持图片生成流式（图片必须使用非流式API）

### 响应格式
使用 **Server-Sent Events (SSE)** 格式：

```
data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}

data: {"candidates":[{"content":{"parts":[{"text":" world"}]}}]}

data: {"candidates":[{"content":{"parts":[{"text":"!"}],"finishReason":"STOP"}],"usageMetadata":{"totalTokenCount":8}}]
```

### 主要Schema
- `GenerateContentRequest` - 请求体（与非流式相同）
- `StreamChunk` - 流式数据块（增量的 GenerateContentResponse）

### 示例请求

**基础流式文本生成**:
```bash
POST /v1beta/models/gemini-pro:streamGenerateContent
Content-Type: application/json
x-goog-api-key: {API_KEY}

{
  "contents": [{
    "parts": [{
      "text": "Write a short story about a robot"
    }]
  }]
}
```

**流式函数调用**:
```json
{
  "contents": [{
    "parts": [{
      "text": "What's the weather in Tokyo?"
    }]
  }],
  "tools": [{
    "functionDeclarations": [{
      "name": "get_weather",
      "description": "Get weather",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        }
      }
    }]
  }]
}
```

**流式图片分析**:
```json
{
  "contents": [{
    "parts": [
      {
        "text": "Describe this image in detail"
      },
      {
        "inlineData": {
          "mimeType": "image/jpeg",
          "data": "<base64_encoded_image>"
        }
      }
    ]
  }]
}
```

### 与非流式API的差异

| 特性 | generateContent | streamGenerateContent |
|------|----------------|---------------------|
| 响应方式 | 一次性完整响应 | SSE 流式分块响应 |
| Content-Type | application/json | text/event-stream |
| 每次返回 | 完整结果 | 增量内容 |
| 使用场景 | 短内容、批处理 | 长内容、实时展示 |
| 首字延迟 | 较高（等待全部生成） | 很低（立即返回首个token） |
| 函数调用 | 完整JSON | JSON逐步构建 |

---

## 📊 EmbedContent API

**文件**: `gemini-embed-content.yaml`

### 核心功能
- ✅ 文本嵌入
- ✅ 9种任务类型优化
- ✅ 自定义输出维度
- ✅ 批量嵌入

### 任务类型（TaskType）
- `RETRIEVAL_QUERY` - 检索查询
- `RETRIEVAL_DOCUMENT` - 检索文档
- `SEMANTIC_SIMILARITY` - 语义相似度
- `CLASSIFICATION` - 分类
- `CLUSTERING` - 聚类
- `QUESTION_ANSWERING` - 问答
- `FACT_VERIFICATION` - 事实验证
- `CODE_RETRIEVAL_QUERY` - 代码检索查询

### 示例请求

**检索查询**:
```bash
POST /v1beta/models/text-embedding-004:embedContent
Content-Type: application/json
x-goog-api-key: {API_KEY}

{
  "content": {
    "parts": [{
      "text": "How to bake a chocolate cake?"
    }]
  },
  "taskType": "RETRIEVAL_QUERY"
}
```

**检索文档（带标题）**:
```json
{
  "content": {
    "parts": [{
      "text": "A chocolate cake is a cake flavored with melted chocolate..."
    }]
  },
  "taskType": "RETRIEVAL_DOCUMENT",
  "title": "Chocolate Cake Recipe"
}
```

**自定义维度**:
```json
{
  "content": {
    "parts": [{
      "text": "Machine learning is a subset of AI"
    }]
  },
  "taskType": "SEMANTIC_SIMILARITY",
  "outputDimensionality": 256
}
```

---

## 🔢 CountTokens API

**文件**: `gemini-count-tokens.yaml`

### 核心功能
- ✅ 计算输入内容的token数
- ✅ 支持多轮对话
- ✅ 支持系统指令
- ✅ 支持工具定义
- ✅ 按模态分类统计（文本、图片、视频、音频）
- ✅ 缓存内容token统计

### 主要Schema
- `CountTokensRequest` - 请求体
- `CountTokensResponse` - 响应体
  - `totalTokens` - 总token数
  - `promptTokensDetails` - 按模态分类的详情
  - `cachedContentTokenCount` - 缓存token数
  - `cacheTokensDetails` - 缓存详情

### 示例请求

**简单文本**:
```bash
POST /v1beta/models/gemini-pro:countTokens
Content-Type: application/json
x-goog-api-key: {API_KEY}

{
  "contents": [{
    "parts": [{
      "text": "Hello, how many tokens is this?"
    }]
  }]
}
```

**多轮对话**:
```json
{
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "What is the capital of France?"}]
    },
    {
      "role": "model",
      "parts": [{"text": "The capital of France is Paris."}]
    },
    {
      "role": "user",
      "parts": [{"text": "What about Germany?"}]
    }
  ]
}
```

**带工具定义**:
```json
{
  "contents": [{
    "parts": [{"text": "What's the weather?"}]
  }],
  "tools": [{
    "functionDeclarations": [{
      "name": "get_weather",
      "description": "Get current weather",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        }
      }
    }]
  }]
}
```

---

## 🔐 认证方式

所有Gemini API端点使用 **x-goog-api-key Header** 认证：

```bash
x-goog-api-key: YOUR_API_KEY
```

完整请求示例：
```bash
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent
Content-Type: application/json
x-goog-api-key: YOUR_API_KEY

{
  "contents": [{
    "parts": [{"text": "Hello"}]
  }]
}
```

---

## 🛠️ 使用工具

### 1. OpenAPI在线编辑器
将YAML文件导入到以下工具查看和测试：
- [Swagger Editor](https://editor.swagger.io/)
- [Stoplight Studio](https://stoplight.io/studio)
- [Redocly](https://redocly.com/)

### 2. 生成客户端SDK
使用OpenAPI Generator生成各语言SDK：

```bash
# 安装 openapi-generator-cli
npm install @openapitools/openapi-generator-cli -g

# 生成Python SDK
openapi-generator-cli generate \
  -i gemini-generate-content.yaml \
  -g python \
  -o ./sdk/python

# 生成TypeScript SDK
openapi-generator-cli generate \
  -i gemini-generate-content.yaml \
  -g typescript-axios \
  -o ./sdk/typescript
```

### 3. API文档生成
使用Redoc生成美观的API文档：

```bash
# 安装 redoc-cli
npm install -g redoc-cli

# 生成HTML文档
redoc-cli bundle gemini-generate-content.yaml \
  -o gemini-generate-content.html
```

---

## 📚 参考资料

- [Google Gemini API官方文档](https://ai.google.dev/docs)
- [OpenAPI 3.1.0规范](https://spec.openapis.org/oas/v3.1.0)
- [项目测试代码](../../tests/gemini/)
- [项目Schema定义](../../llm_spec/validation/schemas/gemini/)

---

## 📝 更新日志

### 2026-01-28
- ✅ 创建GenerateContent API规范（14个示例）
- ✅ 创建StreamGenerateContent API规范（12个流式示例）
- ✅ 创建EmbedContent API规范
- ✅ 创建CountTokens API规范
- ✅ 所有规范符合OpenAPI 3.1.0标准
- ✅ 包含完整的Schema定义和示例
- ✅ 认证方式改为 x-goog-api-key header
- ✅ 添加 license 字段

---

## 🤝 贡献

这些OpenAPI规范基于项目中的Pydantic Schema定义和实际测试生成。
如发现错误或需要补充，请提交Issue或PR。

---

## 📄 许可证

MIT License
