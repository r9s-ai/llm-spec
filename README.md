<div align="center">

# llm-spec

**A config-driven LLM API compliance and parameter support probing tool**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![Python Version](https://img.shields.io/badge/python-3.11+-blue)
![TypeScript](https://img.shields.io/badge/typescript-5.6+-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.115+-green)



</div>

---

🚀 [Getting Started](#getting-started) - 🔧 [Configuration](#configuration) - 💻 [CLI Usage](#cli-usage) - 🌐 [Web UI](#web-ui) - 📊 [Reports](#reports) - 🛣️ [Roadmap](#roadmap)

`llm-spec` turns the question **"does this parameter work, how well does it work, and where does it break?"** into repeatable, aggregatable tests. It provides a complete **evidence chain**: `Request -> Response -> Verdict -> Run Result / Aggregated Report`.

## 🧭 Vision: Accuracy & Stability

Evaluating model capabilities is often plagued by "flaky passes" and "flaky fails". `llm-spec` focuses on stability through:

- **Control-variable Testing**: Start from a baseline request and introduce exactly one parameter/value change at a time.
- **Structured Validation**: Validate responses against Pydantic schemas to pinpoint missing fields or structural changes.
- **Streaming Completeness**: Use **Stream Rules** to validate not just individual chunks, but the entire sequence of events (e.g., terminal markers).
- **Evidence-based reporting**: Every failure is attributed to a specific cause: HTTP error, upstream logic error, schema mismatch, or rule violation.

## 📦 Supported Providers

Built-in suite configurations are located in `suites-registry/providers/`.

## 🗂️ Project Layout

- `packages/core`: runner/adapters/reporting + core tests
- `packages/web-api`: FastAPI backend
- `packages/web`: React frontend
- `suites-registry/providers`: community-maintained JSON5 suites

| Provider | Status | Default Model | Endpoints |
|----------|--------|---------------|-----------|
| **OpenAI** | ✅ | `gpt-4o-mini` | Chat, Embeddings, Images, Audio, etc. |
| **Anthropic** | ✅ | `claude-haiku-4.5` | Messages |
| **Gemini** | ✅ | `gemini-3-flash-preview` | GenerateContent, StreamGenerateContent |
| **xAI** | ✅ | `grok-beta` | Chat (OpenAI-compatible) |

## 🪴 Getting Started

`llm-spec` is built with **uv**. We recommend using it for environment and dependency management.

```bash
# 1) Create a venv (Python 3.11+)
uv venv -p 3.11

# 2) Install dependencies (including dev)
uv sync --extra dev

# 3) Initialize configuration
cp llm-spec.example.toml llm-spec.toml
# Edit llm-spec.toml with your API keys
```

## ⚙️ Configuration (llm-spec.toml)

The configuration file controls API access, timeouts, and logging levels.

```toml
[openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0

[log]
enabled = true
log_request_body = true  # Great for debugging parameter forwarding
```

## 🧪 Config-driven Suites (JSON5)

Suites are defined in JSON5, allowing for comments and flexible syntax. Each suite typically targets one provider and endpoint.

```json5
{
  provider: "anthropic",
  endpoint: "/v1/messages",
  schemas: {
    response: "anthropic.MessagesResponse",
    stream_chunk: "anthropic.AnthropicStreamChunk",
  },
  base_params: {
    model: "claude-haiku-4.5",
    max_tokens: 256,
    messages: [{ role: "user", content: "Hello" }],
  },
  tests: [
    { name: "test_baseline", is_baseline: true },
    {
      name: "test_param_temperature",
      params: { temperature: 0.7 },
      test_param: { name: "temperature", value: 0.7 },
      required_fields: ["content[0].text"]
    }
  ]
}
```

## 💻 CLI Usage

```bash
# Execute all tests
uv run python -m llm_spec run

# Filter by provider or keyword
uv run python -m llm_spec run --provider openai
uv run python -m llm_spec run -k "chat/completions"
```

## 🌐 Web UI

`llm-spec` provides a modern web interface for managing suites, running tests, and viewing results visually.

### Features

- **Suite Management**: Create, update, delete suites and manage JSON5 versions through a visual editor
- **Testing Dashboard**: Select providers/routes/tests, execute batch runs, and monitor progress in real-time
- **Settings Editor**: Edit runtime TOML configuration for providers and report behavior
- **Run History**: View past runs with detailed results and event streams

### Tech Stack

- **Backend**: FastAPI (Python) with PostgreSQL
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS

### Environment Requirements

- Python >= 3.11
- PostgreSQL >= 14
- Node.js >= 18
- pnpm >= 9
- uv (Python package manager)

### Installation

```bash
# Install Python dependencies (including web extra)
uv sync --extra dev --extra web

# Install frontend dependencies
cd packages/web && pnpm install && cd ../..
```

### Database Setup

#### Create PostgreSQL Database

```bash
# Create database
createdb llm_spec

# Or using psql
psql -U postgres -c "CREATE DATABASE llm_spec;"
```

#### Initialize / Migrate Database Schema

```bash
# This file is idempotent: it creates tables if missing, applies minimal schema upgrades,
# and seeds built-in suites into the DB.
psql -U postgres -d llm_spec -f packages/web-api/src/llm_spec_web/schema.sql
```

### Environment Variables

Create a `.env` file or export environment variables:

```bash
# Copy example config
cp packages/web-api/src/llm_spec_web/env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_SPEC_WEB_DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec` |
| `LLM_SPEC_WEB_APP_TOML_PATH` | Path to llm-spec.toml | `llm-spec.toml` |
| `LLM_SPEC_WEB_MOCK_MODE` | Enable mock mode for testing | `false` |
| `LLM_SPEC_WEB_MOCK_BASE_DIR` | Mock data directory | `packages/core/tests/integration/mocks` |
| `LLM_SPEC_WEB_CORS_ORIGINS` | CORS allowed origins | `["*"]` |

### Provider Configuration

The web backend reads runtime provider settings from `llm-spec.toml` via `LLM_SPEC_WEB_APP_TOML_PATH`.

Provider configs are required for `real` runs. For `mock` runs, the backend can execute without provider
credentials.

```toml
[openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0

[anthropic]
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com"
timeout = 30.0
```

### Running the Server

```bash
# Start backend server
uv run python -m llm_spec_web.main

# Or using uvicorn directly
uv run uvicorn llm_spec_web.main:app --reload --port 8000

# Start frontend dev server (in another terminal)
cd packages/web && pnpm dev
```

Or use Makefile shortcuts:

```bash
make web-backend
make web-frontend
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

### Suites In DB

The initial web schema (`packages/web-api/src/llm_spec_web/schema.sql`) seeds the built-in suites from `suites-registry/providers/` into the
database (via `suite` + `suite_version`). For custom suites, use the Web UI (or call the `/api/suites`
endpoints) to create and version them.

### Database Schema

#### suite - Test Suites

| Field | Type | Description |
|-------|------|-------------|
| id | varchar(36) | Primary key UUID |
| provider | varchar(32) | Provider name (openai, anthropic, gemini, xai) |
| endpoint | varchar(255) | API endpoint path |
| name | varchar(255) | Suite name |
| status | varchar(16) | Status (active/archived) |
| latest_version | integer | Latest version number |

#### suite_version - Suite Versions

| Field | Type | Description |
|-------|------|-------------|
| id | varchar(36) | Primary key UUID |
| suite_id | varchar(36) | Foreign key to suite |
| version | integer | Version number |
| raw_json5 | text | Original JSON5 content |
| parsed_json | jsonb | Parsed JSON data |

#### run_batch - Test Task Batch

| Field | Type | Description |
|-------|------|-------------|
| id | varchar(36) | Primary key UUID |
| status | varchar(16) | Status (running/completed/cancelled) |
| mode | varchar(16) | Mode (real/mock) |
| total_runs | integer | Total number of runs |
| completed_runs | integer | Completed run count |
| passed_runs | integer | Passed run count |
| failed_runs | integer | Failed run count |
| started_at | timestamptz | Start timestamp |
| finished_at | timestamptz | Finish timestamp |
| created_at | timestamptz | Creation timestamp |

#### run_job - Execution Jobs

| Field | Type | Description |
|-------|------|-------------|
| id | varchar(36) | Primary key UUID |
| status | varchar(16) | Status (queued/running/success/failed/cancelled) |
| mode | varchar(16) | Mode (real/mock) |
| provider | varchar(32) | Provider name |
| batch_id | varchar(36) | Foreign key to run_batch |
| progress_total | integer | Total tests |
| progress_passed | integer | Passed count |
| progress_failed | integer | Failed count |

#### run_result - Execution Results

| Field | Type | Description |
|-------|------|-------------|
| run_id | varchar(36) | Primary key, foreign key to run_job |
| run_result_json | jsonb | Full result JSON data |
| created_at | timestamptz | Creation timestamp |

#### provider_config - Provider Configurations

| Field | Type | Description |
|-------|------|-------------|
| provider | varchar(32) | Primary key (provider name) |
| base_url | varchar(512) | API base URL |
| timeout | double precision | Request timeout seconds |
| api_key | text | API key |
| extra_config | jsonb | Extra per-provider config |
| updated_at | timestamptz | Last update timestamp |

#### run_event - Run Events

| Field | Type | Description |
|-------|------|-------------|
| id | bigserial | Primary key |
| run_id | varchar(36) | Foreign key to run_job |
| seq | integer | Sequence number (unique per run_id) |
| event_type | varchar(64) | Event type |
| payload | jsonb | Event payload |
| created_at | timestamptz | Creation timestamp |

#### run_test_result - Individual Test Results

| Field | Type | Description |
|-------|------|-------------|
| id | varchar(36) | Primary key UUID |
| run_id | varchar(36) | Foreign key to run_job |
| test_id | varchar(512) | Stable test id |
| test_name | varchar(255) | Test name |
| parameter_name | varchar(255) | Parameter under test |
| parameter_value | jsonb | Tested value |
| status | varchar(16) | pass/fail |
| fail_stage | varchar(32) | request/schema/required_fields/stream_rules |
| reason_code | varchar(64) | Failure reason code |
| latency_ms | integer | Latency in milliseconds |
| raw_record | jsonb | Full test record |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /healthz` | Health check |
| `GET/POST/PUT/DELETE /api/suites` | Suite CRUD operations |
| `GET/POST /api/suites/{suite_id}/versions` | Suite version management |
| `GET /api/suite-versions/{version_id}` | Get suite version details |
| `GET /api/provider-configs` | List provider configurations |
| `GET /api/provider-configs/{provider}` | Get provider config |
| `PUT /api/provider-configs/{provider}` | Update provider config |
| `POST /api/batches` | Create a new test batch (multiple runs) |
| `GET /api/batches` | List batches |
| `GET /api/batches/{batch_id}` | Get batch details with runs |
| `DELETE /api/batches/{batch_id}` | Delete a batch and its runs |
| `GET /api/batches/{batch_id}/runs` | Get runs in a batch |
| `POST /api/runs` | Create a new test run (single) |
| `GET /api/runs` | List runs |
| `GET /api/runs/{run_id}` | Get run details |
| `POST /api/runs/{run_id}/cancel` | Cancel a running test |
| `GET /api/runs/{run_id}/events` | Get run events (polling) |
| `GET /api/runs/{run_id}/events/stream` | SSE event stream |
| `GET /api/runs/{run_id}/result` | Get run result JSON |
| `GET /api/runs/{run_id}/tests` | Get test results list |
| `GET/PUT /api/settings/toml` | TOML configuration |

> [!TIP]
> OpenAPI spec is available at `packages/web-api/src/llm_spec_web/openapi.yaml` (OpenAPI 3.1.0).

### Real-time Progress Updates

The web backend uses an in-memory event bus for real-time progress updates:

1. **Event Bus**: Events are pushed to memory queues instead of frequent database writes
2. **SSE (Server-Sent Events)**: Frontend subscribes via `/api/runs/{run_id}/events/stream`
3. **Database Persistence**: Only terminal events (run_finished, run_failed) are saved to database for history

Event types:
- `run_started` - Run begins execution
- `test_started` - Individual test begins
- `test_finished` - Individual test completes (with progress info)
- `run_finished` / `run_failed` / `run_cancelled` - Terminal events

### Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Suite not found: abc123"
  }
}
```

Error codes:
- `NOT_FOUND` (404): Resource not found
- `VALIDATION_ERROR` (400): Invalid input data
- `DUPLICATE` (409): Resource already exists
- `CONFIGURATION_ERROR` (500): Configuration issue
- `EXECUTION_ERROR` (500): Run execution failure

### Mock Mode

Mock mode allows testing without actual API calls:

```bash
export LLM_SPEC_WEB_MOCK_MODE=true
```

Mock data is stored in `packages/core/tests/integration/mocks/`.

### Architecture

Web backend layout (high-level):

```text
packages/web-api/src/llm_spec_web/
├── api/           # FastAPI routers/controllers
├── core/          # DB wiring, exceptions, event bus
├── models/        # SQLAlchemy ORM models
├── schemas/       # Pydantic request/response models
├── services/      # Business logic
└── repositories/  # Data access
```

## 📊 Reports

Every run generates a unique `run_id` directory in `reports/` containing:
- `run_result.json`: Stable run-level structure (`providers[] -> endpoints[] -> tests[]`).
- `report.md`: Human-readable run-level report rendered from `run_result.json`.
- `report.html`: Visual run-level report rendered from `run_result.json`.

> [!TIP]
> `run_result.json` is the single source of truth; report files are view projections.
> Each `tests[]` item records execution outcome (`result.status`) and failure reason (`result.reason`).

## 🛠️ Development

### Run Tests

```bash
uv run pytest
```

Or use scoped Make targets:

```bash
make test-core
make test-integration
make test-mock-all
```

### Code Formatting

```bash
uv run ruff format .
uv run ruff check . --fix
```

### Type Checking

```bash
uv run pyright
```

## 🗺️ Roadmap

- [ ] **Multimodal Probing**: Support for image/video/audio input suites.
- [ ] **Binary Streaming**: Validation for binary stream responses (e.g., TTS).
- [ ] **Cross-run Diffs**: Compare API behavior changes between different releases.
- [ ] **CI Integration**: Post reports directly to PRs or dashboards.

---

## 📝 License

MIT
