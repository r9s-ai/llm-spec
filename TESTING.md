# LLM-Spec 测试指南

## 快速开始

### 1. 安装依赖

```bash
# 安装所有依赖（包括开发依赖）
uv sync --all-extras

# 或者只安装开发依赖
uv sync --extra dev
```

### 2. 配置 API Key

有两种方式配置 API Key：

**方式一：环境变量**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="..."
export XAI_API_KEY="..."
```

**方式二：配置文件**

复制示例配置文件并修改：
```bash
cp llm-spec.example.toml llm-spec.toml
```

编辑 `llm-spec.toml`：
```toml
[openai]
api_key = "sk-..."
base_url = "https://api.openai.com/v1"  # 可选，支持代理

[anthropic]
api_key = "sk-ant-..."

[report]
format = "terminal"  # terminal / json / both
output_dir = "./reports"  # JSON 报告输出目录
```

## 运行测试

### 基本命令

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_openai.py

# 运行特定测试类
uv run pytest tests/test_openai.py::TestChatCompletions

# 运行特定测试方法
uv run pytest tests/test_openai.py::TestChatCompletions::test_basic_completion
```

### 测试标记 (Markers)

项目使用 pytest markers 来分类测试：

| Marker | 说明 |
|--------|------|
| `integration` | 需要真实 API Key 的集成测试 |
| `expensive` | 消耗大量 API 额度的测试（图像生成等） |

```bash
# 跳过集成测试（不调用真实 API）
uv run pytest -m "not integration"

# 只运行集成测试
uv run pytest -m integration

# 跳过昂贵的测试
uv run pytest -m "not expensive"

# 运行昂贵的测试（需要 --run-expensive 参数）
uv run pytest --run-expensive
```

### 按 Provider 运行

```bash
# 只测试 OpenAI
uv run pytest tests/test_openai.py

# 只测试 Anthropic
uv run pytest tests/test_anthropic.py

# 只测试 Gemini
uv run pytest tests/test_gemini.py
```

### 按功能运行

```bash
# Chat Completions 测试
uv run pytest tests/test_openai.py::TestChatCompletions

# Embeddings 测试
uv run pytest tests/test_openai.py::TestEmbeddings

# Audio 测试
uv run pytest tests/test_openai.py::TestAudioSpeech
uv run pytest tests/test_openai.py::TestAudioTranscription

# Images 测试
uv run pytest tests/test_openai.py::TestImages

# Pipeline 测试（图像/音频流水线）
uv run pytest tests/test_openai_pipeline.py --run-expensive
```

## 输出选项

```bash
# 详细输出
uv run pytest -v

# 显示 print 语句输出
uv run pytest -s

# 详细输出 + print
uv run pytest -vs

# 简短错误追踪
uv run pytest --tb=short

# 完整错误追踪
uv run pytest --tb=long

# 只显示失败的测试
uv run pytest --tb=no -q
```

## 并行测试

使用 pytest-xdist 并行运行测试：

```bash
# 使用所有 CPU 核心
uv run pytest -n auto

# 指定并行数量
uv run pytest -n 4
```

> ⚠️ 注意：并行测试时可能会遇到 API 限流，建议对集成测试谨慎使用。

## 测试覆盖率

```bash
# 生成覆盖率报告
uv run pytest --cov=llm_spec

# 生成 HTML 覆盖率报告
uv run pytest --cov=llm_spec --cov-report=html

# 查看报告
open htmlcov/index.html
```

## 报告配置

### 终端报告

默认情况下，验证报告会以彩色表格形式输出到终端。

### JSON 报告

在 `llm-spec.toml` 中配置：

```toml
[report]
format = "json"           # 或 "both" 同时输出到终端和文件
output_dir = "./reports"  # 报告保存目录
include_raw_response = true  # 是否包含原始 API 响应
```

### 在代码中控制报告

```python
from llm_spec.providers.openai import OpenAIClient

client = OpenAIClient()
report = client.validate_chat_completion(model="gpt-4o-mini")

# 打印到终端
report.print()

# 保存到文件
report.save("./my_report.json")

# 获取 JSON 字符串
json_str = report.to_json()

# 获取字典
data = report.to_dict()

# 根据配置自动输出
report.output()
```

## 常见问题

### Q: 测试被跳过 (SKIPPED)

检查 API Key 是否配置正确：
```bash
echo $OPENAI_API_KEY
```

或检查配置文件 `llm-spec.toml` 是否存在且配置正确。

### Q: 测试失败但报告显示 78% valid

这是正常的！这说明 API 响应与定义的 schema 有差异。可能的原因：
- API 返回了 schema 未定义的新字段（标记为 `unexpected`）
- 类型检查过于严格（如 `Literal` vs `str`）
- API 版本更新导致响应结构变化

### Q: 如何只看失败的字段

报告默认显示所有字段。可以配置只显示问题字段：

```toml
[report]
show_valid = false  # 不显示正确的字段
```

### Q: 图像/音频测试太贵了

这些测试默认会跳过，需要显式启用：
```bash
uv run pytest tests/test_openai_pipeline.py --run-expensive
```

## 测试文件结构

```
tests/
├── conftest.py              # pytest fixtures 和配置
├── base.py                  # 测试工具函数
├── test_openai.py           # OpenAI 单元测试
├── test_openai_pipeline.py  # OpenAI 流水线测试
├── test_anthropic.py        # Anthropic 测试
└── test_gemini.py           # Gemini 测试
```

## 添加新测试

参考现有测试结构：

```python
import pytest
from llm_spec.providers.openai import OpenAIClient
from tests.base import assert_report_valid

@pytest.mark.integration
class TestMyFeature:
    """测试新功能。"""

    def test_basic(self, openai_client: OpenAIClient) -> None:
        """基本功能测试。"""
        report = openai_client.validate_xxx(...)
        report.print()
        assert_report_valid(report)

    @pytest.mark.expensive
    def test_expensive_operation(self, openai_client: OpenAIClient) -> None:
        """昂贵操作测试。"""
        # 需要 --run-expensive 才会运行
        ...
```
