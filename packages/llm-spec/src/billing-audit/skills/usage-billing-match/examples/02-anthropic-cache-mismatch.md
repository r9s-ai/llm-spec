# Example 2: Anthropic Cache Mismatch

## Input

**Usage Records**

```json
[
  {
    "id": "U-001",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20240620",
    "timestamp": "2024-06-21T10:00:00Z",
    "usage": {
      "input_tokens": 20,
      "output_tokens": 100,
      "cache_creation_input_tokens": 1000,
      "cache_read_input_tokens": 500
    }
  }
]
```

**Billing Records**

```json
[
  {
    "id": "B-001",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20240620",
    "request_time": "2024-06-21T10:00:05Z",
    "input_token": 20,
    "output_token": 100,
    "cached_token": 0,
    "amount": 0.00156
  }
]
```

## Expected Output

### 1. 汇总表

| 总usage数 | matched | mismatched | unresolved | missing_billing |
| --- | --- | --- | --- | --- |
| 1 | 0 | 1 | 0 | 0 |

### 2. 逐条审计明细表

| usage序号 | provider | model | 候选billing id | 状态 | 原因 |
| --- | --- | --- | --- | --- | --- |
| 1 (U-001) | anthropic | claude-3-5-sonnet-20240620 | B-001 | mismatched | usage 有 1500 个 cache 相关 token，billing cached_token 为 0 |

### 3. 审计结论

本批数据存在 1 条 mismatch。基础输入 token 和输出 token 一致，但 cache 相关核心计费字段未对齐；建议人工复核 billing 是否缺失 cache creation/read 计费口径。
