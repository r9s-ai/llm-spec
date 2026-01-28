# Anthropic Claude API OpenAPI 规范文档

本目录包含 Anthropic Claude API 的 OpenAPI 3.1.0 格式规范文档。

## 📋 文件列表

| 文件 | 端点 | 描述 |
|------|------|------|
| [messages-api.yaml](./messages-api.yaml) | `POST /v1/messages` | Messages API（标准响应） |
| [messages-streaming.yaml](./messages-streaming.yaml) | `POST /v1/messages` (streaming) | Messages API（流式响应） |

---

## 💬 Messages API

**文件**: `messages-api.yaml`

### 核心功能
- ✅ 多轮对话
- ✅ 系统提示（System Prompt）
- ✅ 多模态输入（文本 + 图片）
- ✅ 工具调用（Tool Use）
- ✅ 思考模式（Extended Thinking）- Claude 3.7+
- ✅ Prompt Caching
- ✅ 采样参数（temperature, top_p, top_k）
- ✅ 停止序列

### 认证方式
使用 `x-api-key` header：

```bash
x-api-key: sk-ant-xxxxx
```

### 必需 Headers
```bash
x-api-key: {YOUR_API_KEY}
anthropic-version: 2023-06-01
Content-Type: application/json
```

### 主要 Schema
- `MessagesRequest` - 请求体
- `MessagesResponse` - 响应体
- `Message` - 消息结构
- `ContentBlock` - 内容块（文本、图片、工具使用、工具结果）
- `Tool` - 工具定义
- `ToolChoice` - 工具选择策略
- `Usage` - Token使用统计

### 示例请求

**简单对话**:
```bash
POST /v1/messages
x-api-key: sk-ant-xxxxx
anthropic-version: 2023-06-01
Content-Type: application/json

{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": "Hello, Claude!"
    }
  ]
}
```

**带系统提示**:
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "system": "You are a helpful assistant specialized in programming.",
  "messages": [
    {
      "role": "user",
      "content": "How do I reverse a string in Python?"
    }
  ]
}
```

**多轮对话**:
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": "What is the capital of France?"
    },
    {
      "role": "assistant",
      "content": "The capital of France is Paris."
    },
    {
      "role": "user",
      "content": "What about Germany?"
    }
  ]
}
```

**图片输入**:
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUg..."
          }
        },
        {
          "type": "text",
          "text": "What do you see in this image?"
        }
      ]
    }
  ]
}
```

**工具调用**:
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "tools": [
    {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "input_schema": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "City name"
          }
        },
        "required": ["location"]
      }
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "What's the weather in San Francisco?"
    }
  ]
}
```

**思考模式（Extended Thinking）**:
```json
{
  "model": "claude-3-7-sonnet-20250219",
  "max_tokens": 4096,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 2000
  },
  "messages": [
    {
      "role": "user",
      "content": "Solve this complex problem step by step..."
    }
  ]
}
```

### 响应格式

**成功响应**:
```json
{
  "id": "msg_abc123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I assist you today?"
    }
  ],
  "model": "claude-3-5-sonnet-20241022",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 15
  }
}
```

**工具调用响应**:
```json
{
  "id": "msg_abc456",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_xyz789",
      "name": "get_weather",
      "input": {
        "location": "San Francisco"
      }
    }
  ],
  "model": "claude-3-5-sonnet-20241022",
  "stop_reason": "tool_use",
  "usage": {
    "input_tokens": 50,
    "output_tokens": 20
  }
}
```

---

## 🌊 Messages API - Streaming

**文件**: `messages-streaming.yaml`

### 流式响应
使用 Server-Sent Events (SSE) 格式。

### 启用流式
在请求中设置 `"stream": true`:

```json
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": "Write a short poem"
    }
  ]
}
```

### 事件类型

1. **message_start** - 消息开始
2. **content_block_start** - 内容块开始
3. **content_block_delta** - 内容增量
4. **content_block_stop** - 内容块结束
5. **message_delta** - 消息增量
6. **message_stop** - 消息结束
7. **ping** - 心跳
8. **error** - 错误

### 事件流示例

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_abc","type":"message","role":"assistant","content":[],"model":"claude-3-5-sonnet-20241022","usage":{"input_tokens":10,"output_tokens":0}}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"The"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" ocean"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" waves"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":15}}

event: message_stop
data: {"type":"message_stop"}
```

### 流式工具调用

工具输入以JSON增量方式传输：

```
event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_123","name":"get_weather","input":{}}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\"loc"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"ation\":\""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"Paris\"}"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}
```

---

## 🎯 可用模型

| 模型 | 描述 | Context Window |
|------|------|----------------|
| claude-3-5-sonnet-20241022 | 最新Sonnet（推荐） | 200K |
| claude-sonnet-4-5-20250110 | Sonnet 4.5 | 200K |
| claude-3-opus-20240229 | 最强模型 | 200K |
| claude-3-haiku-20240307 | 快速模型 | 200K |
| claude-3-5-haiku-20241022 | 最新Haiku | 200K |

---

## 🔐 API Key 获取

1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 创建账号并登录
3. 生成 API Key
4. 在请求header中使用: `x-api-key: sk-ant-xxxxx`

---

## 💰 计费说明

### Token计算
- **输入Token**: 提示词 + 系统提示 + 对话历史 + 工具定义
- **输出Token**: 模型生成的内容

### Prompt Caching
使用缓存可以降低成本：
- `cache_creation_input_tokens` - 创建缓存的token
- `cache_read_input_tokens` - 从缓存读取的token（折扣90%）

---

## 🛠️ 使用工具

### 1. 在线查看
```bash
# Swagger Editor
https://editor.swagger.io/

# 导入 messages-api.yaml 查看交互式文档
```

### 2. 生成SDK
```bash
# Python SDK
openapi-generator-cli generate \
  -i messages-api.yaml \
  -g python \
  -o ./sdk/python

# TypeScript SDK
openapi-generator-cli generate \
  -i messages-api.yaml \
  -g typescript-axios \
  -o ./sdk/typescript
```

### 3. 生成文档
```bash
# 使用 Redoc
redoc-cli bundle messages-api.yaml \
  -o anthropic-api-docs.html
```

---

## 📚 参考资料

- [Anthropic官方文档](https://docs.anthropic.com/)
- [Claude API参考](https://docs.anthropic.com/claude/reference/)
- [项目测试代码](../../tests/anthropic/)
- [项目Schema定义](../../llm_spec/validation/schemas/anthropic/)

---

## 🆚 与 OpenAI API 的差异

| 特性 | Anthropic | OpenAI |
|------|-----------|--------|
| 认证Header | `x-api-key` | `Authorization: Bearer` |
| 版本Header | `anthropic-version` (必需) | 无 |
| max_tokens | **必需参数** | 可选 |
| System Prompt | 独立的 `system` 参数 | messages数组中的system角色 |
| 工具调用 | 原生content块（tool_use/tool_result） | messages中的function_call |
| 流式格式 | Server-Sent Events | Server-Sent Events |
| 思考模式 | Extended Thinking (Claude 3.7+) | 无 |

---

## 📝 更新日志

### 2026-01-28
- ✅ 创建 Messages API 规范（标准响应）
- ✅ 创建 Messages API 规范（流式响应）
- ✅ 所有规范符合 OpenAPI 3.1.0 标准
- ✅ 包含完整的 Schema 定义和示例
- ✅ 涵盖所有主要功能（对话、工具调用、多模态、流式）

---

## 🤝 贡献

这些 OpenAPI 规范基于项目中的 Pydantic Schema 定义和实际测试生成。
如发现错误或需要补充，请提交 Issue 或 PR。

---

## 📄 许可证

MIT License
