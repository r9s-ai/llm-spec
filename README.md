# LLM Spec

用于验证三类 SDK API 格式/参数/特性支持情况的测试工具：

- `openai`
- `@anthropic-ai/sdk`
- `@google/genai`

其中 OpenAI provider 会同时覆盖：
- `chat.completions.create`
- `responses.create`

支持统一配置 `API_BASE_URL` / `API_KEY`，也支持各 provider 的独立配置。

## 快速开始

1. 安装依赖

```bash
pnpm install
```

2. 复制并填写环境变量

```bash
cp .env.example .env
```

3. 构建并运行

```bash
pnpm build
node dist/index.js
```

## 运行方式

- 运行全部 provider（默认）：`openai,anthropic,gemini`
- 指定 provider：

```bash
TARGET_PROVIDERS=openai node dist/index.js
TARGET_PROVIDERS=anthropic,gemini node dist/index.js
```

- 只运行指定测试用例（逗号分隔）：

```bash
TARGET_CASES=basic,stream node dist/index.js
TARGET_CASES=claude-agent:basic_prompt,openai:responses_* node dist/index.js
```

说明：
- 支持 `caseId`、`provider:caseId`
- 支持通配符：`*`（任意长度）和 `?`（单字符）
- 兼容别名环境变量：`TEST_CASES`、`CASE_IDS`

- 失败即停：

```bash
FAIL_FAST=true node dist/index.js
```

- 输出报告（JSON + HTML + 纯文本）：

```bash
REPORT_FILE=./report.json node dist/index.js
```

会生成：

- `./report.json`
- `./report.html`
- `./report.txt`

## 配置说明

### 通用配置

- `API_KEY`
- `API_BASE_URL`
- `TARGET_PROVIDERS`
- `TARGET_CASES`（可选，只运行匹配的用例）
- `FAIL_FAST`
- `REPORT_FILE`
- `SDK_TIMEOUT_MS`

### OpenAI

- `OPENAI_API_KEY`
- `OPENAI_API_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_AUDIO_MODEL`（启用音频模态测试）
- `OPENAI_REASONING_MODEL`（启用 Responses API 的 reasoning 参数测试）
- `OPENAI_RESPONSES_PROMPT_ID`（启用 Responses API 的 prompt 参数测试）

### Anthropic

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_API_BASE_URL`
- `ANTHROPIC_MODEL`
- `ANTHROPIC_CONTAINER`（启用 container 参数测试）
- `ANTHROPIC_INFERENCE_GEO`（启用 inference_geo 参数测试）

### Claude Agent

- `CLAUDE_AGENT_API_KEY`
- `CLAUDE_AGENT_API_BASE_URL`
- `CLAUDE_AGENT_MODEL`
- `CLAUDE_AGENT_CUSTOM_HEADERS`（JSON 对象字符串，例如 `{"X-Debug-Channel-ID":"13"}`）

说明：`CLAUDE_AGENT_CUSTOM_HEADERS` 会注入到 Agent 请求头；同时兼容 `ANTHROPIC_CUSTOM_HEADERS`。

### Gemini

- `GEMINI_API_KEY`
- `GEMINI_API_BASE_URL`
- `GEMINI_API_VERSION`
- `GEMINI_MODEL`
- `GEMINI_CACHED_CONTENT`（启用 cachedContent 测试）
- `GEMINI_AUDIO_MODEL`（启用音频相关参数测试）
- `GEMINI_IMAGE_MODEL`（启用 imageConfig 测试）
- `GEMINI_ENABLE_VERTEX_ONLY_CASES`（启用 routing/modelSelection 等 Vertex 偏向特性）
- `GEMINI_MODEL_ARMOR_PROMPT_TEMPLATE`
- `GEMINI_MODEL_ARMOR_RESPONSE_TEMPLATE`

## 输出结果

脚本会输出：

- 每个测试用例的 `PASS / FAIL / SKIP`
- 每个 provider 的参数覆盖统计（covered / untested，`covered` 仅统计 `PASS` 用例）
- 最终汇总（总通过/失败/跳过）

当设置 `REPORT_FILE` 时，默认会同时生成三种格式：

- `JSON`：机器可读，便于后处理
- `HTML`：可视化查看，适合人工快速浏览
- `TXT`：纯文本，适合终端、日志系统和 CI artifact 预览

当存在失败用例时，进程退出码为 `1`。
