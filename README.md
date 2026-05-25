# LLM Spec

用于验证三类 SDK API 格式/参数/特性支持情况的测试工具：

- `openai`
- `@anthropic-ai/sdk`
- `@google/genai`

其中 OpenAI provider 会同时覆盖：
- `chat.completions.create`
- `responses.create`

支持统一配置 `API_BASE_URL` / `API_KEY`，也支持各 provider 的独立配置。

现在也支持单目标模式：直接指定 `apiType + apiBaseUrl + apiKey + model`，只运行这个 API surface 对应的测试用例。

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
pnpm test:sdk
```

## 平台模式

项目现在可以作为自部署平台运行，分为两个服务：

- 前端：`packages/reporter/`，负责配置测试、浏览报告、普通 API 的浏览器直连测试。
- 后端：`packages/llm-spec/dist/server.js`，负责代理/执行不适合浏览器直连的普通 API 测试，以及所有 Agent 测试。

### 启动后端

```bash
pnpm build
LLM_SPEC_BACKEND_PORT=8788 pnpm start:server
```

后端接口：

- `GET /api/health`
- `POST /api/run`

后端默认允许跨域访问。可通过 `LLM_SPEC_CORS_ORIGIN` 收紧来源。

### 启动前端

```bash
pnpm dev:reporter
```

前端默认连接 `http://localhost:8788`，也可以在构建/运行前设置：

```bash
VITE_LLM_SPEC_BACKEND_URL=http://your-backend:8788 pnpm --filter @llm-spec/reporter build
```

### 执行策略

- 普通 API 测试默认在浏览器端运行，直接使用 `fetch` 请求目标 API，并生成与 CLI 一致的报告结构。
- 普通 API 测试可以切换为后端运行，用于目标 API 不支持 CORS、需要私网访问或需要集中保管密钥的场景。
- `claude-agent` / `codex` 等 Agent 测试只能通过后端运行；前端负责填写 API key、base URL、工作目录、用例过滤等配置。

### 站点 Profile 与测试矩阵

平台前端将配置拆成两层：

- 站点 Profile：保存低频变化的连接信息，例如 API key、base URL、custom headers、backend URL、Agent 工作目录等。
- Test Matrix：保存本次运行要测的目标行，每一行可以独立选择 API/Agent、model、case filter，并可在执行前快速增删改。

执行时前端会按 Test Matrix 逐行调用现有运行接口并合并报告。报告中会带上 `runSnapshot`，记录本次实际执行的站点、模型、用例过滤和执行方式。

## 运行方式

### 单目标模式

设置 `TEST_API_TYPE` 后，会忽略 `TARGET_PROVIDERS`，只执行一个 API surface：

```bash
TEST_API_TYPE=openai.chat \
TEST_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ \
TEST_API_KEY=your_gemini_key_here \
TEST_MODEL=gemini-2.5-flash \
pnpm test:sdk
```

支持的 `TEST_API_TYPE`：

- `openai.chat`
- `openai.responses`
- `anthropic.messages`
- `gemini.generateContent`

示例：

```bash
TEST_API_TYPE=openai.responses \
TEST_API_KEY=your_openai_key_here \
TEST_API_BASE_URL=https://api.openai.com/v1 \
TEST_MODEL=gpt-4o-mini \
TARGET_CASES=openai.responses:responses_* \
pnpm test:sdk
```

```bash
TEST_API_TYPE=anthropic.messages \
TEST_API_KEY=your_anthropic_key_here \
TEST_MODEL=claude-3-5-haiku-latest \
pnpm test:sdk
```

```bash
TEST_API_TYPE=gemini.generateContent \
TEST_API_KEY=your_gemini_key_here \
TEST_MODEL=gemini-2.5-flash \
pnpm test:sdk
```

- 运行全部 provider（默认）：`openai,anthropic,gemini`
- 指定 provider：

```bash
TARGET_PROVIDERS=openai pnpm test:sdk
TARGET_PROVIDERS=anthropic,gemini pnpm test:sdk
TARGET_PROVIDERS=claude-agent pnpm test:sdk
```

- 只运行指定测试用例（逗号分隔）：

```bash
TARGET_CASES=basic,stream pnpm test:sdk
TARGET_CASES=claude-agent:basic_prompt,openai:responses_* pnpm test:sdk
```

说明：
- 支持 `caseId`、`provider:caseId`
- 也支持 `apiType:caseId`，例如 `openai.chat:basic`、`openai.responses:responses_*`、`anthropic.messages:*`
- 支持通配符：`*`（任意长度）和 `?`（单字符）
- 兼容别名环境变量：`TEST_CASES`、`CASE_IDS`

- 失败即停：

```bash
FAIL_FAST=true pnpm test:sdk
```

- 输出报告（JSON + HTML + 纯文本）：

```bash
REPORT_FILE=./report.json pnpm test:sdk
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
- `CUSTOM_HEADERS`（JSON 对象字符串，作为 OpenAI SDK / Claude Agent 的统一自定义请求头配置；兼容旧的 `OPENAI_CUSTOM_HEADERS` / `CLAUDE_AGENT_CUSTOM_HEADERS`）

### 单目标配置

- `TEST_API_TYPE`
- `TEST_API_KEY`
- `TEST_API_BASE_URL`
- `TEST_MODEL`
- `TEST_TIMEOUT_MS`
- `TEST_CUSTOM_HEADERS`（JSON 对象字符串，目前主要用于 OpenAI SDK）
- `TEST_API_VERSION`（用于 Gemini 原生 SDK）

### OpenAI

- `OPENAI_API_KEY`
- `OPENAI_API_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_AUDIO_MODEL`（启用音频模态测试）
- `OPENAI_REASONING_MODEL`（启用 Responses API 的 reasoning 参数测试）
- `OPENAI_RESPONSES_PROMPT_ID`（启用 Responses API 的 prompt 参数测试）
- `OPENAI_INCLUDE_MODEL_CATALOG_CASES`（启用 GPT/OpenAI 模型目录 smoke 测试；设置 `TARGET_CASES` 时也会自动加载这些可筛选用例）

### Anthropic

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_API_BASE_URL`
- `ANTHROPIC_MODEL`
- `ANTHROPIC_OPUS_MODEL` / `ANTHROPIC_HAIKU_MODEL` / `ANTHROPIC_FAST_MODE_MODEL`（可选；未设置时相关用例使用 `ANTHROPIC_MODEL`）
- `ANTHROPIC_INFERENCE_GEO`（启用 inference_geo 参数测试）
- `ANTHROPIC_INCLUDE_MODEL_CATALOG_CASES`（启用 Claude Messages 模型目录 smoke 测试；设置 `TARGET_CASES` 时也会自动加载这些可筛选用例）

### Claude Agent

- `CLAUDE_AGENT_API_KEY`
- `CLAUDE_AGENT_API_BASE_URL`
- `CLAUDE_AGENT_MODEL`
- `CLAUDE_AGENT_OPUS_MODEL` / `CLAUDE_AGENT_SONNET_MODEL` / `CLAUDE_AGENT_HAIKU_MODEL`（可选；只在需要按模型槽位覆盖特定 Agent 用例时使用，未设置时回退到 `CLAUDE_AGENT_MODEL`）

说明：使用 `CUSTOM_HEADERS` 注入 Agent 请求头，例如 `{"X-Debug-Channel-ID":"13"}`；同时兼容旧的 `CLAUDE_AGENT_CUSTOM_HEADERS` 和 `ANTHROPIC_CUSTOM_HEADERS`。

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
- `GEMINI_INCLUDE_MODEL_CATALOG_CASES`（启用 Gemini 当前仍可服务的 generateContent 模型 smoke 测试；设置 `TARGET_CASES` 时也会自动加载这些可筛选用例）

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

## 代码结构

项目现在使用 pnpm workspace 组织：

- `packages/llm-spec/`
  - Node CLI、backend server、SDK/Agent 测试运行器
- `packages/reporter/`
  - Vite + React 报告和平台前端
- `docs/`
  - API reference 文档快照

测试执行代码按两部分组织：

- `packages/llm-spec/src/api-sdk-tester/environment/`
  - 运行时环境解析
  - `.env` 加载和 provider 配置
  - `TARGET_CASES` 过滤
  - HTTP 请求日志和 provider 上下文
- `packages/llm-spec/src/api-sdk-tester/cases/`
  - 各 provider/agent 的测试用例定义
  - `TestCase` 类型和用例执行器
  - provider 级别的覆盖率统计和执行摘要
