# 配置驱动测试指南 (Configuration-Driven Testing Guide)

## 概述

本项目已从手写 Python 测试代码全面迁移至**配置驱动 (Configuration-Driven)** 架构。测试逻辑（如何请求、如何验证、如何报告）已固化在执行引擎中，开发者只需通过 JSON5 配置文件即可定义新的测试套件和用例。

---

## 核心组件流程

```mermaid
graph TD
    A[JSON5 配置文件] --> B[Pytest 自动发现]
    B --> C[ConfigDrivenTestRunner]
    C --> D[Schema Registry]
    C --> E[Provider Adapter]
    C --> F[HTTP Client]
    F --> G[API 厂商]
    G --> F
    F --> H[Response Validator]
    H --> I[Report Collector]
```

---

## 配置文件规范 (.json5)

配置文件位于 `tests/testcases/` 目录下。

### 顶级字段说明

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `suite_name` | string | 测试套件名称（如 "OpenAI Chat"） |
| `provider` | string | 厂商标识符（openai, gemini, anthropic, xai） |
| `endpoint` | string | API 路径（如 "/v1/chat/completions"） |
| `method` | string | HTTP 方法（如 "POST"） |
| `base_params` | object | 所有测试用例共享的基础参数（模型名等） |
| `param_wrapper`| string | (可选) 参数包装键，如 Gemini 的 `generationConfig` |
| `schemas` | object | 校验配置。`response` 字段需填入注册表中的 Key |
| `tests` | array | 具体测试用例数组 |

### 测试用例字段 (`tests` 数组)

- `name`: 用例名称。
- `description`: 详述测试目的。
- `params`: 本用例特有的参数。会自动与 `base_params` 合并。
- `parameterize`: (可选) 动态生成子用例。如 `{"model": ["gpt-4o", "o1-mini"]}`。
- `files`: (可选) 上传文件。格式为 `{"字段名": "文件相对于根目录的路径"}`。
- `stream`: (可选) 设为 `true` 以启动流式解析校验。
- `test_param`: (可选) 指定要测试的参数，格式为 `{"name": "参数路径", "value": "参数值"}`。用于记录参数支持情况。
- `is_baseline`: (可选) 设为 `true` 表示基线测试，会记录所有参数的支持情况。
- `no_wrapper`: (可选) 设为 `true` 以在该用例中跳过 `param_wrapper` 的包装。

---

## 模式示例 (Test Patterns)

### 1. 基线测试 (Baseline)
基线测试用于测试 API 的基本功能，并记录所有参数的支持情况。
```javascript
{
  name: "test_baseline",
  description: "测试基线：仅必需参数",
  is_baseline: true
}
```

### 2. 普通参数测试
测试单个参数的支持情况，使用 `test_param` 指定参数名和值：
```javascript
{
  name: "test_param_temperature",
  description: "测试 temperature 参数",
  params: {
    temperature: 0.7
  },
  test_param: {
    name: "temperature",
    value: 0.7
  }
}
```

对于嵌套参数（如 `response_format.type`）：
```javascript
{
  name: "test_response_format_json_schema",
  description: "测试 response_format 为 json_schema",
  params: {
    response_format: {
      type: "json_schema",
      json_schema: {
        name: "person",
        schema: { ... }
      }
    }
  },
  test_param: {
    name: "response_format.type",
    value: "json_schema"
  }
}
```

### 3. 参数化测试 (Parameterize)
一次性对多个模型或选项进行交叉测试：
```javascript
{
  name: "test_model_variants",
  parameterize: {
    model: ["gpt-4o-mini", "o1-preview", "gpt-4o"]
  },
  params: { model: "$model" },  // 使用 $ 符号引用变量
  test_param: {
    name: "model",
    value: "$model"  // 同样使用 $ 符号引用变量
  }
}
```

### 4. 文件上传测试 (Multipart)
```javascript
{
  name: "test_transcription",
  files: {
    file: "test_assets/audio/hello.mp3"
  },
  params: { model: "whisper-1" },
  test_param: {
    name: "file",
    value: "hello.mp3"
  }
}
```

---

## 如何添加新测试用例 (四步走)

### 第一步：检查或添加 Schema
在 `llm_spec/validation/schemas/` 目录下确保有对应的 Pydantic 模型。

### 第二步：注册 Schema
在 `tests/runners/schema_registry.py` 中导入并注册该模型：
```python
from llm_spec.validation.schemas.openai.audio import AudioTranscriptionResponse
_REGISTRY["openai.AudioTranscription"] = AudioTranscriptionResponse
```

### 第三步：创建 JSON5 配置文件
在 `tests/testcases/` 下的对应厂商文件夹中（如 `openai/`）创建 `.json5` 文件。

### 第四步：运行测试
```bash
# 运行指定厂商的配置测试
uv run pytest tests/test_from_config.py -k "openai"

# 结合日志查看详情
uv run pytest tests/test_from_config.py -v --log-cli-level=INFO
```

---

## 注意事项

1. **绝对路径 vs 相对路径**：JSON5 中的文件路径应相对于项目根目录。
2. **深度合并**：`params` 会递归地合并到 `base_params` 中，允许覆盖或添加子字段。
3. **参数支持记录**：
   - 基线测试（`is_baseline: true`）会自动记录所有参数的支持情况
   - 普通测试需要通过 `test_param` 手动指定要记录的参数名和值
   - 只有被明确记录的参数才会显示在报告中
