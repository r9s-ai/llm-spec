# Example 4: Mixed Providers Batch Audit

## Input

**Usage Records**

```json
[
  {
    "id": "U-001",
    "provider": "openai",
    "model": "gpt-4o",
    "timestamp": 1720000000,
    "usage": {
      "prompt_tokens": 1500,
      "completion_tokens": 200,
      "total_tokens": 1700,
      "prompt_tokens_details": { "cached_tokens": 1000 }
    }
  },
  {
    "id": "U-002",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20240620",
    "timestamp": 1720000050,
    "usage": {
      "input_tokens": 50,
      "output_tokens": 100,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0,
      "server_tool_use": { "web_search_requests": 2 }
    }
  },
  {
    "id": "U-003",
    "provider": "gemini",
    "model": "gemini-1.5-pro",
    "timestamp": 1720000100,
    "usage": {
      "promptTokenCount": 500,
      "candidatesTokenCount": 100,
      "totalTokenCount": 600,
      "promptTokensDetails": [
        { "modality": "VIDEO", "tokenCount": 450 },
        { "modality": "TEXT", "tokenCount": 50 }
      ]
    }
  },
  {
    "id": "U-004",
    "provider": "openai",
    "model": "o1-preview",
    "timestamp": 1720000200,
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 500,
      "total_tokens": 510,
      "completion_tokens_details": { "reasoning_tokens": 400 }
    }
  },
  {
    "id": "U-005",
    "provider": "gemini",
    "model": "gemini-1.5-flash",
    "timestamp": 1720000300,
    "usage": {
      "promptTokenCount": 80,
      "candidatesTokenCount": 20,
      "totalTokenCount": 100
    }
  }
]
```

**Billing Records**

```json
[
  {
    "id": "B-001",
    "provider": "openai",
    "model": "gpt-4o",
    "request_time": 1720000002,
    "input_token": 1500,
    "output_token": 200,
    "cached_token": 1000
  },
  {
    "id": "B-002",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20240620",
    "request_time": 1720000055,
    "input_token": 50,
    "output_token": 100,
    "cached_token": 0,
    "ext": { "web_search_requests": 0 }
  },
  {
    "id": "B-003",
    "provider": "gemini",
    "model": "gemini-1.5-pro",
    "request_time": 1720000105,
    "input_token": 50,
    "output_token": 100,
    "cached_token": 0,
    "ext": {
      "input_v2": {
        "video": {
          "unit": "M tokens",
          "price": 0.0001,
          "usage": 0.00045,
          "amount": 0.000000045
        }
      }
    }
  },
  {
    "id": "B-004",
    "provider": "openai",
    "model": "o1-preview",
    "request_time": 1720000205,
    "input_token": 10,
    "output_token": 500,
    "cached_token": 0
  },
  {
    "id": "B-005",
    "provider": "gemini",
    "model": "gemini-1.5-flash",
    "request_time": 1720000302,
    "input_token": 81,
    "output_token": 20,
    "cached_token": 0
  }
]
```

## Expected Output

### 1. 汇总表

| 总usage数 | matched | mismatched | unresolved | missing_billing |
| --- | --- | --- | --- | --- |
| 5 | 3 | 2 | 0 | 0 |

### 2. 逐条审计明细表

| usage序号 | provider | model | 候选billing id | 状态 | 原因 |
| --- | --- | --- | --- | --- | --- |
| 1 (U-001) | openai | gpt-4o | B-001 | matched |  |
| 2 (U-002) | anthropic | claude-3-5-sonnet-20240620 | B-002 | mismatched | usage 有 2 次 web_search，billing ext 记录为 0 |
| 3 (U-003) | gemini | gemini-1.5-pro | B-003 | matched |  |
| 4 (U-004) | openai | o1-preview | B-004 | matched |  |
| 5 (U-005) | gemini | gemini-1.5-flash | B-005 | mismatched | 输入 token 差 1，虽候选唯一但按严格审计记为 mismatched |

### 3. 审计结论

本批数据 5 条 usage 中有 3 条 matched、2 条 mismatched。异常集中在工具调用计费和基础输入 token 严格一致性：U-002 的 web search 次数未对齐，U-005 输入 token 差 1。U-004 的 reasoning_tokens 作为输出侧拆分说明，billing 输出 token 已覆盖 completion_tokens，因此不单独判定为 mismatch。
