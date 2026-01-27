# 数据流和架构说明

## 整体数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                        测试层 (tests/)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  TestChatCompletions                                     │  │
│  │    - ENDPOINT = "/v1/chat/completions"                   │  │
│  │    - BASE_PARAMS = {...}                                 │  │
│  │    - test_baseline()                                     │  │
│  │    - test_param_temperature()                            │  │
│  │    - test_model_variants()                               │  │
│  └─────────────────────┬────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────┘
                         │ 调用
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Provider 适配层 (providers/)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OpenAIAdapter (组合模式)                                │  │
│  │    - config: ProviderConfig                              │  │
│  │    - http_client: HTTPClient  ◄─ 持有HTTP客户端实例      │  │
│  │    + prepare_headers() → {"Authorization": "Bearer xxx"} │  │
│  │    + request(endpoint, params) → 委托给http_client       │  │
│  └─────────────────────┬────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────┘
                         │ 委托
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HTTP 客户端层 (client/)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  HTTPClient                                              │  │
│  │    - logger: RequestLogger                               │  │
│  │    + request(method, url, headers, json)                 │  │
│  │    + stream(method, url, headers, json)                  │  │
│  │    + request_async()                                     │  │
│  │    + stream_async()                                      │  │
│  └─────────────────────┬────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────┘
                         │ 发起请求
                         ▼
                 ┌───────────────┐
                 │   httpx 库    │
                 │   (底层HTTP)  │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │  LLM API      │
                 │  (OpenAI等)   │
                 └───────┬───────┘
                         │ 返回响应
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    验证层 (validation/)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ResponseValidator.validate()                            │  │
│  │    输入: response_body (dict)                            │  │
│  │    Schema: ChatCompletionResponse (Pydantic)             │  │
│  │    输出: (is_valid, error_msg, missing_fields)           │  │
│  └─────────────────────┬────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────┘
                         │ 验证结果
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    报告层 (reporting/)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ReportCollector                                         │  │
│  │    - tested_params: set                                  │  │
│  │    - unsupported_params: list                            │  │
│  │    - errors: list                                        │  │
│  │    + record_test(test_name, params, status, error)       │  │
│  │    + add_unsupported_param(name, value, reason)          │  │
│  │    + finalize() → 生成JSON报告                           │  │
│  └─────────────────────┬────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │  JSON 报告文件   │
               │  reports/*.json  │
               └──────────────────┘
```

## 组件职责

### 1. 测试层 (Tests)
**职责**：定义测试用例和参数
```python
- 显式定义 ENDPOINT 和 BASE_PARAMS
- 使用控制变量法测试参数
- 调用 Provider Adapter 发起请求
- 调用 ResponseValidator 验证响应
- 调用 ReportCollector 记录结果
```

### 2. Provider 适配层 (Providers)
**职责**：适配各厂商 API
```python
- 准备厂商特定的请求头（认证）
- 拼接完整 URL (base_url + endpoint)
- 委托给 HTTPClient 执行请求
- 不做业务逻辑，只做适配
```

### 3. HTTP 客户端层 (Client)
**职责**：处理 HTTP 通信
```python
- 发起同步/异步、流式/非流式请求
- 记录请求/响应日志（带 request_id）
- 统一错误处理
- 不知道 Provider 的存在
```

### 4. 验证层 (Validation)
**职责**：验证响应格式
```python
- 使用 Pydantic 模型验证响应
- 提取缺失字段
- 返回字段级别的错误信息
```

### 5. 报告层 (Reporting)
**职责**：汇总测试结果
```python
- 收集所有测试的参数、状态、错误
- 跟踪不支持的参数和缺失字段
- 生成 JSON 格式报告
```

## 关键设计模式

### 1. 组合模式 (Composition over Inheritance)
```python
# Provider 持有 HTTPClient，而非继承
class OpenAIAdapter(ProviderAdapter):
    def __init__(self, config, http_client):
        self.http_client = http_client  # 组合
```

**优势**：
- 解耦：HTTPClient 可独立演化
- 灵活：可动态替换 HTTPClient 实现
- 清晰：职责分明，不会混淆

### 2. 依赖注入 (Dependency Injection)
```python
# 通过 Pytest Fixture 注入依赖
@pytest.fixture(scope="session")
def openai_client(config):
    provider_config = config.get_provider_config("openai")
    logger = RequestLogger(config.log)
    http_client = HTTPClient(logger)
    return OpenAIAdapter(provider_config, http_client)
```

**优势**：
- 可测试性：可注入 Mock 对象
- 配置集中：依赖关系清晰
- 灵活性：易于替换实现

### 3. 策略模式 (Strategy Pattern)
```python
# 不同的 Provider 使用不同的认证策略
class OpenAIAdapter:
    def prepare_headers(self):
        return {"Authorization": f"Bearer {self.config.api_key}"}

class AnthropicAdapter:
    def prepare_headers(self):
        return {"x-api-key": self.config.api_key}
```

**优势**：
- 扩展性：添加新 Provider 无需修改现有代码
- 封装：认证逻辑封装在各自的 Adapter 中

## 数据流示例

### 完整的测试执行流程

```
1. 测试开始
   ├─ test_baseline() 执行
   │  └─ params = {"model": "gpt-3.5-turbo", "messages": [...]}
   │
2. 调用 Provider Adapter
   ├─ openai_client.request(endpoint="/v1/chat/completions", params)
   │  ├─ url = base_url + endpoint
   │  │     = "https://api.openai.com" + "/v1/chat/completions"
   │  └─ headers = prepare_headers()
   │           = {"Authorization": "Bearer sk-xxx", "Content-Type": "application/json"}
   │
3. 委托给 HTTP Client
   ├─ http_client.request(method="POST", url, headers, json=params)
   │  ├─ request_id = generate_request_id() = "abc-123"
   │  ├─ logger.log_request(request_id, method, url, headers, params)
   │  ├─ response = httpx.post(url, headers, json=params)
   │  └─ logger.log_response(request_id, status_code, headers, body)
   │
4. 返回响应
   ├─ (status_code, headers, response_body)
   │  └─ (200, {...}, {"id": "chatcmpl-xxx", "choices": [...]})
   │
5. 验证响应
   ├─ ResponseValidator.validate(response_body, ChatCompletionResponse)
   │  ├─ 尝试解析为 Pydantic 模型
   │  ├─ 检查所有必需字段
   │  └─ 返回: (is_valid=True, error_msg=None, missing_fields=[])
   │
6. 记录测试结果
   ├─ report_collector.record_test(
   │      test_name="test_baseline",
   │      params=params,
   │      status_code=200,
   │      response_body=response_body,
   │      error=None
   │  )
   │  ├─ total_tests += 1
   │  ├─ passed_tests += 1
   │  └─ tested_params.add("model", "messages")
   │
7. 测试完成
   └─ report_collector.finalize()
      ├─ 构建 JSON 报告
      └─ 写入文件: reports/openai_v1_chat_completions_20260127.json
```

## 扩展点

### 添加新 Endpoint 的扩展点

1. **Validation Schemas** ([llm_spec/validation/schemas/](llm_spec/validation/schemas/))
   - 添加新的 Pydantic 模型

2. **Test Files** ([tests/providers/](tests/providers/))
   - 创建新的测试类
   - 定义 ENDPOINT 和 BASE_PARAMS
   - 复用现有的 Provider Adapter

### 添加新 Provider 的扩展点

1. **Provider Adapter** ([llm_spec/providers/](llm_spec/providers/))
   - 继承 `ProviderAdapter`
   - 实现 `prepare_headers()`

2. **Config File** ([llm-spec.toml](llm-spec.toml))
   - 添加新的 `[provider_name]` 配置段

3. **Pytest Fixture** ([tests/conftest.py](tests/conftest.py))
   - 创建新的 `{provider}_client` fixture

## 配置流

```
llm-spec.toml
      │
      ├─ [log] ──────────► LogConfig
      │                        │
      │                        └──► RequestLogger
      │
      ├─ [report] ───────► ReportConfig
      │                        │
      │                        └──► ReportCollector
      │
      └─ [openai] ───────► ProviderConfig
                               │
                               └──► OpenAIAdapter
                                       │
                                       └─ http_client: HTTPClient
                                             │
                                             └─ logger: RequestLogger
```

所有配置从单一来源（`llm-spec.toml`）加载，通过 Pydantic 验证，然后注入到各个组件中。
