# LLM-Spec 项目指南

本文档为 AI Agent 和开发者提供项目规范，确保开发风格一致。

## 项目概述

LLM-Spec 是一个用于验证各家 LLM API 响应是否符合官方规范的测试框架。

**支持的 Provider：**
- OpenAI
- Anthropic
- Google Gemini
- xAI (Grok)

**核心功能：**
1. 使用 Pydantic 定义各 API 的 request/response schema
2. 封装 sync/async/stream HTTP client (基于 httpx)
3. 字段级别的验证报告（哪些字段正确/错误/缺失/多余）
4. 支持终端彩色输出和 JSON 格式报告

## 目录结构

```
llm-spec/
├── llm_spec/
│   ├── __init__.py              # 包入口，导出主要接口
│   ├── core/                    # 核心抽象层
│   │   ├── __init__.py
│   │   ├── client.py            # BaseClient 基类
│   │   ├── config.py            # 全局/局部配置管理
│   │   ├── report.py            # ValidationReport, FieldResult
│   │   ├── validator.py         # 字段级验证逻辑
│   │   └── registry.py          # Provider 自动发现机制
│   │
│   └── providers/               # 各厂商实现（自包含）
│       ├── __init__.py
│       ├── openai/
│       │   ├── __init__.py      # 导出 Client 和 Schemas
│       │   ├── client.py        # OpenAIClient
│       │   ├── schemas.py       # Pydantic 模型定义
│       │   └── tests.py         # 该厂商的测试用例
│       ├── anthropic/
│       ├── gemini/
│       └── xai/
│
├── tests/                       # pytest 测试入口
│   ├── conftest.py              # pytest fixtures
│   └── test_*.py                # 集成测试
│
├── pyproject.toml               # 项目配置和依赖
├── CLAUDE.md                    # 本文件
└── README.md                    # 用户文档
```

## 代码规范

### Python 版本
- 最低支持 Python 3.11
- 使用现代类型注解语法（`str | None` 而非 `Optional[str]`）

### 类型注解
- 所有公开函数必须有完整的类型注解
- 使用 `from __future__ import annotations` 延迟注解求值
- 复杂类型使用 TypeAlias 定义

```python
from __future__ import annotations
from typing import TypeAlias

JsonDict: TypeAlias = dict[str, Any]
```

### Pydantic 使用规范
- 统一使用 Pydantic v2 语法
- Schema 类继承 `BaseModel`
- 使用 `Field()` 定义字段元数据
- 可选字段显式标注 `field: str | None = None`

```python
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色")
    content: str | None = Field(default=None, description="消息内容")
```

### 异步规范
- Client 同时提供同步和异步方法
- 异步方法使用 `async_` 前缀：`request()` / `async_request()`
- 内部使用 httpx 的 `Client` 和 `AsyncClient`

```python
class BaseClient:
    def request(self, ...) -> Response:
        """同步请求"""

    async def async_request(self, ...) -> Response:
        """异步请求"""

    def stream(self, ...) -> Iterator[Chunk]:
        """同步流式请求"""

    async def async_stream(self, ...) -> AsyncIterator[Chunk]:
        """异步流式请求"""
```

### 配置优先级
从高到低：
1. 方法参数（局部覆盖）
2. Client 实例化参数
3. 环境变量（如 `OPENAI_API_KEY`）
4. 配置文件（可选）
5. 默认值

### 命名规范
- 类名：PascalCase（`OpenAIClient`, `ChatCompletionRequest`）
- 函数/方法：snake_case（`validate_response`, `to_json`）
- 常量：UPPER_SNAKE_CASE（`DEFAULT_TIMEOUT`）
- 私有成员：单下划线前缀（`_http_client`）

### 错误处理
- 自定义异常继承自 `LLMSpecError` 基类
- 网络错误：`RequestError`
- 验证错误：`ValidationError`
- 配置错误：`ConfigError`

```python
# core/exceptions.py
class LLMSpecError(Exception):
    """基础异常类"""

class RequestError(LLMSpecError):
    """HTTP 请求错误"""

class ValidationError(LLMSpecError):
    """Schema 验证错误"""
```

## 添加新 Provider 指南

1. 在 `providers/` 下创建新目录：
```bash
mkdir llm_spec/providers/new_provider
```

2. 创建必要文件：
```
new_provider/
├── __init__.py      # 导出公开接口
├── client.py        # 继承 BaseClient
├── schemas.py       # 定义 Request/Response 模型
└── tests.py         # 验证测试用例
```

3. 在 `__init__.py` 中导出：
```python
from .client import NewProviderClient
from .schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)

__all__ = [
    "NewProviderClient",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
]
```

4. Client 实现模板：
```python
from llm_spec.core.client import BaseClient
from llm_spec.core.report import ValidationReport

class NewProviderClient(BaseClient):
    provider_name = "new_provider"
    default_base_url = "https://api.newprovider.com/v1"

    def validate_chat_completion(self, **kwargs) -> ValidationReport:
        """验证 chat completion 接口"""
        ...
```

## 验证报告规范

### FieldStatus 枚举
- `VALID`: 字段存在且类型正确
- `INVALID_TYPE`: 字段存在但类型不匹配
- `MISSING`: 必填字段缺失
- `UNEXPECTED`: API 返回了 schema 未定义的字段

### 字段路径格式
使用点号和方括号表示嵌套：
- `id` - 顶层字段
- `choices[0].message.content` - 数组元素的嵌套字段
- `usage.prompt_tokens` - 对象嵌套

## 测试规范

### 单元测试
- 使用 pytest
- Mock 外部 API 调用
- 测试文件命名：`test_*.py`

### 集成测试（实际调用 API）
- 需要配置真实 API Key
- 使用 `@pytest.mark.integration` 标记
- CI 中可选择性跳过

```python
@pytest.mark.integration
def test_openai_chat_completion():
    """需要真实 API Key 的集成测试"""
    ...
```

### Targeted Parameter Testing (目标参数测试)
为确保测试报告的精确性，避免 False Negatives（即因为 A 参数失败导致 B 参数被误判为 Unsupported），应使用 **Targeted Testing** 模式：

1. **原则**：每个测试用例应明确指定其主要验证的参数 (`_test_param`)。
2. **行为**：如果测试失败，系统仅将失败归咎于目标参数，同一请求中的其他参数仍被视为 Effective/Supported。
3. **变体**：支持指定 `_test_variant` 来描述具体不支持的用法（如 "string array" vs "string"）。

```python
def test_param_input_list(self, openai_client):
    """测试 input 参数的数组形式"""
    openai_client.validate_responses(
        # 基础参数确保请求有效
        model="gpt-4o",
        max_output_tokens=50,
        
        # 待测参数
        input=["Hello", "World"],
        
        # 元数据：指定这是针对 input 的 "string array" 变体验证
        _test_param="input",
        _test_variant="string array",
    )
```

## 依赖管理

核心依赖：
- `httpx` - HTTP 客户端
- `pydantic` >= 2.0 - 数据验证
- `pydantic-settings` - 配置管理
- `rich` - 终端美化输出

开发依赖：
- `pytest` - 测试框架
- `pytest-asyncio` - 异步测试支持
- `ruff` - 代码检查和格式化

## 常用命令

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest

# 运行集成测试（需要 API Key）
pytest -m integration

# 代码检查
ruff check .

# 代码格式化
ruff format .
```
