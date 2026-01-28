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
│   │       │   ├── generate_content.py  # GenerateContent API
│   │       │   ├── embeddings.py        # EmbedContent API
│   │       │   └── tokens.py            # CountTokens API
│   │       ├── anthropic/         # Anthropic schemas ✅
│   │       │   ├── __init__.py
│   │       │   └── messages.py         # Messages API
│   │       └── xai/               # xAI schemas
│   │           └── __init__.py
│   └── reporting/                 # 报告系统
│       ├── __init__.py
│       ├── collector.py           # 测试结果收集器
│       └── generator.py           # 报告生成器（待实现）
├── tests/                         # 测试代码
│   ├── __init__.py
│   ├── conftest.py                # Pytest全局fixtures
│   └── providers/
│       ├── __init__.py
│       ├── openai/                # OpenAI 测试 ✅
│       │   ├── __init__.py
│       │   ├── test_chat_completions.py
│       │   ├── test_audio_speech.py
│       │   ├── test_audio_transcriptions.py
│       │   ├── test_audio_translations.py
│       │   ├── test_embeddings.py
│       │   ├── test_images_generations.py
│       │   └── test_responses.py
│       ├── gemini/                # Gemini 测试 ✅
│       │   ├── __init__.py
│       │   ├── test_generate_content.py
│       │   ├── test_embed_content.py
│       │   └── test_count_tokens.py
│       ├── anthropic/             # Anthropic 测试 ✅
│       │   ├── __init__.py
│       │   ├── test_messages_basic.py
│       │   ├── test_messages_advanced.py
│       │   ├── test_messages_tools.py
│       │   └── test_messages_streaming.py
│       └── xai/                   # xAI 测试
│           ├── __init__.py
│           └── test_chat_completions.py
├── test_assets/                   # 测试资源文件
│   ├── audio/                     # 音频文件
│   └── images/                    # 图片文件
├── temp/                          # 临时文件（按时间戳分目录）
├── reports/                       # 生成的JSON报告
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
**职责**：测试结果汇总和报告生成
- 收集测试参数、状态码、错误信息
- 跟踪不支持的参数和缺失的响应字段
- 生成JSON格式报告

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
# tests/providers/openai/test_audio_speech.py
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
pytest tests/providers/openai/test_audio_speech.py -v
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
# tests/providers/anthropic/test_messages.py
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
async def test_streaming(self):
    params = {**self.BASE_PARAMS, "stream": True}

    chunks = []
    async for chunk in self.client.stream_async(self.ENDPOINT, params):
        # 逐chunk验证
        chunks.append(chunk)

    # 验证完整响应
```

---

## 报告格式说明

生成的JSON报告包含：

```json
{
  "test_time": "测试时间",
  "provider": "provider名称",
  "endpoint": "API端点路径",
  "base_url": "基础URL",
  "test_summary": {
    "total_tests": "总测试数",
    "passed": "通过数",
    "failed": "失败数"
  },
  "parameters": {
    "tested": ["实际测试过的参数列表"],
    "untested": ["规范中有但未测试的参数"],
    "unsupported": [
      {
        "parameter": "参数名",
        "value": "参数值",
        "test_name": "测试名称",
        "reason": "不支持的原因（HTTP状态码+错误信息）"
      }
    ]
  },
  "response_fields": {
    "expected": [
      "顶层字段和所有嵌套字段（使用点号分隔）",
      "例如: id, object, created, choices, choices.index,",
      "choices.message, choices.message.role, choices.message.content,",
      "usage, usage.prompt_tokens, usage.completion_tokens"
    ],
    "unsupported": [
      {
        "field": "字段名",
        "test_name": "测试名称",
        "reason": "缺失原因"
      }
    ]
  },
  "errors": [
    {
      "test_name": "测试名称",
      "type": "错误类型",
      "message": "详细错误信息"
    }
  ]
}
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
- [ ] 实现Terminal格式报告输出（使用rich库）

### 中期
- [x] 实现 Gemini provider ✅
- [x] 完善 Anthropic provider ✅
- [ ] 完善 xAI provider
- [ ] 支持从YAML/JSON规范文件自动生成测试
- [ ] 添加并发测试支持（pytest-xdist）

### 长期
- [ ] 实现自动化CI/CD测试流程
- [ ] 生成HTML格式的测试报告
- [ ] 支持性能基准测试（响应时间统计）

---

## Anthropic Provider 实现详情

### Schema 结构

Anthropic 的 schema 提供完整的 Messages API 支持：

**llm_spec/validation/schemas/anthropic/messages.py**
- **请求相关类**：
  - `Role`, `TextBlock`, `ImageBlock`, `ToolUseBlock`, `ToolResultBlock`
  - `Message`, `Tool`, `ToolChoice`, `Metadata`, `ThinkingConfig`
  - `ImageSource` - 支持 base64 和 URL 两种图片输入方式

- **响应相关类**：
  - `MessagesResponse` - 标准响应格式
  - `Usage` - Token 使用统计（支持 prompt caching）
  - `StopReason` - 停止原因枚举

- **流式响应事件**：
  - `MessageStartEvent` - 消息开始
  - `ContentBlockStartEvent` - 内容块开始
  - `ContentBlockDeltaEvent` - 内容增量（text_delta / input_json_delta）
  - `ContentBlockStopEvent` - 内容块结束
  - `MessageDeltaEvent` - 消息增量
  - `MessageStopEvent` - 消息结束
  - `PingEvent`, `ErrorEvent` - 辅助事件

### 测试覆盖

**tests/providers/anthropic/** (48个测试，2479行代码)

#### test_messages_basic.py (13个测试，539行)
- **阶段 1**: 基线与模型测试
  - `test_baseline` - 仅必需参数
  - `test_model_variants[5个模型]` - claude-3-5-sonnet, opus, haiku, 3-5-haiku, sonnet-4-5

- **阶段 2**: 采样参数测试
  - `test_param_temperature` - temperature 参数
  - `test_param_top_p` - top_p 参数
  - `test_param_top_k` - top_k 参数
  - `test_param_combined_sampling` - 组合采样参数

- **阶段 3**: 停止控制测试
  - `test_param_stop_sequences` - 自定义停止序列
  - `test_param_max_tokens_minimum` - max_tokens 边界测试（最小值）
  - `test_param_max_tokens_maximum` - max_tokens 边界测试（8192）

- **阶段 4**: 系统提示测试
  - `test_param_system` - system prompt 参数
  - `test_system_with_multiline` - 多行系统提示
  - `test_system_with_complex_instructions` - 复杂系统指令

- **阶段 5**: 元数据与追踪
  - `test_param_metadata` - metadata.user_id 追踪

#### test_messages_advanced.py (13个测试，572行)
- **阶段 1**: 多轮对话测试
  - `test_multi_turn_conversation` - 多轮对话历史
  - `test_alternating_roles` - 角色交替验证
  - `test_long_conversation_history` - 长对话（10轮）

- **阶段 2**: 多模态内容测试
  - `test_param_image_base64` - base64 图片输入
  - `test_image_media_type_variants[4种格式]` - jpeg/png/gif/webp
  - `test_text_and_image_combined` - 文本+图片混合

- **阶段 3**: 内容块格式测试
  - `test_content_as_string` - 字符串格式 content
  - `test_content_as_blocks` - 块数组格式 content
  - `test_multiple_text_blocks` - 多个文本块

- **阶段 4**: 思考模式测试（Claude 3.7+）
  - `test_param_thinking_enabled` - 启用思考模式
  - `test_param_thinking_budget_tokens` - 思考 token 预算

#### test_messages_tools.py (12个测试，734行)
- **阶段 1**: 基础工具调用
  - `test_param_tools_basic` - 基础工具定义
  - `test_tool_use_response` - 工具调用响应验证
  - `test_tool_result_submission` - 提交工具结果

- **阶段 2**: 工具选择策略
  - `test_tool_choice_auto` - 自动选择
  - `test_tool_choice_any` - 强制使用任意工具
  - `test_tool_choice_specific_tool` - 指定特定工具

- **阶段 3**: 复杂工具场景
  - `test_multiple_tools` - 多个工具定义
  - `test_tool_with_complex_schema` - 复杂嵌套 schema
  - `test_parallel_tool_use` - 并行工具调用
  - `test_multi_turn_tool_conversation` - 多轮工具对话

- **阶段 4**: 工具错误处理
  - `test_tool_result_with_error` - is_error 标志
  - `test_tool_without_tool_choice` - 无 tool_choice 参数

#### test_messages_streaming.py (10个测试，634行)
- **阶段 1**: 基础流式测试
  - `test_streaming_basic` - 基础流式响应
  - `test_streaming_event_types` - 所有事件类型验证

- **阶段 2**: 流式内容验证
  - `test_streaming_text_accumulation` - 文本累积
  - `test_streaming_usage_tracking` - usage 统计
  - `test_streaming_stop_reason` - stop_reason 验证

- **阶段 3**: 流式工具调用
  - `test_streaming_tool_use` - 流式工具调用
  - `test_streaming_input_json_delta` - input_json_delta 事件

- **阶段 4**: 流式错误处理
  - `test_streaming_error_event` - 错误事件
  - `test_streaming_ping_event` - ping 事件

### Anthropic API 特性

**与 OpenAI 的主要区别：**

1. **API Key 传递方式**
   - OpenAI: `Authorization: Bearer {api_key}` header
   - Anthropic: `x-api-key: {api_key}` header

2. **必需参数**
   - Anthropic 强制要求 `max_tokens` 参数
   - 需要明确的 `anthropic-version` header（如 "2023-06-01"）

3. **角色系统**
   - `system` 参数独立于 messages 数组
   - messages 只支持 `user` 和 `assistant` 角色

4. **内容块结构**
   - 支持丰富的内容块类型：text, image, tool_use, tool_result
   - content 可以是字符串或块数组

5. **工具调用**
   - 原生支持工具调用（tool_use / tool_result 块）
   - 支持 tool_choice：auto / any / tool（指定特定工具）
   - 流式响应中支持 input_json_delta 增量更新

6. **思考模式（Extended Thinking）**
   - Claude 3.7+ 支持 thinking 配置
   - 可设置 budget_tokens 控制思考深度

7. **Prompt Caching**
   - Usage 字段包含 cache_creation_input_tokens 和 cache_read_input_tokens
   - 支持对系统提示和对话历史的缓存

8. **流式响应**
   - SSE (Server-Sent Events) 格式
   - 7种事件类型：message_start, content_block_start/delta/stop, message_delta/stop, ping, error

---

## Gemini Provider 实现详情

### Schema 结构

Gemini 的 schema 按照 API endpoints 拆分为独立文件：

**llm_spec/validation/schemas/gemini/**
- **generate_content.py** - GenerateContent API 相关 schema
  - 请求类：`Part`, `Content`, `Tool`, `SafetySetting`, `GenerationConfig`, `SystemInstruction` 等
  - 响应类：`Candidate`, `SafetyRating`, `UsageMetadata`, `GenerateContentResponse` 等
  - 类型别名：`HarmCategory`, `HarmBlockThreshold`, `FinishReason`, `BlockReason` 等

- **embeddings.py** - EmbedContent/BatchEmbedContents API
  - `TaskType` 枚举（9种任务类型）
  - `EmbedContentRequest`, `Embedding`, `EmbedContentResponse`, `BatchEmbedContentsResponse`

- **tokens.py** - CountTokens API
  - `CountTokensResponse`, `ModalityTokenDetails`

### 测试覆盖

**tests/providers/gemini/**

#### test_generate_content.py (17个测试)
- **阶段 1**: 基线测试
  - `test_baseline` - 仅必需参数
  - `test_param_temperature` - temperature 参数
  - `test_param_max_output_tokens` - maxOutputTokens 参数

- **阶段 2**: 基础参数测试
  - `test_param_top_p` - topP 参数
  - `test_param_top_k` - topK 参数
  - `test_param_candidate_count` - candidateCount 参数（多个候选响应）
  - `test_param_stop_sequences` - stopSequences 参数

- **阶段 3**: 响应格式测试
  - `test_response_format_json` - JSON 响应格式
  - `test_response_format_json_with_schema` - 带 schema 的 JSON 响应

- **阶段 4**: 安全设置测试
  - `test_param_safety_settings` - safetySettings 基础测试
  - `test_safety_threshold_variants[4个阈值]` - 安全阈值变体测试

- **阶段 5**: 系统指令测试
  - `test_param_system_instruction` - systemInstruction 参数

- **阶段 6**: 工具调用测试
  - `test_param_function_calling` - 函数调用功能
  - `test_param_code_execution` - 代码执行功能

#### test_embed_content.py (11个测试)
- **阶段 1**: 基线测试
  - `test_baseline` - 仅必需参数

- **阶段 2**: TaskType 测试
  - `test_param_task_type_retrieval_query` - RETRIEVAL_QUERY
  - `test_param_task_type_retrieval_document` - RETRIEVAL_DOCUMENT（带 title）
  - `test_task_type_variants[7种]` - 所有 TaskType 变体

- **阶段 3**: 输出维度测试
  - `test_param_output_dimensionality` - outputDimensionality 参数

#### test_count_tokens.py (4个测试)
- **阶段 1**: 基线测试 - `test_baseline`
- **阶段 2**: 多轮对话测试 - `test_multi_turn_conversation`
- **阶段 3**: 系统指令测试 - `test_with_system_instruction`
- **阶段 4**: 工具定义测试 - `test_with_tools`

### Gemini API 特性

**与 OpenAI 的主要区别：**

1. **API Key 传递方式**
   - OpenAI: `Authorization: Bearer {api_key}` header
   - Gemini: URL 参数 `?key={api_key}`

2. **参数结构**
   - OpenAI: 扁平化参数（如 `temperature`, `top_p`）
   - Gemini: 嵌套在 `generationConfig` 中（如 `generationConfig.temperature`）

3. **安全设置**
   - Gemini 提供细粒度的 `safetySettings`（6种类别 × 4种阈值）
   - 包括 `HARM_CATEGORY_HARASSMENT`, `HARM_CATEGORY_HATE_SPEECH` 等

4. **工具能力**
   - 支持 `functionDeclarations`（函数调用）
   - 支持 `codeExecution`（代码执行）

5. **多模态支持**
   - 原生支持 `inlineData`（base64）和 `fileData`（File API）
   - 支持图片、视频、音频、PDF 等多种输入格式

6. **响应结构**
   - 提供 `promptFeedback`（提示词反馈）
   - 包含 `citationMetadata`（引用来源）
   - 支持 `groundingAttributions`（搜索增强）
