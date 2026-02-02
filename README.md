# llm-spec

一个基于 **pytest** 的 LLM API 格式/参数兼容性检查工具：通过“控制变量法”逐项测试请求参数，并用 **Pydantic schema** 校验响应结构，最终生成 **JSON + Markdown + HTML** 报告（支持单 endpoint 报告与按厂商聚合报告）。

## 特性

- **参数支持情况探测**：在基线请求成功的前提下，逐个引入参数/参数值，定位“不支持”的精确原因（通常是 HTTP 4xx/5xx 或响应校验失败）。
- **响应格式验证**：为不同厂商/路由提供响应 schema，输出缺失字段列表与字段级错误定位。
- **报告输出**：
  - 单 endpoint：`report.json` / `parameters.md` / `report.html`
  - 多 endpoint（同一厂商目录）：自动生成 `*_aggregated_*` 聚合报告（JSON/MD/HTML）
- **结构化请求日志**：可选记录请求/响应（支持截断，避免巨大 body）。

## 当前支持的厂商与路由

项目内置了以下 provider 适配与测试用例（配置文件位于 `tests/testcases/`）：

### OpenAI

Provider：`openai`（默认 `base_url=https://api.openai.com`）

支持测试路由：
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`
- `POST /v1/images/generations`
- `POST /v1/images/edits`
- `POST /v1/audio/speech`（二进制音频返回）
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/translations`

测试默认模型/基线（来自测试用例中的 `BASE_PARAMS` 或 endpoint 路径本身）：
- Chat Completions：`gpt-4o-mini`
- Responses：`gpt-4o-mini`
- Embeddings：`text-embedding-3-small`
- Images Generations：`dall-e-3`（另有 GPT image 基线 `gpt-image-1.5`）
- Images Edits：`gpt-image-1.5`
- Audio Speech：`gpt-4o-mini-tts`
- Audio Transcriptions：`whisper-1`（另在模型变体测试中出现 `gpt-4o-mini-transcribe`）
- Audio Translations：`whisper-1`

### Anthropic

Provider：`anthropic`（默认 `base_url=https://api.anthropic.com`）

支持测试路由：
- `POST /v1/messages`

测试默认模型：
- Messages：`claude-haiku-4.5`

### Google Gemini

Provider：`gemini`（默认 `base_url=https://generativelanguage.googleapis.com`）

支持测试路由：
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent`（流式）
- `POST /v1beta/models/{model}:batchGenerateContent`
- `POST /v1beta/models/{model}:embedContent`
- `POST /v1beta/models/{model}:countTokens`

测试默认模型/基线（来自 endpoint 路径本身；Gemini 的 model 通常在 URL 中）：
- Generate：`gemini-3-flash-preview`（`/v1beta/models/gemini-3-flash-preview:generateContent`）
- StreamGenerate：`gemini-3-flash-preview`（`...:streamGenerateContent`）
- BatchGenerate：`gemini-3-flash-preview`（`...:batchGenerateContent`）
- Embed：`text-embedding-005`（`/v1beta/models/text-embedding-005:embedContent`）
- CountTokens：`gemini-2.5-flash`（`/v1beta/models/gemini-2.5-flash:countTokens`）

### xAI（OpenAI 兼容）

Provider：`xai`（默认 `base_url=https://api.x.ai/v1`）

支持测试路由：
- `POST /v1/chat/completions`

测试默认模型：
- Chat Completions：`grok-beta`

## 使用 uv 创建环境并安装依赖

项目是标准 `pyproject.toml`，推荐用 **uv** 管理虚拟环境与依赖。

```bash
# 1) 创建并使用 venv（Python 3.11+）
uv venv -p 3.11

# 2) 安装（包含测试依赖）
uv sync --extra dev

# 3) 进入环境（任选其一）
source .venv/bin/activate
# 或不激活，直接用 uv 运行：
# uv run pytest ...
```

## 配置

复制示例配置并填写 key：

```bash
cp llm-spec.example.toml llm-spec.toml
```

`llm-spec.toml` 关键字段：

- `[report].output_dir`：报告输出目录（默认 `./reports`）
- `[log]`：日志开关、级别、是否记录 request/response body
- `[openai] / [anthropic] / [gemini] / [xai]`：各厂商 `api_key` / `base_url` / `timeout`

示例（节选）：

```toml
[report]
output_dir = "./reports"

[openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0
```

## 运行方式

项目现在主要通过 **配置驱动** 的方式运行测试。所有测试用例定义在 `tests/testcases/` 目录下的 JSON5 文件中。

### 运行全部配置驱动测试

```bash
uv run pytest tests/test_from_config.py -v
```

### 运行特定厂商的测试

```bash
# 运行 OpenAI 的所有配置测试
uv run pytest tests/test_from_config.py -k "openai" -v

# 运行 Gemini 的所有配置测试
uv run pytest tests/test_from_config.py -k "gemini" -v
```

### 运行特定路由的测试

```bash
# 运行 OpenAI Chat Completions
uv run pytest tests/test_from_config.py -k "openai/chat_completions" -v
```

### 调试记录

如果你想查看具体的请求响应日志，可以结合 `--log-cli-level=INFO`：

```bash
uv run pytest tests/test_from_config.py -k "openai/chat_completions" --log-cli-level=INFO
```

> 说明：pytest session 开始时会生成本次运行的 `run_id`（时间戳），所有报告会写到 `reports/<run_id>/...`，避免和历史报告混在一起。

## 查看报告

### 1) 定位本次 run 的目录

```bash
ls -lt reports | head
```

你会看到类似：

```
reports/20260130_141530/
  openai_v1_chat_completions_20260130_141531/
    report.json
    parameters.md
    report.html
  openai_aggregated_20260130_141620/
    report.json
    report.md
    report.html
```

### 2) 打开 HTML 报告

- 单 endpoint：`reports/<run_id>/<provider>_<endpoint>_<timestamp>/report.html`
- 聚合报告：`reports/<run_id>/<provider>_aggregated_<timestamp>/report.html`

本地直接用浏览器打开即可。

### 3) 查看 JSON/Markdown

```bash
cat reports/<run_id>/openai_v1_responses_*/report.json
cat reports/<run_id>/openai_v1_responses_*/parameters.md
```

## 文档 (Documentation)

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: 项目分层架构、组件职责及设计原则。
- **[DATAFLOW.md](docs/DATAFLOW.md)**: 从测试配置解析到 HTTP 请求与报告生成的全生命周期数据流。
- **[CONFIG_DRIVEN_TESTING.md](docs/CONFIG_DRIVEN_TESTING.md)**: **核心指南**。详细讲解配置驱动的设计方案、JSON5 语法规范，以及如何添加新的测试套件。

## License

MIT
