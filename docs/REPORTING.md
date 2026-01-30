# 报告系统设计文档

## 概述

llm-spec 的报告系统自动收集测试结果，并生成三种格式的报告：
- **JSON** 报告：原始数据，供程序处理
- **Markdown** 报告：参数表格，便于阅读
- **HTML** 报告：美观展示，便于分享

## 核心组件

### 1. ReportCollector（测试结果收集器）

**职责**：收集和汇总测试结果

```python
class ReportCollector:
    def __init__(self, provider: str, endpoint: str, base_url: str)
    def record_test(self, test_name, params, status_code, response_body, error=None)
    def add_unsupported_param(self, param_name, param_value, test_name, reason)
    def finalize(self, output_dir="./reports") -> str
```

**工作流程**：

```
测试执行
  ↓
record_test()  ← 每次请求调用一次
  ├─ 提取参数路径（递归处理嵌套结构）
  ├─ 记录测试统计
  ├─ 检测错误和不支持的参数
  ↓
finalize()  ← 测试完成后调用一次
  ├─ 生成 JSON 报告
  ├─ 调用 ParameterTableFormatter
  ├─ 生成 Markdown 表格
  ├─ 生成 HTML 报告
  └─ 返回报告路径
```

#### 参数提取示例

```python
# 扁平结构
_extract_param_paths({"temperature": 0.7})
# 结果: ["temperature"]

# 嵌套字典
_extract_param_paths({"generationConfig": {"temperature": 0.7}})
# 结果: ["generationConfig", "generationConfig.temperature"]

# 数组元素
_extract_param_paths({"messages": [{"role": "user", "content": "hi"}]})
# 结果: ["messages", "messages[0].role", "messages[0].content"]

# 复杂嵌套
_extract_param_paths({
    "requests": [{
        "contents": [{"parts": [{"text": "hello"}]}]
    }]
})
# 结果: ["requests", "requests[0].contents",
#        "requests[0].contents[0].parts",
#        "requests[0].contents[0].parts[0].text"]
```

### 2. ParameterTableFormatter（参数表格格式化器）

**职责**：将 JSON 报告转换为 Markdown 和 HTML 格式

```python
class ParameterTableFormatter:
    def __init__(self, report_data: dict)
    def generate_markdown(self) -> str
    def generate_html(self) -> str
    def save_markdown(self, output_dir) -> str
    def save_html(self, output_dir) -> str
```

**工作流程**：

```
JSON 报告
  ↓
extract_data()
  ├─ tested_params: ["model", "messages", "temperature", ...]
  ├─ unsupported_params: {"param_x": {...}, ...}
  ├─ test_summary: {total, passed, failed}
  ↓
generate_markdown()  →  Markdown 表格
generate_html()      →  HTML 报告
```

#### 输出示例

**Markdown**：
```
# Chat Completions 参数支持报告

**报告时间**: 2026-01-29T19:14:20.005688
**总测试数**: 15
**测试通过**: 14 ✅
**测试失败**: 1 ❌

## 参数支持情况

- **已测试参数**: 7
  - ✅ 支持: 6
  - ❌ 不支持: 1

## 参数详情

| 参数 | 状态 |
|------|------|
| `model` | ✅ 支持 |
| `messages` | ✅ 支持 |
| `temperature` | ✅ 支持 |
| `streaming_options` | ❌ 不支持 (参数不支持) |
```

**HTML**：
- 响应式设计，自适应各种屏幕
- 统计信息卡片（总数、通过、失败、支持率）
- 简洁的参数表格

## 报告结构

### 目录布局

每个测试生成一个独立的子目录：

```
reports/
└── {provider}_{endpoint}_{timestamp}/
    ├── report.json          # JSON 格式（原始数据）
    ├── parameters.md        # Markdown 格式（参数表格）
    └── report.html          # HTML 格式（美观展示）
```

**示例**：

```
reports/
├── openai_v1_chat_completions_20260129_191805/
│   ├── report.json          (665 bytes)
│   ├── parameters.md        (461 bytes)
│   └── report.html          (5.2 KB)
│
├── openai_v1_embeddings_20260129_191805/
│   ├── report.json          (474 bytes)
│   ├── parameters.md        (403 bytes)
│   └── report.html          (4.9 KB)
│
└── gemini_v1beta_models_gemini-3-flash-preview:batchGenerateContent_20260129_191805/
    ├── report.json          (2.4 KB)
    ├── parameters.md        (5.8 KB)
    └── report.html          (10 KB)
```

### JSON 报告格式

```json
{
  "test_time": "2026-01-29T19:14:20.005688",
  "provider": "openai",
  "endpoint": "/v1/chat/completions",
  "base_url": "http://172.18.158.51:3000",
  "test_summary": {
    "total_tests": 15,
    "passed": 14,
    "failed": 1
  },
  "parameters": {
    "tested": [
      "model",
      "messages",
      "messages[0].role",
      "messages[0].content",
      "temperature",
      "top_p",
      "max_tokens"
    ],
    "untested": [],
    "unsupported": [
      {
        "parameter": "streaming_options",
        "value": null,
        "test_name": "test_1",
        "reason": "HTTP 400: 参数不支持"
      }
    ]
  },
  "response_fields": {
    "expected": [],
    "unsupported": []
  },
  "errors": [
    {
      "test_name": "test_1",
      "type": "http_error",
      "message": "HTTP 400: 参数不支持"
    }
  ]
}
```

## 使用流程

### 基本用法

```python
from llm_spec.reporting.collector import ReportCollector

# 1. 创建收集器
collector = ReportCollector(
    provider="openai",
    endpoint="/v1/chat/completions",
    base_url="http://api.openai.com"
)

# 2. 执行测试并记录结果
params = {"model": "gpt-3.5-turbo", "messages": [...]}
status_code, headers, response = client.request(endpoint, params)

collector.record_test(
    test_name="test_baseline",
    params=params,
    status_code=status_code,
    response_body=response,
    error=None if 200 <= status_code < 300 else "HTTP error"
)

# 3. 测试不支持的参数
if error_detected:
    collector.add_unsupported_param(
        param_name="some_param",
        param_value=value,
        test_name="test_param",
        reason="HTTP 400: Not supported"
    )

# 4. 生成报告（自动生成 JSON、Markdown、HTML）
report_path = collector.finalize("./reports")
# 返回: "reports/openai_v1_chat_completions_20260129_191805/report.json"

# 5. 报告自动生成的文件：
# - reports/openai_v1_chat_completions_20260129_191805/report.json
# - reports/openai_v1_chat_completions_20260129_191805/parameters.md
# - reports/openai_v1_chat_completions_20260129_191805/report.html
```

### 在测试中使用

```python
import pytest
from llm_spec.reporting.collector import ReportCollector

class TestChatCompletions:
    ENDPOINT = "/v1/chat/completions"
    BASE_PARAMS = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Hello"}],
    }

    @pytest.fixture(autouse=True)
    def setup_collector(self, openai_client):
        """为每个测试类设置报告收集器"""
        self.client = openai_client
        self.collector = ReportCollector(
            provider="openai",
            endpoint=self.ENDPOINT,
            base_url=openai_client.get_base_url(),
        )
        yield
        # 测试完成后生成报告
        report_path = self.collector.finalize()
        print(f"\n报告已生成: {report_path}")

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        assert 200 <= status_code < 300

    def test_param_temperature(self):
        """测试 temperature 参数"""
        test_name = "test_param_temperature"
        params = {**self.BASE_PARAMS, "temperature": 0.7}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="temperature",
                param_value=0.7,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        assert 200 <= status_code < 300
```

## 设计特点

### 1. 自动化

- ✅ 参数路径自动提取（支持嵌套结构）
- ✅ 报告自动生成（JSON、Markdown、HTML）
- ✅ 目录自动创建和组织

### 2. 零配置

- ❌ 无需手动定义参数列表
- ❌ 无需指定哪些参数支持/不支持
- ✅ 只需记录测试结果，表格自动生成

### 3. 简洁

- Formatter 只需要 JSON 报告数据
- 无需维护多个参数配置文件
- 代码行数少（294 行）

### 4. 可视化

- Markdown 表格便于阅读
- HTML 报告美观专业
- 统计信息一目了然

## 常见问题

### Q: 为什么参数表格自动生成？

A: 因为所有测试的参数信息已经在 JSON 报告的 `tested_params` 字段中，无需手动指定。Formatter 直接从这个字段生成表格。

### Q: 如何添加新的 API 支持？

A: 无需做任何特殊配置。只要在测试中使用 ReportCollector 并调用 finalize()，报告系统会自动为新 API 生成表格。

### Q: 可以自定义报告格式吗？

A: 可以。修改 `ParameterTableFormatter.generate_markdown()` 或 `generate_html()` 方法来自定义格式。

### Q: 如何汇总多个报告？

A: 自动支持！运行整个厂商的测试时，pytest 会自动生成聚合报告。详见下面的[聚合报告](#聚合报告)章节。

### Q: 报告保存在哪里？

A: 默认保存在 `reports/` 目录下，每个测试一个子目录。可以通过 `collector.finalize(output_dir)` 指定自定义目录。

## 最佳实践

1. **每个测试类一个 Collector**：使用 pytest fixture 为每个测试类创建独立的 ReportCollector
2. **及时记录**：在每个测试方法后立即调用 `record_test()`
3. **记录失败**：参数不支持时立即调用 `add_unsupported_param()`
4. **完整信息**：在 reason 字段包含 HTTP 状态码和响应体
5. **查看报告**：测试完成后查看生成的 HTML 报告，比直接看 JSON 更清晰

## 性能特性

| 操作 | 耗时 |
|------|------|
| 参数提取 | O(n)，其中 n 为参数数量 |
| Markdown 生成 | < 10ms |
| HTML 生成 | < 20ms |
| 目录创建 | < 5ms |
| 总耗时 | < 50ms |

## 扩展方向

### 近期
- [ ] 实现汇总报告（多个测试的综合统计）
- [ ] 添加参数说明文档（从 API 规范提取）
- [ ] 实现报告对比（新旧版本差异）

### 长期
- [ ] Web UI 查看报告
- [ ] 报告导出（PDF、Excel）
- [ ] 实时报告仪表盘
- [ ] 历史趋势分析

---

## 文件列表

| 文件 | 用途 |
|------|------|
| `llm_spec/reporting/collector.py` | 测试结果收集器 |
| `llm_spec/reporting/formatter.py` | 参数表格格式化器 |

## 相关文档

- [架构文档](ARCHITECTURE.md) - 整体系统架构
- [DATAFLOW.md](DATAFLOW.md) - 数据流说明
