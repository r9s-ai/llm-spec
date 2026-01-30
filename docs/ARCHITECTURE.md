# LLM-Spec 架构文档

## 项目概述

LLM-Spec 是一个规范驱动的 LLM API 厂商兼容性测试工具，用于验证各厂商API的参数支持情况和响应格式合规性，并生成细粒度的测试报告。

## 项目结构

```
llm-spec/
├── llm_spec/                      # 核心代码
│   ├── __init__.py
│   ├── config/                    # 配置管理
│   │   ├── __init__.py
│   │   └── loader.py              # TOML配置解析器
│   ├── client/                    # HTTP客户端层
│   │   ├── __init__.py
│   │   ├── base_client.py         # HTTP客户端抽象接口
│   │   ├── http_client.py         # httpx具体实现
│   │   └── logger.py              # 结构化日志器
│   ├── providers/                 # Provider适配层
│   │   ├── __init__.py
│   │   ├── base.py                # Provider适配器基类
│   │   ├── openai.py              # OpenAI适配器
│   │   ├── anthropic.py           # Anthropic适配器
│   │   ├── gemini.py              # Gemini适配器 ✅
│   │   └── xai.py                 # xAI适配器
│   ├── validation/                # 响应验证层
│   │   ├── __init__.py
│   │   ├── validator.py           # 核心验证逻辑
│   │   └── schemas/               # Pydantic响应模型
│   │       ├── __init__.py
│   │       ├── openai/            # OpenAI schemas
│   │       │   ├── __init__.py
│   │       │   ├── chat.py        # Chat Completions
│   │       │   ├── audio.py       # Audio endpoints ✅
│   │       │   ├── images.py      # Images endpoints ✅
│   │       │   ├── embeddings.py  # Embeddings ✅
│   │       │   └── responses.py   # Responses API ✅
│   │       ├── gemini/            # Gemini schemas ✅
│   │       │   ├── __init__.py
│   │       │   ├── generate_content.py       # GenerateContent API
│   │       │   ├── batch_generate_content.py # BatchGenerateContent API ✅
│   │       │   ├── embeddings.py             # EmbedContent API
│   │       │   └── tokens.py                 # CountTokens API
│   │       ├── anthropic/         # Anthropic schemas ✅
│   │       │   ├── __init__.py
│   │       │   └── messages.py         # Messages API
│   │       └── xai/               # xAI schemas
│   │           └── __init__.py
│   └── reporting/                 # 报告系统
│       ├── __init__.py
│       ├── collector.py           # 测试结果收集器 ✅
│       └── formatter.py           # 参数表格格式化器 ✅
├── tests/                         # 测试代码
│   ├── __init__.py
│   ├── conftest.py                # Pytest全局fixtures
│   ├── openai/                    # OpenAI 测试 ✅
│   │   ├── __init__.py
│   │   ├── test_chat_completions.py
│   │   ├── test_audio_speech.py
│   │   ├── test_audio_transcriptions.py
│   │   ├── test_audio_translations.py
│   │   ├── test_embeddings.py
│   │   ├── test_images_generations.py
│   │   └── test_responses.py
│   ├── gemini/                    # Gemini 测试 ✅
│   │   ├── __init__.py
│   │   ├── test_generate_content.py        # 非流式生成测试
│   │   ├── test_stream_generate_content.py # 流式生成测试 (15个测试)
│   │   ├── test_batch_generate_content.py  # 批处理生成测试 ✅ (21个测试)
│   │   ├── test_embed_content.py
│   │   └── test_count_tokens.py
│   ├── anthropic/                 # Anthropic 测试 ✅
│   │   ├── __init__.py
│   │   ├── test_messages_basic.py
│   │   ├── test_messages_advanced.py
│   │   ├── test_messages_tools.py
│   │   └── test_messages_streaming.py
│   └── xai/                       # xAI 测试
│       ├── __init__.py
│       └── test_chat_completions.py
├── test_assets/                   # 测试资源文件
│   ├── audio/                     # 音频文件
│   └── images/                    # 图片文件
├── temp/                          # 临时文件（按时间戳分目录）
├── reports/                       # 生成的报告目录
│   └── {provider}_{endpoint}_{timestamp}/  # 每个测试一个子目录
│       ├── report.json            # JSON 格式报告
│       ├── parameters.md          # Markdown 参数表格
│       └── report.html            # HTML 格式报告
├── logs/                          # 应用日志
├── llm-spec.toml                  # 配置文件
└── pyproject.toml                 # 项目元数据
```

## 架构分层

### 第一层：配置与日志 (config + client/logger)
**职责**：配置管理、日志记录
- 解析 `llm-spec.toml` 配置文件
- 提供结构化日志（带request_id追踪）
- 支持控制台和文件日志输出

### 第二层：HTTP客户端 (client)
**职责**：HTTP通信
- 抽象接口：`BaseHTTPClient` 定义标准方法
- 具体实现：`HTTPClient` 基于 httpx
- 支持：同步/异步、流式/非流式
- 自动错误处理和日志记录

### 第三层：Provider适配器 (providers)
**职责**：各厂商API适配
- 使用**组合模式**（持有HTTPClient，而非继承）
- 准备厂商特定的请求头（如认证）
- 拼接完整URL（base_url + endpoint）
- 委托HTTPClient执行请求

### 第四层：验证系统 (validation)
**职责**：响应格式验证
- **递归字段提取**：自动提取所有嵌套字段（如 `choices.message.role`、`usage.prompt_tokens`）
- **字段级验证**：精确定位缺失或错误的字段
- **类型验证**：确保字段值符合 schema 定义
- Pydantic模型定义期望的响应结构

### 第五层：报告系统 (reporting)
**职责**：测试结果汇总、参数表格生成
- 收集测试参数、状态码、错误信息
- **递归嵌套参数提取**：自动提取嵌套字典和数组中的参数路径（如 `generationConfig.temperature`、`messages[0].role`）
- 跟踪不支持的参数和缺失的响应字段
- 生成 JSON、Markdown、HTML 格式报告

**ReportCollector 核心功能**：
```python
@staticmethod
def _extract_param_paths(params: dict[str, Any], prefix: str = "", max_depth: int = 10) -> set[str]:
    """递归提取参数路径（支持嵌套结构）

    示例：
    - 扁平结构 (OpenAI): {"temperature": 0.7} → ["temperature"]
    - 嵌套字典 (Gemini): {"generationConfig": {"temperature": 0.7}}
      → ["generationConfig", "generationConfig.temperature"]
    - 数组字典 (Anthropic): {"messages": [{"role": "user"}]}
      → ["messages", "messages[0].role"]
    """
```

这确保了报告中的 `parameters.tested` 字段包含所有实际使用的参数路径，而不仅仅是顶级键。

**ParameterTableFormatter 核心功能**：
```python
class ParameterTableFormatter:
    """参数支持情况格式化器

    直接从 JSON 报告的 tested_params 生成表格：
    - 无需手动定义参数列表
    - 自动检测支持/不支持状态
    - 支持 Markdown 和 HTML 两种输出格式
    """

    def __init__(self, report_data: dict):
        # 从报告中提取：
        # - tested_params: 已测试的参数列表
        # - unsupported_params: 不支持的参数及原因
        # - test_summary: 测试统计（总数、通过、失败）

    def generate_markdown(self) -> str:
        """生成简洁的 Markdown 表格"""

    def generate_html(self) -> str:
        """生成美观的 HTML 报告"""
```

**报告目录结构**：
```
reports/
└── openai_v1_chat_completions_20260129_191805/  # provider_endpoint_timestamp
    ├── report.json              # JSON 格式（原始数据）
    ├── parameters.md            # Markdown 格式（参数表格）
    └── report.html              # HTML 格式（美观展示）
```

### 第六层：测试层 (tests)
**职责**：执行具体的API测试
- Pytest测试类和方法
- 使用控制变量法测试参数
- 参数变体测试（parametrize）

## 设计原则

### 1. 关注点分离
- **HTTP客户端** 不知道 Provider 的存在
- **Provider适配器** 不知道验证逻辑
- **验证器** 不知道报告格式
- 每层职责单一，接口清晰

### 2. 组合优于继承
```python
# ❌ 不使用继承
class OpenAIAdapter(HTTPClient):
    pass

# ✅ 使用组合
class OpenAIAdapter(ProviderAdapter):
    def __init__(self, config, http_client):
        self.http_client = http_client  # 持有实例
```

### 3. 显式优于隐式
```python
class TestChatCompletions:
    # ✅ 参数在顶层显式定义
    ENDPOINT = "/v1/chat/completions"
    BASE_PARAMS = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Say hello"}],
    }

    # ❌ 避免隐藏在方法内部
```

### 4. 控制变量法测试
```python
# 基线测试：仅必需参数
def test_baseline(self):
    params = self.BASE_PARAMS

# 单参数测试：基线 + 1个新参数
def test_param_temperature(self):
    params = {**self.BASE_PARAMS, "temperature": 0.7}

# 参数变体测试：测试所有可能值
@pytest.mark.parametrize("model", ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"])
def test_model_variants(self, model):
    params = {**self.BASE_PARAMS, "model": model}
```

### 5. 统一错误处理
- 所有错误（网络、HTTP、验证）都视为测试失败
- 错误详情记录在 `reason` 字段
- 不区分错误类型，但保留完整上下文

## 如何添加新的 Endpoint

### 方法一：为现有 Provider 添加新 Endpoint（推荐用于简单场景）

假设要为 OpenAI 添加 `/v1/audio/speech` endpoint：

#### Step 1: 创建 Pydantic Schema

```python
# llm_spec/validation/schemas/openai/audio.py
from pydantic import BaseModel

class AudioSpeechResponse(BaseModel):
    """Audio Speech 响应（二进制数据，这里简化）"""
    # 注意：实际audio响应是二进制流，这里可能不需要验证
    # 或者只验证HTTP状态码和Content-Type
    pass
```

#### Step 2: 创建测试文件

```python
# tests/openai/test_audio_speech.py
import pytest
from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.audio import AudioSpeechResponse
from llm_spec.validation.validator import ResponseValidator


class TestAudioSpeech:
    """Audio Speech API 测试类"""

    ENDPOINT = "/v1/audio/speech"

    # 基线参数：仅必需参数
    BASE_PARAMS = {
        "model": "tts-1",
        "input": "Hello world",
        "voice": "alloy",
    }

    @pytest.fixture(autouse=True)
    def setup_collector(self, openai_client):
        """为每个测试设置报告收集器"""
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

        # Audio响应是二进制，验证状态码和Content-Type
        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=None,  # 二进制数据不记录
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        assert 200 <= status_code < 300
        assert "audio" in headers.get("content-type", "")

    def test_param_speed(self):
        """测试 speed 参数"""
        test_name = "test_param_speed"
        params = {**self.BASE_PARAMS, "speed": 1.5}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="speed",
                param_value=1.5,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300

    @pytest.mark.parametrize("voice", [
        "alloy", "echo", "fable", "onyx", "nova", "shimmer"
    ])
    def test_voice_variants(self, voice):
        """测试不同的 voice 变体"""
        test_name = f"test_voice_variants[{voice}]"
        params = {**self.BASE_PARAMS, "voice": voice}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=None,
            error=None if 200 <= status_code < 300 else f"HTTP {status_code}",
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="voice",
                param_value=voice,
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
```

#### Step 3: 运行测试

```bash
pytest tests/openai/test_audio_speech.py -v
```

#### Step 4: 检查报告

```bash
cat reports/openai_v1_audio_speech_*.json
```

---

### 方法二：添加新的 Provider

假设要添加 Anthropic provider：

#### Step 1: 实现 Provider 适配器

```python
# llm_spec/providers/anthropic.py
from llm_spec.providers.base import ProviderAdapter


class AnthropicAdapter(ProviderAdapter):
    """Anthropic API 适配器"""

    def prepare_headers(self, additional_headers: dict[str, str] | None = None) -> dict[str, str]:
        """准备 Anthropic 请求头

        Anthropic 使用 x-api-key 而非 Authorization
        """
        headers = {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",  # 版本号
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers
```

#### Step 2: 更新配置文件

```toml
# llm-spec.toml
[anthropic]
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com"
timeout = 30.0
```

#### Step 3: 添加 fixture

```python
# tests/conftest.py
from llm_spec.providers.anthropic import AnthropicAdapter

@pytest.fixture(scope="session")
def anthropic_client(config):
    """创建 Anthropic 客户端"""
    provider_config = config.get_provider_config("anthropic")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    return AnthropicAdapter(provider_config, http_client)
```

#### Step 4: 创建 Pydantic Schema

```python
# llm_spec/validation/schemas/anthropic/__init__.py
# llm_spec/validation/schemas/anthropic/messages.py
from pydantic import BaseModel

class AnthropicMessage(BaseModel):
    role: str
    content: str

class AnthropicResponse(BaseModel):
    id: str
    type: str
    role: str
    content: list[dict]
    model: str
    # ... 其他字段
```

#### Step 5: 创建测试文件

```python
# tests/anthropic/test_messages.py
import pytest
from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.anthropic.messages import AnthropicResponse
from llm_spec.validation.validator import ResponseValidator


class TestMessages:
    """Anthropic Messages API 测试类"""

    ENDPOINT = "/v1/messages"

    BASE_PARAMS = {
        "model": "claude-3-opus-20240229",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 1024,
    }

    @pytest.fixture(autouse=True)
    def setup_collector(self, anthropic_client):
        self.client = anthropic_client
        self.collector = ReportCollector(
            provider="anthropic",
            endpoint=self.ENDPOINT,
            base_url=anthropic_client.get_base_url(),
        )
        yield
        report_path = self.collector.finalize()
        print(f"\n报告已生成: {report_path}")

    def test_baseline(self):
        """测试基线"""
        test_name = "test_baseline"

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )

        is_valid, error_msg, missing_fields = ResponseValidator.validate(
            response_body, AnthropicResponse
        )

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
        )

        assert 200 <= status_code < 300
        assert is_valid

    # ... 其他测试方法
```

---

## 测试模式总结

### 模式 1: 基线测试
**目的**：验证仅使用必需参数时API是否正常工作
```python
def test_baseline(self):
    params = self.BASE_PARAMS
    # 发起请求，验证响应
```

### 模式 2: 单参数测试
**目的**：测试某个可选参数是否被支持
```python
def test_param_temperature(self):
    params = {**self.BASE_PARAMS, "temperature": 0.7}
    # 如果失败，记录不支持
```

### 模式 3: 依赖参数测试
**目的**：测试需要多个参数配合的场景
```python
def test_param_tools(self):
    params = {
        **self.BASE_PARAMS,
        "tools": [...],
        "tool_choice": "auto",  # 依赖 tools
    }
```

### 模式 4: 参数变体测试
**目的**：测试参数的所有可能值
```python
@pytest.mark.parametrize("voice", ["alloy", "echo", "fable", ...])
def test_voice_variants(self, voice):
    params = {**self.BASE_PARAMS, "voice": voice}
    # 精确报告哪个值不支持
```

### 模式 5: 流式测试
**目的**：测试SSE流式响应
```python
# 示例 1: 简单流式测试（同步）
def test_streaming_baseline(self):
    params = {**self.BASE_PARAMS}

    chunks = []
    complete_content = ""

    for chunk_bytes in self.client.stream(endpoint=self.ENDPOINT, params=params):
        chunk_str = chunk_bytes.decode("utf-8")

        for line in chunk_str.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue

            data_str = line[6:]  # 移除 "data: " 前缀
            if data_str == "[DONE]":
                break

            chunk_data = json.loads(data_str)
            chunks.append(chunk_data)

            # 验证每个chunk符合schema
            is_valid, error_msg, _, _ = ResponseValidator.validate(
                chunk_data, GenerateContentResponse
            )

            # 累积文本内容
            if chunk_data.get("candidates"):
                for candidate in chunk_data["candidates"]:
                    if candidate.get("content"):
                        for part in candidate["content"].get("parts", []):
                            if part.get("text"):
                                complete_content += part["text"]

    assert len(chunks) > 0
    assert len(complete_content) > 0

# 示例 2: 异步流式测试
async def test_streaming_async(self):
    params = {**self.BASE_PARAMS, "stream": True}

    chunks = []
    async for chunk in self.client.stream_async(self.ENDPOINT, params):
        # 逐chunk验证
        chunks.append(chunk)

    # 验证完整响应
```

**Gemini StreamGenerateContent 测试结构**（15个测试分5个阶段）：
1. **基础流式测试** (3个): baseline、chunk验证、内容累积
2. **生成配置参数** (4个): temperature、maxOutputTokens、topP/topK、stopSequences
3. **多模态流式** (3个): 图片分析、多轮对话、系统指令
4. **高级功能** (3个): 函数调用、JSON模式、安全设置
5. **流式特性验证** (2个): usage metadata、finish reason

### 模式 6: 批处理测试
**目的**：测试异步批量处理API，支持成本优化
```python
class TestBatchGenerateContent:
    """Batch Generate Content API 异步批处理测试"""

    ENDPOINT_CREATE = "/v1beta/models/gemini-3-flash-preview:batchGenerateContent"
    ENDPOINT_GET = "/v1beta/batches/{batch_id}"

    BASE_PARAMS = {
        "requests": [
            {"contents": [{"parts": [{"text": "Request 1"}]}]},
            {"contents": [{"parts": [{"text": "Request 2"}]}]},
        ]
    }

    def test_batch_baseline(self):
        # 1. 创建批任务（异步）
        status_code, headers, response = self.client.request(
            endpoint=self.ENDPOINT_CREATE,
            params=self.BASE_PARAMS,
        )

        # 2. 验证创建响应
        is_valid, error_msg = ResponseValidator.validate(
            response, BatchCreateResponse
        )

        # 3. 轮询查询任务状态
        batch_name = response.get("name")
        final_status = self._poll_batch_status(batch_name)

        # 4. 记录测试
        self.collector.record_test(...)
```

**Gemini BatchGenerateContent 测试结构**（21个测试分6个阶段）：
1. **基础批处理** (4个): baseline、多请求、显示名称、状态查询
2. **批配置参数** (3个): 生成配置、安全设置、系统指令
3. **请求内容变体** (6个): 纯文本、内联图像、函数调用、JSON模式、混合内容
4. **批量大小和混合** (2个): 不同批大小变体、混合参数
5. **响应字段验证** (2个): 必需字段、元数据验证
6. **错误和边界情况** (4个): 空列表、无效格式、超时配置、状态追踪

---

## 报告格式说明

生成的报告包含三种格式：

### 1. JSON 报告（report.json）

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
        "reason": "参数不支持"
      }
    ]
  },
  "response_fields": {
    "expected": [],
    "unsupported": []
  },
  "errors": []
}
```

### 2. Markdown 报告（parameters.md）

```markdown
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

### 3. HTML 报告（report.html）

- 美观的响应式设计
- 统计信息卡片（总数、通过、失败、支持率）
- 参数详情表格（参数名、支持状态）
- 自适应布局

**报告目录结构**：
每个测试生成一个独立的子目录，包含所有三种格式的报告：
```
reports/
├── openai_v1_chat_completions_20260129_191805/
│   ├── report.json
│   ├── parameters.md
│   └── report.html
├── openai_v1_embeddings_20260129_191805/
│   ├── report.json
│   ├── parameters.md
│   └── report.html
└── gemini_v1beta_models_gemini-3-flash-preview:batchGenerateContent_20260129_191805/
    ├── report.json
    ├── parameters.md
    └── report.html
```

---

## 常见问题

### Q: 如何测试需要上传文件的endpoint（如图片编辑）？

使用 `test_assets` fixture：

```python
@pytest.fixture
def test_image(test_assets):
    """提供测试图片路径"""
    return test_assets / "images" / "test.png"

def test_image_edit(self, test_image):
    with open(test_image, "rb") as f:
        files = {"image": f}
        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
            files=files,
        )
```

### Q: 如何处理二进制响应（如音频、图片）？

不验证响应体内容，只验证HTTP状态码和Content-Type：

```python
assert 200 <= status_code < 300
assert "audio/mpeg" in headers.get("content-type", "")
```

### Q: 如何测试流式endpoint？

使用异步流式方法：

```python
async def test_streaming(self):
    params = {**self.BASE_PARAMS, "stream": True}

    complete_response = ""
    async for chunk in self.client.stream_async(self.ENDPOINT, params):
        # 解析SSE格式
        if chunk.startswith(b"data: "):
            data = json.loads(chunk[6:])
            # 验证chunk格式
            complete_response += data.get("content", "")

    # 验证完整响应
    assert len(complete_response) > 0
```

---

## 最佳实践

1. **参数定义在顶层**：所有测试参数在类常量中显式定义
2. **一次测一个**：每个测试方法只测试一个新参数（控制变量）
3. **失败即记录**：不支持的参数立即调用 `add_unsupported_param()`
4. **完整的错误信息**：reason中包含HTTP状态码和响应体
5. **独立的报告**：每个endpoint生成独立的JSON报告
6. **日志追踪**：每个请求有唯一request_id，便于日志查询
7. **测试隔离**：每个测试类有独立的ReportCollector实例

---

## 扩展建议

### 短期
- [x] 添加更多OpenAI endpoints（audio, images, embeddings等）
- [x] 添加流式响应的完整验证逻辑
- [x] 完善 Gemini provider 和测试覆盖
- [x] 实现参数表格生成系统（JSON → Markdown/HTML）✅
- [ ] 实现汇总报告（多个测试的综合统计）

### 中期
- [x] 实现 Gemini provider ✅
- [x] 完善 Anthropic provider ✅
- [ ] 完善 xAI provider
- [ ] 支持从YAML/JSON规范文件自动生成测试
- [ ] 添加并发测试支持（pytest-xdist）
- [ ] 实现报告自动清理（保留最近N次测试）

### 长期
- [ ] 实现自动化CI/CD测试流程
- [ ] 支持性能基准测试（响应时间统计）
- [ ] 生成对比报告（新旧版本API差异）
- [ ] 实现Web UI查看报告

---


