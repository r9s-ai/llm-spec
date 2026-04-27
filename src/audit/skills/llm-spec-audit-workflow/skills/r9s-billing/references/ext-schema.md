# R9S ext Schema

这个文件补充说明 R9S billing record 中 `ext` 字段的结构，适合在需要精确解释多模态和工具计费时读取。

## 作用

`ext` 是 billing record 的扩展计费区，用于表达主字段之外的附加成本。

典型用途：

- 多模态输入计费
- 工具调用计费
- 后续扩展计费项

## 通用模式

`ext` 自身通常是一个对象：

```json
{
  "ext": {}
}
```

或：

```json
{
  "ext": {
    "input_v2": {
      "image": {
        "unit": "mtoken",
        "price": 2,
        "usage": 0.00108,
        "amount": 0.00216
      }
    }
  }
}
```

也可能是：

```json
{
  "ext": {
    "tools": {
      "web_search": {
        "unit": "each",
        "price": 0.001,
        "usage": 3,
        "amount": 0.003
      }
    }
  }
}
```

## 可复用的明细结构

`ext` 下很多计费项都复用同一种结构：

- `unit`
- `price`
- `usage`
- `amount`

语义如下：

- `unit`
  计费单位，例如 `mtoken` 或 `each`
- `price`
  单价
- `usage`
  使用量
- `amount`
  这一项对应的费用

## ext.input_v2

`input_v2` 表示扩展输入计费，通常用于多模态输入。

常见子项：

- `audio`
- `video`
- `image`

结构示意：

```json
{
  "ext": {
    "input_v2": {
      "audio": {
        "unit": "mtoken",
        "price": 2,
        "usage": 0.000029,
        "amount": 0.000058
      },
      "video": {
        "unit": "mtoken",
        "price": 2,
        "usage": 0.000064,
        "amount": 0.000128
      },
      "image": {
        "unit": "mtoken",
        "price": 2,
        "usage": 0.00108,
        "amount": 0.00216
      }
    }
  }
}
```

解释原则：

- `input_token` 很小时，不代表输入成本低
- 某些模型会把 image / audio / video 费用放在 `ext.input_v2` 中单独体现
- 和 usage 对账时，应尽量使用 provider 的多模态明细去解释这些项目

## ext.tools

`tools` 表示工具调用相关的附加费用。

当前已知示例：

- `web_search`

结构示意：

```json
{
  "ext": {
    "tools": {
      "web_search": {
        "unit": "each",
        "price": 0.001,
        "usage": 3,
        "amount": 0.003
      }
    }
  }
}
```

解释原则：

- `usage` 表示工具调用次数
- `amount` 表示工具调用总成本
- 这类字段应与 usage 侧的 tool-use / web-search 信息联合解释

## 对账建议

解释 R9S 账单时，建议按下面的顺序看 `ext`：

1. `ext` 是否为空对象
2. 是否存在 `input_v2`
3. 是否存在 `tools`
4. 逐项读取 `unit` / `price` / `usage` / `amount`

如果 billing 金额与主 token 不完全一致，不要马上判错，先检查：

- 是否存在 image / audio / video 成本
- 是否存在 web search 等工具成本
- 是否存在 cache 成本已在主字段中单独体现

## 扩展兼容性

未来如果 R9S 增加新字段，例如：

- `ext.output_v2`
- `ext.tools.code_interpreter`
- `ext.tools.file_search`
- 其他 modality 或工具名

优先按同一模式理解：

- 把它视为扩展计费项
- 检查是否仍然使用 `unit` / `price` / `usage` / `amount`
- 再将其纳入 usage 对账说明
