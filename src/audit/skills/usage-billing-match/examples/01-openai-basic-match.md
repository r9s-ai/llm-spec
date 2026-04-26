# Example 1: OpenAI Basic Match

## Input

**Usage Records**

```json
[
  {
    "id": "U-001",
    "provider": "openai",
    "model": "gpt-4o",
    "timestamp": 1715570000,
    "usage": {
      "prompt_tokens": 150,
      "completion_tokens": 50,
      "total_tokens": 200,
      "prompt_tokens_details": {
        "cached_tokens": 0,
        "audio_tokens": 0
      },
      "completion_tokens_details": {
        "reasoning_tokens": 0,
        "audio_tokens": 0
      }
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
    "request_time": 1715570005,
    "input_token": 150,
    "output_token": 50,
    "cached_token": 0,
    "amount": 0.0015
  }
]
```

## Expected Output

### 1. 汇总表

| 总usage数 | matched | mismatched | unresolved | missing_billing |
| --- | --- | --- | --- | --- |
| 1 | 1 | 0 | 0 | 0 |

### 2. 逐条审计明细表

| usage序号 | provider | model | 候选billing id | 状态 | 原因 |
| --- | --- | --- | --- | --- | --- |
| 1 (U-001) | openai | gpt-4o | B-001 | matched |  |

### 3. 审计结论

本批数据 1 条 usage 均可唯一匹配 billing。输入 token、输出 token、cached token 均严格一致；未发现需要人工复核的异常项。
