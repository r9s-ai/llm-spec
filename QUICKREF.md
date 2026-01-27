# 快速参考指南 (Quick Reference)

## 文件位置速查

| 组件 | 文件路径 | 用途 |
|------|---------|------|
| 配置文件 | `llm-spec.toml` | Provider配置、日志配置、报告配置 |
| 测试用例 | `tests/providers/{provider}/test_{endpoint}.py` | 具体的endpoint测试 |
| Provider适配器 | `llm_spec/providers/{provider}.py` | 各厂商API适配 |
| 响应Schema | `llm_spec/validation/schemas/{provider}/{endpoint}.py` | Pydantic响应模型 |
| 测试报告 | `reports/{provider}_{endpoint}_{timestamp}.json` | 自动生成的测试报告 |
| 日志文件 | `logs/llm-spec.log` | 请求/响应日志 |

## 常用命令

```bash
# 运行所有测试
pytest tests/ -v

# 运行单个Provider的所有测试
pytest tests/providers/openai/ -v

# 运行单个Endpoint测试
pytest tests/providers/openai/test_chat_completions.py -v

# 运行单个测试方法
pytest tests/providers/openai/test_chat_completions.py::TestChatCompletions::test_baseline -v

# 运行测试并显示详细输出
pytest tests/ -v -s

# 运行测试并生成覆盖率报告
pytest tests/ --cov=llm_spec --cov-report=html

# 查看最新报告
ls -lt reports/ | head -5
cat reports/$(ls -t reports/ | head -1)
```

## 代码模板

### 1. 添加新Endpoint测试模板

```python
# tests/providers/openai/test_{endpoint_name}.py
import pytest
from llm_spec.reporting.collector import ReportCollector
from llm_spec.validation.schemas.openai.{module} import {ResponseModel}
from llm_spec.validation.validator import ResponseValidator


class Test{EndpointName}:
    """【API名称】测试类"""

    ENDPOINT = "/v1/{endpoint/path}"

    # 基线参数：仅包含必需参数
    BASE_PARAMS = {
        "required_param1": "value1",
        "required_param2": "value2",
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
        report_path = self.collector.finalize()
        print(f"\n报告已生成: {report_path}")

    def test_baseline(self):
        """测试基线：仅必需参数"""
        test_name = "test_baseline"

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=self.BASE_PARAMS,
        )

        is_valid, error_msg, missing_fields = ResponseValidator.validate(
            response_body, {ResponseModel}
        )

        self.collector.record_test(
            test_name=test_name,
            params=self.BASE_PARAMS,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
        )

        assert 200 <= status_code < 300, f"HTTP {status_code}: {response_body}"
        assert is_valid, f"响应验证失败: {error_msg}"

    def test_param_{param_name}(self):
        """测试 {param_name} 参数"""
        test_name = "test_param_{param_name}"
        params = {**self.BASE_PARAMS, "{param_name}": {value}}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields = ResponseValidator.validate(
            response_body, {ResponseModel}
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="{param_name}",
                param_value={value},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid

    @pytest.mark.parametrize("{param_name}", [{value1}, {value2}, {value3}])
    def test_{param_name}_variants(self, {param_name}):
        """测试不同的 {param_name} 变体"""
        test_name = f"test_{param_name}_variants[{{param_name}}]"
        params = {**self.BASE_PARAMS, "{param_name}": {param_name}}

        status_code, headers, response_body = self.client.request(
            endpoint=self.ENDPOINT,
            params=params,
        )

        is_valid, error_msg, missing_fields = ResponseValidator.validate(
            response_body, {ResponseModel}
        )

        self.collector.record_test(
            test_name=test_name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_msg if not is_valid else None,
            missing_fields=missing_fields,
        )

        if not (200 <= status_code < 300):
            self.collector.add_unsupported_param(
                param_name="{param_name}",
                param_value={param_name},
                test_name=test_name,
                reason=f"HTTP {status_code}: {response_body}",
            )

        assert 200 <= status_code < 300
        assert is_valid
```

### 2. 添加新Provider适配器模板

```python
# llm_spec/providers/{provider_name}.py
from llm_spec.providers.base import ProviderAdapter


class {ProviderName}Adapter(ProviderAdapter):
    """{Provider显示名称} API 适配器"""

    def prepare_headers(self, additional_headers: dict[str, str] | None = None) -> dict[str, str]:
        """准备 {Provider显示名称} 请求头

        Args:
            additional_headers: 额外的请求头

        Returns:
            包含认证的完整请求头
        """
        headers = {
            # 根据Provider的文档填写认证方式
            "Authorization": f"Bearer {self.config.api_key}",
            # 或
            # "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers
```

### 3. 添加Pydantic Schema模板

```python
# llm_spec/validation/schemas/{provider}/{module}.py
from typing import Literal
from pydantic import BaseModel, Field


class {SubModel}(BaseModel):
    """子模型描述"""
    field1: str
    field2: int
    optional_field: str | None = None


class {MainResponse}(BaseModel):
    """主响应模型描述"""

    # 必需字段
    id: str
    object: Literal["{expected_value}"]
    created: int

    # 可选字段
    optional_field: str | None = None

    # 嵌套模型
    items: list[{SubModel}]
```

### 4. 添加Pytest Fixture模板

```python
# tests/conftest.py
from llm_spec.providers.{provider_name} import {ProviderName}Adapter

@pytest.fixture(scope="session")
def {provider}_client(config):
    """创建 {Provider显示名称} 客户端"""
    provider_config = config.get_provider_config("{provider}")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger, default_timeout=provider_config.timeout)
    return {ProviderName}Adapter(provider_config, http_client)
```

### 5. 配置文件模板

```toml
# llm-spec.toml
[{provider}]
api_key = "your-api-key-here"
base_url = "https://api.{provider}.com"
timeout = 30.0
```

## 调试技巧

### 查看请求/响应日志

```bash
# 实时查看日志
tail -f logs/llm-spec.log

# 查找特定request_id的日志
grep "abc-123-def" logs/llm-spec.log

# 查看最近的错误
grep "ERROR" logs/llm-spec.log | tail -20
```

### 查看测试报告

```bash
# 查看最新报告（格式化输出）
cat reports/$(ls -t reports/ | head -1) | python -m json.tool

# 提取不支持的参数
cat reports/*.json | jq '.parameters.unsupported'

# 统计测试结果
cat reports/*.json | jq '.test_summary'

# 查看响应字段列表（包括嵌套字段）
cat reports/*.json | jq '.response_fields.expected'
```

### 报告格式示例

生成的JSON报告中，`response_fields.expected` 包含递归提取的所有字段（包括嵌套字段）：

```json
{
  "response_fields": {
    "expected": [
      "id",
      "object",
      "created",
      "model",
      "choices",
      "choices.index",
      "choices.message",
      "choices.message.role",
      "choices.message.content",
      "choices.message.tool_calls",
      "choices.message.tool_calls.id",
      "choices.message.tool_calls.type",
      "choices.message.tool_calls.function",
      "choices.message.tool_calls.function.name",
      "choices.message.tool_calls.function.arguments",
      "choices.finish_reason",
      "choices.logprobs",
      "choices.logprobs.content",
      "choices.logprobs.content.token",
      "choices.logprobs.content.logprob",
      "choices.logprobs.content.bytes",
      "choices.logprobs.content.top_logprobs",
      "choices.logprobs.content.top_logprobs.token",
      "choices.logprobs.content.top_logprobs.logprob",
      "choices.logprobs.content.top_logprobs.bytes",
      "usage",
      "usage.prompt_tokens",
      "usage.completion_tokens",
      "usage.total_tokens",
      "system_fingerprint"
    ],
    "unsupported": []
  }
}
```

**字段路径说明**：
- 顶层字段：`id`, `model`, `choices`, `usage`
- 一级嵌套：`choices.message`, `usage.prompt_tokens`
- 二级嵌套：`choices.message.role`, `choices.message.tool_calls`
- 三级嵌套：`choices.message.tool_calls.function`
- 四级嵌套：`choices.message.tool_calls.function.name`

字段路径使用点号（`.`）分隔嵌套层级，自动从 Pydantic schema 中递归提取。

### 运行单个测试并保留输出

```bash
pytest tests/providers/openai/test_chat_completions.py::TestChatCompletions::test_baseline -v -s --tb=short
```

### 使用Python调试器

```python
# 在测试代码中添加断点
def test_baseline(self):
    import pdb; pdb.set_trace()  # 断点
    status_code, headers, response_body = self.client.request(...)
```

## 常见问题解决

### 问题1：配置文件找不到

```bash
# 确保在项目根目录运行测试
cd /path/to/llm-spec
pytest tests/

# 或指定配置文件路径
export LLM_SPEC_CONFIG=/path/to/llm-spec.toml
```

### 问题2：导入错误

```bash
# 确保安装了项目
pip install -e .

# 或添加到PYTHONPATH
export PYTHONPATH=/path/to/llm-spec:$PYTHONPATH
```

### 问题3：API认证失败

```toml
# 检查llm-spec.toml中的配置
[openai]
api_key = "sk-..."  # 确保API key正确
base_url = "https://api.openai.com"  # 确保base_url正确（不包含/v1）
```

### 问题4：响应验证失败但API调用成功

可能是Pydantic schema定义不匹配：

```python
# 临时禁用验证，查看实际响应
print(json.dumps(response_body, indent=2))

# 更新schema以匹配实际响应
```

## 测试最佳实践

1. **参数组织**
   ```python
   # ✅ 好的做法
   class TestAPI:
       BASE_PARAMS = {"model": "gpt-4", "messages": [...]}

       def test_param_temperature(self):
           params = {**self.BASE_PARAMS, "temperature": 0.7}

   # ❌ 避免
   def test_param_temperature(self):
       params = {"model": "gpt-4", "messages": [...], "temperature": 0.7}  # 重复定义
   ```

2. **错误处理**
   ```python
   # ✅ 记录不支持的参数
   if not (200 <= status_code < 300):
       self.collector.add_unsupported_param(
           param_name="param",
           param_value=value,
           test_name=test_name,
           reason=f"HTTP {status_code}: {response_body}",
       )

   # ❌ 不要静默失败
   try:
       assert status_code == 200
   except:
       pass  # 不记录错误
   ```

3. **测试命名**
   ```python
   # ✅ 清晰的测试名称
   def test_baseline(self):
   def test_param_temperature(self):
   def test_model_variants(self, model):

   # ❌ 模糊的测试名称
   def test_1(self):
   def test_api(self):
   ```

## 性能优化

### 并行测试

```bash
# 使用pytest-xdist并行运行测试
pytest tests/ -n auto -v

# 指定worker数量
pytest tests/ -n 4 -v
```

### 跳过慢速测试

```python
@pytest.mark.slow
def test_large_file_upload(self):
    # 耗时的测试
    pass

# 运行时跳过
pytest tests/ -v -m "not slow"
```

## 目录结构约定

```
tests/providers/{provider}/
  ├── test_chat_completions.py      # /v1/chat/completions
  ├── test_audio_speech.py           # /v1/audio/speech
  ├── test_audio_transcriptions.py  # /v1/audio/transcriptions
  ├── test_audio_translations.py    # /v1/audio/translations
  ├── test_images_generations.py    # /v1/images/generations
  └── test_embeddings.py             # /v1/embeddings

llm_spec/validation/schemas/{provider}/
  ├── chat.py          # Chat相关的schemas
  ├── audio.py         # Audio相关的schemas
  ├── images.py        # Images相关的schemas
  └── embeddings.py    # Embeddings相关的schemas
```

## 环境变量

```bash
# 覆盖配置文件中的设置
export OPENAI_API_KEY="sk-override-key"
export OPENAI_BASE_URL="https://custom.api.com"

# 启用调试模式
export LLM_SPEC_DEBUG=1

# 指定配置文件
export LLM_SPEC_CONFIG="/custom/path/config.toml"
```

## Git 忽略规则

```gitignore
# .gitignore
logs/
reports/
temp/
.pytest_cache/
__pycache__/
*.pyc
.coverage
htmlcov/
llm-spec.toml  # 包含敏感API key，不提交
```

提交前确保有 `llm-spec.example.toml` 作为模板。
