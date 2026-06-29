# LLM Spec

A test tool for validating SDK/API formats, parameters, and feature support across multiple providers:

- `openai`
- `@anthropic-ai/sdk`
- `@google/genai`
- xAI OpenAI-compatible API

The OpenAI provider covers both:

- `chat.completions.create`
- `responses.create`

It supports unified `API_BASE_URL` / `API_KEY` configuration, as well as provider-specific configuration.

It also supports single-target mode: specify `apiType + apiBaseUrl + apiKey + model` directly, and only the test cases for that API surface will run.

## Quick Start

1. Install dependencies

```bash
pnpm install
```

2. Copy and fill in environment variables

```bash
cp .env.example .env
```

3. Build and run

```bash
pnpm build
pnpm test:sdk
```

## Platform Mode

The project can now run as a self-hosted platform with two services:

- Frontend: `packages/reporter/`, used to configure tests, browse reports, and run browser-direct tests for standard APIs.
- Backend: `packages/llm-spec/dist/server.js`, used to proxy/execute standard API tests that are not suitable for browser-direct execution, and all Agent tests.

### Start the Backend

```bash
pnpm build
LLM_SPEC_BACKEND_PORT=8788 pnpm start:server
```

Backend endpoints:

- `GET /api/health`
- `POST /api/run`
- `POST /api/run/stream`
- `POST /api/jobs`
- `GET /api/jobs/:id`
- `GET /api/history`
- `GET /api/history/:id`
- `POST /api/history`
- `DELETE /api/history/:id`

The backend allows cross-origin access by default. Use `LLM_SPEC_CORS_ORIGIN` to restrict allowed origins.

### Backend HTTP API

You can send test run requests directly to the backend through the HTTP API. Parameters are passed in the JSON request body. `POST /api/run` waits synchronously for the test run to finish and returns a `RunSummary`; `POST /api/run/stream` returns an NDJSON progress stream; `POST /api/jobs` creates an asynchronous job and returns a job ID, which is suitable for long-running tests or polling from external systems.

Single-target synchronous run example:

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

Multi-target matrix synchronous run example:

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

Asynchronous job example:

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

Streaming run example:

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

Request body fields:

- `kind`: Used for single-target requests. Valid values are `standard` or `agent`; defaults to `standard` when omitted.
- `apiType`: Standard API test type. Supported values are `openai.chat`, `openai.responses`, `anthropic.messages`, and `gemini.generateContent`.
- `agentProvider`: Agent test type. Supported values are `claude-agent` and `codex`.
- `targets`: Multi-target matrix. Each item supports `id`, `kind`, `enabled`, `apiType`, `agentProvider`, `model`, and `targetCases`, and can override top-level connection parameters.
- `apiKey` / `apiBaseUrl` / `model`: Target service connection and model parameters. If omitted, the backend process environment variables are used as fallback.
- `customHeaders`: Custom request headers, as a JSON object or JSON string.
- `apiVersion`: Used by the native Gemini SDK.
- `targetCases`: Runs only matching cases, using the same syntax as `TARGET_CASES`. If omitted or set to an empty string, the recommended cases for the current model are run by default.
- When `targetCases` is not specified, cases with parameters known to be incompatible with the selected test model are filtered out automatically, such as reasoning-only cases, legacy `max_tokens` cases, Gemini image/audio model cases, and similar model-specific cases. When `targetCases` is provided explicitly, the manual selection takes precedence.
- `testModel` in the report indicates the actual test model selected for the case. Some cases use dedicated model slots, such as `OPENAI_REASONING_MODEL`, `OPENAI_AUDIO_MODEL`, `GEMINI_IMAGE_MODEL`, or Anthropic Opus/Haiku/Fast Mode models.
- `timeoutMs` / `concurrency` / `failFast`: Run control parameters.
- `pluginPaths`: Optional array of plugin module paths, or a comma-separated string. Paths are resolved relative to the backend process working directory.
- `billingAudit`: Optional R9S billing audit configuration, in the form `{ "enabled": true, "managerBaseUrl": "https://portal-api.r9s.ai", "managerKey": "...", "tokenId": "tk_xxx" }`. When enabled, all cases run first, then the R9S Manager API usage endpoint is called and the local usage is compared with platform billing records in the report.
- `workingDirectory` / `skipGitRepoCheck` / `testImagePath`: Agent test parameters.
- `persistResult`: Whether to write the run into backend history. Defaults to `true`.
- `runSnapshot`: Optional run snapshot, written into the report as-is.

Within `targets[]`, `apiKey`, `apiBaseUrl`, `customHeaders`, `apiVersion`, `timeoutMs`, `concurrency`, `workingDirectory`, `skipGitRepoCheck`, `testImagePath`, and `failFast` override the top-level fields with the same names. This makes it possible to mix different targets in a single API request.

### Plugin Mechanism

The Node runner supports plugins that listen to the test lifecycle. Configure plugins for the CLI with `LLM_SPEC_PLUGINS=./plugins/a.mjs,./plugins/b.mjs`; for the backend API, pass `pluginPaths` in the request body.

A plugin module can default-export a plugin object, an array of plugin objects, or a factory function that returns a plugin object. Supported hooks:

- `beforeCase(context)`: Runs before a test case sends a real request. If a case sends multiple requests, the hook runs once per request. `context` includes `id`, `name`, `description`, `provider`, `testId`, `requestId`, `requestIndex`, and `request`. `request` includes `url`, `method`, `headers`, and `body`. The hook can return `{ request: { headers, body, url, method } }`, or return those fields directly, to modify the request. `headers` are merged; values set to `null` / `undefined` delete the corresponding header.
- `afterCase(context)`: Runs after a case result is produced. `context` includes the case name, description, `result`, the first `request` / `response`, and the full `exchanges` request/response array.
- `afterRun(context)`: Runs after all cases complete. `context.summary` is the full `RunSummary` report, including request and response traces for each case.

Example:

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

### R9S Billing Audit

The built-in R9S billing audit plugin runs through the `afterRun` lifecycle. It extracts OpenAI / Anthropic / Gemini-style `usage` data from local HTTP trace response bodies, then calls the R9S Manager API `GET /api/v1/portal/management/usage` using the run report's `startedAt` / `finishedAt` window. It compares local input/output/cached tokens with R9S billing records by model. The report's `billingAudit` field contains the query window, platform records, per-model diffs, warnings, and errors. The frontend Summary section also shows a diff table.

Enable it in the CLI with environment variables:

```bash
R9S_BILLING_AUDIT=true \
R9S_MANAGER_BASE_URL=https://portal-api.r9s.ai \
R9S_MANAGER_KEY=manager-key \
R9S_TOKEN_ID=tk_xxx \
TEST_API_KEY=target-api-key \
pnpm test:sdk
```

Pass it directly to the Backend API:

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

When `R9S Billing Audit` is enabled in the frontend Site Profile, the frontend requires Manager Base URL and Manager Key configuration and automatically runs the test through the backend, so the Manager Key is not exposed in the browser. `token_id` filtering is enabled only when `billingAudit.tokenId` / `R9S_TOKEN_ID` is explicitly configured. If no token ID is configured, the plugin queries the whole time window and notes in the report that filtering by `token_id` was not applied. If R9S billing fields are missing or cannot be parsed, the report shows `not fetched` with a warning instead of replacing the unknown value with 0.

### Start the Frontend

```bash
pnpm dev:reporter
```

In development mode, the frontend connects to `http://localhost:8788` by default. In production builds, it connects to the backend on the same origin as the current page by default. You can also set this before building/running:

```bash
VITE_LLM_SPEC_BACKEND_URL=http://your-backend:8788 pnpm --filter @llm-spec/reporter build
```

### Package as a Single Node Service

If you want the frontend and backend to be served by the same Node service:

```bash
pnpm build:service
pnpm start:service
```

`build:service` builds the reporter frontend and the llm-spec backend, then copies the frontend assets into `packages/llm-spec/dist/public/`. After startup, `/api/*` is handled by the backend endpoints, and all other paths return the frontend static files from the same service.

Use `LLM_SPEC_STATIC_DIR` to override the static file directory.

### Execution Strategy

- Standard API tests run in the browser by default, using `fetch` to request the target API directly and generating the same report structure as the CLI.
- Standard API tests can be switched to backend execution for target APIs that do not support CORS, require private-network access, or need centralized secret management.
- Agent tests such as `claude-agent` / `codex` can only run through the backend. The frontend is responsible for collecting the API key, base URL, working directory, case filter, and related configuration.

### Site Profiles and Test Matrix

The platform frontend splits configuration into two layers:

- Site Profile: Stores connection information that changes infrequently, such as API key, base URL, custom headers, backend URL, and Agent working directory.
- Test Matrix: Stores the target rows for the current run. Each row can independently select the API/Agent, model, and case filter, and can be quickly added, removed, or edited before execution.

During execution, the frontend calls the existing run API row by row according to the Test Matrix and merges the reports. The report includes `runSnapshot`, which records the site, model, case filter, and execution mode actually used for the run.

## Running Tests

### Single-Target Mode

After setting `TEST_API_TYPE`, `TARGET_PROVIDERS` is ignored and only one API surface is tested:

```bash
TEST_API_TYPE=openai.chat \
TEST_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ \
TEST_API_KEY=your_gemini_key_here \
TEST_MODEL=gemini-2.5-flash \
pnpm test:sdk
```

Supported `TEST_API_TYPE` values:

- `openai.chat`
- `openai.responses`
- `anthropic.messages`
- `gemini.generateContent`

Examples:

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

- Run all providers (default): `openai,anthropic,gemini`
- Specify providers:

```bash
TARGET_PROVIDERS=openai pnpm test:sdk
TARGET_PROVIDERS=anthropic,gemini pnpm test:sdk
TARGET_PROVIDERS=xai pnpm test:sdk
TARGET_PROVIDERS=claude-agent pnpm test:sdk
```

- Run only specified test cases, separated by commas:

```bash
TARGET_CASES=basic,stream pnpm test:sdk
TARGET_CASES=claude-agent:basic_prompt,openai:responses_* pnpm test:sdk
```

Notes:

- Supports `caseId` and `provider:caseId`.
- Also supports `apiType:caseId`, such as `openai.chat:basic`, `openai.responses:responses_*`, and `anthropic.messages:*`.
- Supports wildcards: `*` for any length and `?` for a single character.
- Compatible alias environment variables: `TEST_CASES` and `CASE_IDS`.

- Stop on first failure:

```bash
FAIL_FAST=true pnpm test:sdk
```

- Output reports (JSON + HTML + plain text):

```bash
REPORT_FILE=./report.json pnpm test:sdk
```

This generates:

- `./report.json`
- `./report.html`
- `./report.txt`

## Configuration

### General Configuration

- `API_KEY`
- `API_BASE_URL`
- `TARGET_PROVIDERS`
- `TARGET_CASES` (optional; only runs matching cases)
- `FAIL_FAST`
- `REPORT_FILE`
- `SDK_TIMEOUT_MS`
- `LLM_SPEC_PLUGINS` (comma-separated Node plugin module paths)
- `CUSTOM_HEADERS` (JSON object string, used as unified custom request header configuration for the OpenAI SDK / Claude Agent; compatible with the legacy `OPENAI_CUSTOM_HEADERS` / `CLAUDE_AGENT_CUSTOM_HEADERS`)

### Single-Target Configuration

- `TEST_API_TYPE`
- `TEST_API_KEY`
- `TEST_API_BASE_URL`
- `TEST_MODEL`
- `TEST_TIMEOUT_MS`
- `TEST_CUSTOM_HEADERS` (JSON object string, currently mainly used for the OpenAI SDK)
- `TEST_API_VERSION` (used by the native Gemini SDK)

### OpenAI

- `OPENAI_API_KEY`
- `OPENAI_API_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_AUDIO_MODEL` (enables audio modality tests)
- `OPENAI_REASONING_MODEL` (enables reasoning parameter tests for the Responses API)
- `OPENAI_RESPONSES_PROMPT_ID` (enables prompt parameter tests for the Responses API)
- `OPENAI_INCLUDE_MODEL_CATALOG_CASES` (enables GPT/OpenAI model catalog smoke tests; these filterable cases are also automatically loaded when `TARGET_CASES` is set)

### xAI

- `XAI_API_KEY`
- `XAI_API_BASE_URL` (defaults to `https://api.x.ai/v1`)
- `XAI_MODEL` (defaults to `grok-beta`, reuses OpenAI-compatible `chat.completions` cases)
- `XAI_TIMEOUT_MS`

### Anthropic

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_API_BASE_URL`
- `ANTHROPIC_MODEL`
- `ANTHROPIC_OPUS_MODEL` / `ANTHROPIC_HAIKU_MODEL` / `ANTHROPIC_FAST_MODE_MODEL` (optional; related cases use `ANTHROPIC_MODEL` when these are not set)
- `ANTHROPIC_INFERENCE_GEO` (enables `inference_geo` parameter tests)
- `ANTHROPIC_INCLUDE_MODEL_CATALOG_CASES` (enables Claude Messages model catalog smoke tests; these filterable cases are also automatically loaded when `TARGET_CASES` is set)

### Claude Agent

- `CLAUDE_AGENT_API_KEY`
- `CLAUDE_AGENT_API_BASE_URL`
- `CLAUDE_AGENT_MODEL`
- `CLAUDE_AGENT_OPUS_MODEL` / `CLAUDE_AGENT_SONNET_MODEL` / `CLAUDE_AGENT_HAIKU_MODEL` (optional; only used when specific Agent cases need model-slot overrides; falls back to `CLAUDE_AGENT_MODEL` when unset)

Note: Use `CUSTOM_HEADERS` to inject Agent request headers, such as `{"X-Debug-Channel-ID":"13"}`. The legacy `CLAUDE_AGENT_CUSTOM_HEADERS` and `ANTHROPIC_CUSTOM_HEADERS` are also supported.

### Gemini

- `GEMINI_API_KEY`
- `GEMINI_API_BASE_URL`
- `GEMINI_API_VERSION`
- `GEMINI_MODEL`
- `GEMINI_CACHED_CONTENT` (enables cachedContent tests)
- `GEMINI_AUDIO_MODEL` (enables audio-related parameter tests)
- `GEMINI_IMAGE_MODEL` (enables imageConfig tests)
- `GEMINI_ENABLE_VERTEX_ONLY_CASES` (enables Vertex-oriented features such as routing/modelSelection)
- `GEMINI_MODEL_ARMOR_PROMPT_TEMPLATE`
- `GEMINI_MODEL_ARMOR_RESPONSE_TEMPLATE`
- `GEMINI_INCLUDE_MODEL_CATALOG_CASES` (enables smoke tests for currently serviceable Gemini generateContent models; these filterable cases are also automatically loaded when `TARGET_CASES` is set)

## Output

The script outputs:

- `PASS / FAIL / SKIP` for each test case
- Parameter coverage statistics for each provider (`covered` / `untested`; `covered` only counts `PASS` cases)
- Final summary (total passed/failed/skipped)

When `REPORT_FILE` is set, three formats are generated by default:

- `JSON`: Machine-readable, suitable for post-processing
- `HTML`: Visual report, suitable for quick manual review
- `TXT`: Plain text, suitable for terminals, logging systems, and CI artifact previews

If any test case fails, the process exits with code `1`.

## Code Structure

The project now uses a pnpm workspace:

- `packages/llm-spec/`
  - Node CLI, backend server, and SDK/Agent test runner
- `packages/reporter/`
  - Vite + React report and platform frontend
- `docs/`
  - API reference documentation snapshots

Test execution code is organized into two parts:

- `packages/llm-spec/src/api-sdk-tester/environment/`
  - Runtime environment parsing
  - `.env` loading and provider configuration
  - `TARGET_CASES` filtering
  - HTTP request logging and provider context
- `packages/llm-spec/src/api-sdk-tester/cases/`
  - Test case definitions for each provider/agent
  - `TestCase` type and case executor
  - Provider-level coverage statistics and execution summary
