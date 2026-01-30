# LLM-Spec

一个规范驱动的 LLM API 厂商兼容性测试工具，用于验证各厂商API的参数支持情况和响应格式合规性。

## 🎯 核心功能

- ✅ **细粒度参数测试**：使用控制变量法，精确定位不支持的参数和参数值
- ✅ **参数变体测试**：自动测试参数的所有可能值（如不同的model、voice等）
- ✅ **响应格式验证**：使用Pydantic模型验证响应结构，字段级别错误定位
- ✅ **详细JSON报告**：包含测试统计、不支持参数列表、缺失字段、详细错误信息
- ✅ **结构化日志**：每个请求有唯一ID，完整的请求/响应链路追踪
- ✅ **多Provider支持**：支持OpenAI、Anthropic、Gemini、xAI等

## 📦 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 配置

编辑 `llm-spec.toml`：

```toml
[log]
enabled = true
level = "INFO"
file = "./logs/llm-spec.log"
log_request_body = true
log_response_body = false

[report]
output_dir = "./reports"

[openai]
api_key = "your-api-key"
base_url = "https://api.openai.com"
timeout = 30.0
```

### 3. 运行测试

```bash
# 运行单个endpoint测试
pytest tests/openai/test_chat_completions.py -v

# 运行所有OpenAI测试
pytest tests/openai/ -v

# 运行所有Anthropic测试
pytest tests/anthropic/ -v

# 运行所有Gemini测试
pytest tests/gemini/ -v

# 运行所有测试
pytest tests/ -v
```

### 4. 查看报告

```bash
# 报告输出会按 run_id 分目录（例如 reports/20260130_123456/...）
# 先找到最新的 run_id 目录
ls -lt reports | head

# 再查看某个 endpoint 的 JSON 报告
cat reports/<run_id>/openai_v1_chat_completions_*/report.json
```

## 📋 项目结构

```
llm-spec/
├── llm_spec/              # 核心代码
│   ├── config/            # 配置管理
│   ├── client/            # HTTP客户端
│   ├── providers/         # Provider适配器
│   ├── validation/        # 响应验证
│   └── reporting/         # 报告生成
├── tests/                 # 测试代码
│   ├── openai/            # OpenAI 测试（7个文件）
│   ├── anthropic/         # Anthropic 测试（4个文件）
│   ├── gemini/            # Gemini 测试（3个文件）
│   └── xai/               # xAI 测试
├── test_assets/           # 测试资源
├── reports/               # 生成的报告
└── logs/                  # 日志文件
```

## 🚀 添加新的 Endpoint 测试

### 示例：测试 `/v1/audio/speech`

1. **创建 Pydantic Schema**（如果需要）

```python
# llm_spec/validation/schemas/openai/audio.py
from pydantic import BaseModel

class AudioSpeechResponse(BaseModel):
    # 音频响应通常是二进制，可能不需要验证
    pass
```

2. **创建测试文件**

```python
# tests/providers/openai/test_audio_speech.py
import pytest
from llm_spec.reporting.collector import ReportCollector

class TestAudioSpeech:
    ENDPOINT = "/v1/audio/speech"
    BASE_PARAMS = {
        "model": "tts-1",
        "input": "Hello",
        "voice": "alloy",
    }

    @pytest.fixture(autouse=True)
    def setup_collector(self, openai_client):
        self.client = openai_client
        self.collector = ReportCollector(
            provider="openai",
            endpoint=self.ENDPOINT,
            base_url=openai_client.get_base_url(),
        )
        yield
        self.collector.finalize()

    def test_baseline(self):
        status_code, headers, body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )
        self.collector.record_test(
            test_name="test_baseline",
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )
        assert 200 <= status_code < 300

    @pytest.mark.parametrize("voice", ["alloy", "echo", "fable"])
    def test_voice_variants(self, voice):
        params = {**self.BASE_PARAMS, "voice": voice}
        status_code, headers, body = self.client.request(
            endpoint=self.ENDPOINT, params=params
        )
        # 记录测试结果...
```

3. **运行测试**

```bash
pytest tests/providers/openai/test_audio_speech.py -v
```

详细文档见 [ARCHITECTURE.md](ARCHITECTURE.md)

## 🧪 测试模式

### 基线测试
仅使用必需参数，验证基本功能

```python
def test_baseline(self):
    params = self.BASE_PARAMS
    # 测试...
```

### 单参数测试
每次测试一个新参数（控制变量法）

```python
def test_param_temperature(self):
    params = {**self.BASE_PARAMS, "temperature": 0.7}
    # 如果失败，记录为不支持
```

### 参数变体测试
测试参数的所有可能值

```python
@pytest.mark.parametrize("model", ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"])
def test_model_variants(self, model):
    params = {**self.BASE_PARAMS, "model": model}
    # 精确报告哪个值不支持
```

## 📊 报告格式

生成的JSON报告包含：

```json
{
  "test_time": "2026-01-27T15:40:00Z",
  "provider": "openai",
  "endpoint": "/v1/chat/completions",
  "test_summary": {
    "total_tests": 6,
    "passed": 5,
    "failed": 1
  },
  "parameters": {
    "tested": ["model", "messages", "temperature", "max_tokens"],
    "unsupported": [
      {
        "parameter": "model",
        "value": "gpt-4",
        "test_name": "test_model_variants[gpt-4]",
        "reason": "HTTP 404: No available channels"
      }
    ]
  },
  "response_fields": {
    "expected": ["id", "object", "created", "model", "choices"],
    "unsupported": [
      {
        "field": "system_fingerprint",
        "reason": "Field missing in response"
      }
    ]
  },
  "errors": [...]
}
```

## 🎨 设计原则

- **显式优于隐式**：所有参数在测试类顶部显式定义
- **控制变量法**：每次只测试一个新参数
- **细粒度报告**：精确到参数值、字段级别的错误
- **统一错误处理**：所有错误都视为失败并记录
- **低耦合高扩展**：添加新endpoint或provider无需修改核心代码

## 📚 文档

- [ARCHITECTURE.md](ARCHITECTURE.md) - 完整架构文档
- [llm-spec.toml](llm-spec.toml) - 配置文件示例

## 🔧 依赖

- Python >= 3.11
- httpx - HTTP客户端
- pydantic - 数据验证
- pytest - 测试框架

## 📝 License

MIT
