# LLM Spec

用于验证多类 SDK/API 格式、参数和特性支持情况的测试工具：

- `openai`
- `@anthropic-ai/sdk`
- `@google/genai`
- xAI OpenAI-compatible API

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
- `POST /api/run/stream`
- `POST /api/jobs`
- `GET /api/jobs/:id`
- `GET /api/history`
- `GET /api/history/:id`
- `POST /api/history`
- `DELETE /api/history/:id`

后端默认允许跨域访问。可通过 `LLM_SPEC_CORS_ORIGIN` 收紧来源。

### Backend HTTP API

可以直接通过 HTTP API 向 backend 发送测试服务请求，参数通过 JSON request body 传入。`POST /api/run` 会同步等待测试完成并返回 `RunSummary`；`POST /api/run/stream` 返回 NDJSON 进度流；`POST /api/jobs` 创建异步任务并返回 job id，适合长时间测试或外部系统轮询。

单目标同步运行示例：

```bash
curl -sS http://localhost:8788/api/run \
  -H 'Content-Type: application/json' \
  -d '{
    "kind": "standard",
    "apiType": "openai.chat",
    "apiBaseUrl": "https://api.openai.com/v1",
    "apiKey": "sk-...",
    "model": "gpt-4o-mini",
    "targetCases": "basic,stream",
    "timeoutMs": 60000,
    "concurrency": 1,
    "persistResult": true
  }'
```

多目标矩阵同步运行示例：

```bash
curl -sS http://localhost:8788/api/run \
  -H 'Content-Type: application/json' \
  -d '{
    "apiKey": "sk-...",
    "apiBaseUrl": "https://api.openai.com/v1",
    "timeoutMs": 600000,
    "concurrency": 1,
    "customHeaders": {
      "X-Debug-Channel-ID": "13"
    },
    "targets": [
      {
        "id": "chat-smoke",
        "kind": "standard",
        "apiType": "openai.chat",
        "model": "gpt-4o-mini",
        "targetCases": "basic,stream"
      },
      {
        "id": "responses-smoke",
        "kind": "standard",
        "apiType": "openai.responses",
        "model": "gpt-4o-mini",
        "targetCases": "responses_basic,responses_basic_stream"
      }
    ]
  }'
```

异步任务示例：

```bash
JOB_ID=$(curl -sS http://localhost:8788/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "apiKey": "sk-...",
    "apiBaseUrl": "https://api.openai.com/v1",
    "targets": [
      {
        "kind": "standard",
        "apiType": "openai.chat",
        "model": "gpt-4o-mini",
        "targetCases": "basic"
      }
    ]
  }' | node -e 'process.stdin.on("data", d => console.log(JSON.parse(d).id))')

curl -sS "http://localhost:8788/api/jobs/${JOB_ID}"
```

流式运行示例：

```bash
curl -N http://localhost:8788/api/run/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "kind": "standard",
    "apiType": "anthropic.messages",
    "apiKey": "sk-ant-...",
    "model": "claude-3-5-haiku-latest",
    "targetCases": "basic,stream"
  }'
```

请求体字段说明：

- `kind`：单目标请求使用，取值 `standard` 或 `agent`；未设置时默认为 `standard`。
- `apiType`：普通 API 测试类型，支持 `openai.chat`、`openai.responses`、`anthropic.messages`、`gemini.generateContent`。
- `agentProvider`：Agent 测试类型，支持 `claude-agent`、`codex`。
- `targets`：多目标矩阵。每项支持 `id`、`kind`、`enabled`、`apiType`、`agentProvider`、`model`、`targetCases`，并可覆盖顶层连接参数。
- `apiKey` / `apiBaseUrl` / `model`：目标服务连接和模型参数；未传时回退到 backend 进程环境变量。
- `customHeaders`：自定义请求头，支持 JSON 对象或 JSON 字符串。
- `apiVersion`：Gemini 原生 SDK 使用。
- `targetCases`：只运行匹配的用例，语法与 `TARGET_CASES` 一致；不传或传空字符串时默认运行当前模型推荐用例。
- 默认未指定 `targetCases` 时，会根据本行选择的测试模型自动筛掉已知不适配的参数用例（例如 reasoning-only、legacy `max_tokens`、Gemini image/audio 模型用例等）。显式传入 `targetCases` 时以人工选择为准。
- 报告中的 `testModel` 表示该用例实际选择的测试模型；部分用例会使用专用模型槽位，例如 `OPENAI_REASONING_MODEL`、`OPENAI_AUDIO_MODEL`、`GEMINI_IMAGE_MODEL` 或 Anthropic 的 Opus/Haiku/Fast Mode 模型。
- `timeoutMs` / `concurrency` / `failFast`：运行控制参数。
- `pluginPaths`：可选插件模块路径数组，或逗号分隔字符串。路径相对 backend 进程工作目录解析。
- `billingAudit`：可选 R9S 计费审计配置，格式为 `{ "enabled": true, "managerBaseUrl": "https://portal-api.r9s.ai", "managerKey": "...", "tokenId": "tk_xxx" }`。开启后会在所有用例结束后调用 R9S Manager API usage 接口并把本地 usage 与平台账单写入报告。
- `workingDirectory` / `skipGitRepoCheck` / `testImagePath`：Agent 测试参数。
- `persistResult`：是否写入 backend history，默认 `true`。
- `runSnapshot`：可选运行快照，会原样写入报告。

`targets[]` 中的 `apiKey`、`apiBaseUrl`、`customHeaders`、`apiVersion`、`timeoutMs`、`concurrency`、`workingDirectory`、`skipGitRepoCheck`、`testImagePath`、`failFast` 会覆盖顶层同名字段，便于一次 API 请求中混合不同目标。

### 插件机制

Node runner 支持通过插件监听测试生命周期。CLI 使用 `LLM_SPEC_PLUGINS=./plugins/a.mjs,./plugins/b.mjs` 配置；backend API 可以在请求体中传 `pluginPaths`。

插件模块可以默认导出插件对象、插件数组或返回插件对象的工厂函数。支持的 hook：

- `beforeCase(context)`：在测试用例发出真实请求前执行；如果一个用例发出多次请求，会按请求各执行一次。`context` 包含 `id`、`name`、`description`、`provider`、`testId`、`requestId`、`requestIndex` 和 `request`。`request` 包含 `url`、`method`、`headers`、`body`。hook 可以返回 `{ request: { headers, body, url, method } }` 或直接返回这些字段来修改请求；`headers` 会合并，值为 `null` / `undefined` 表示删除该 header。
- `afterCase(context)`：在用例结果生成后执行。`context` 包含用例名称、描述、`result`、首个 `request` / `response`，以及完整 `exchanges` 请求响应数组。
- `afterRun(context)`：所有用例结束后执行，`context.summary` 是完整 `RunSummary` 报告，包含各用例的请求和响应 trace。

示例：

```js
// plugins/add-debug-header.mjs
export default {
  name: 'add-debug-header',
  beforeCase({ request, name }) {
    return {
      request: {
        headers: {
          'x-llm-spec-case': name,
          ...request.headers,
        },
      },
    };
  },
  afterCase({ name, response }) {
    console.log(`[plugin] ${name}: status=${response?.status ?? 'none'}`);
  },
  afterRun({ summary }) {
    console.log(`[plugin] finished providers=${summary.providers.length}`);
  },
};
```

### R9S 计费审计

内置 R9S 计费审计插件基于 `afterRun` 生命周期执行。它会从本地 HTTP trace 的响应体中提取 OpenAI / Anthropic / Gemini 风格的 `usage`，再按运行报告的 `startedAt` / `finishedAt` 调用 R9S Manager API `GET /api/v1/portal/management/usage`，并按模型对比本地 input/output/cached token 与 R9S billing 记录。报告中的 `billingAudit` 字段会包含查询窗口、平台记录、按模型差异、告警和错误信息；前端 Summary 区域也会展示差异表。

CLI 可通过环境变量开启：

```bash
R9S_BILLING_AUDIT=true \
R9S_MANAGER_BASE_URL=https://portal-api.r9s.ai \
R9S_MANAGER_KEY=manager-key \
R9S_TOKEN_ID=tk_xxx \
TEST_API_KEY=target-api-key \
pnpm test:sdk
```

Backend API 可直接传入：

```json
{
  "kind": "standard",
  "apiType": "openai.chat",
  "apiKey": "target-api-key",
  "apiBaseUrl": "https://your-r9s-gateway/v1",
  "model": "gpt-4o-mini",
  "billingAudit": {
    "enabled": true,
    "managerBaseUrl": "https://portal-api.r9s.ai",
    "managerKey": "manager-key",
    "tokenId": "tk_xxx"
  }
}
```

前端在 Site Profile 中勾选 `R9S Billing Audit` 后会要求配置 Manager Base URL 和 Manager Key，并自动使用 backend 执行测试，避免在浏览器端暴露 Manager Key。`token_id` 过滤只会在显式配置 `billingAudit.tokenId` / `R9S_TOKEN_ID` 时启用；如果没有配置 token id，插件会查询整个时间窗口并在报告里提示未按 token_id 过滤。R9S 账单字段缺失或无法解析时会显示 `not fetched` 并给出 warning，不会用 0 代替未知值。

### 启动前端

```bash
pnpm dev:reporter
```

前端开发模式默认连接 `http://localhost:8788`；生产构建默认连接当前页面同源后端。也可以在构建/运行前设置：

```bash
VITE_LLM_SPEC_BACKEND_URL=http://your-backend:8788 pnpm --filter @llm-spec/reporter build
```

### 打包为单个 Node 服务

如果希望前端和后端由同一个 Node 服务提供：

```bash
pnpm build:service
pnpm start:service
```

`build:service` 会构建 reporter 前端、构建 llm-spec 后端，并把前端产物复制到 `packages/llm-spec/dist/public/`。启动后，`/api/*` 由后端接口处理，其他路径由同一个服务返回前端静态文件。

可用 `LLM_SPEC_STATIC_DIR` 覆盖静态文件目录。

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
TARGET_PROVIDERS=xai pnpm test:sdk
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
- `LLM_SPEC_PLUGINS`（逗号分隔的 Node 插件模块路径）
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

### xAI

- `XAI_API_KEY`
- `XAI_API_BASE_URL`（默认 `https://api.x.ai/v1`）
- `XAI_MODEL`（默认 `grok-beta`，复用 OpenAI-compatible `chat.completions` 用例）
- `XAI_TIMEOUT_MS`

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
