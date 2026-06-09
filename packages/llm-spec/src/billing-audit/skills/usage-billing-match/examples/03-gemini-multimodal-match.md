# Example 3: Gemini Multimodal Match

## Input

**Usage Records**

```json
[
  {
    "id": "U-001",
    "provider": "gemini",
    "model": "gemini-1.5-flash",
    "timestamp": 1720274400,
    "usage": {
      "promptTokenCount": 310,
      "candidatesTokenCount": 50,
      "totalTokenCount": 360,
      "promptTokensDetails": [
        { "modality": "TEXT", "tokenCount": 52 },
        { "modality": "IMAGE", "tokenCount": 258 }
      ]
    }
  }
]
```

**Billing Records**

```json
[
  {
    "id": "B-001",
    "provider": "gemini",
    "model": "gemini-1.5-flash",
    "request_time": 1720274402,
    "input_token": 52,
    "output_token": 50,
    "cached_token": 0,
    "ext": {
      "input_v2": {
        "image": {
          "unit": "M tokens",
          "price": 0.0001,
          "usage": 0.000258,
          "amount": 0.0000000258
        }
      }
    },
    "amount": 0.0001
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
| 1 (U-001) | gemini | gemini-1.5-flash | B-001 | matched |  |

### 3. 审计结论

本批数据 1 条 usage 可唯一匹配 billing。billing 主输入 token 对应文本输入 52，图片输入 258 token 由 `ext.input_v2.image` 解释；输出 token 一致，未发现异常项。
