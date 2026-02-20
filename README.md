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

Built-in suite configurations are located in `suites/`.

| Provider | Status | Default Model | Endpoints |
|----------|--------|---------------|-----------|
| **OpenAI** | ✅ | `gpt-4o-mini` | Chat, Embeddings, Images, Audio, etc. |
| **Anthropic** | ✅ | `claude-3-5-haiku` | Messages |
| **Gemini** | ✅ | `gemini-2.0-flash` | GenerateContent, Embed, etc. |
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
    model: "claude-3-5-haiku-20241022",
    max_tokens: 1024,
    messages: [{ role: "user", content: "Hello" }],
  },
  tests: [
    { name: "test_baseline", is_baseline: true },
    {
      name: "test_param_temperature",
      params: { temperature: 0.7 },
      test_param: { name: "temperature", value: 0.7 },
      required_fields: ["choices[0].message.content"]
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

### Installation

```bash
# Install with web extra
uv sync --extra dev --extra web

# Install frontend dependencies
cd frontend && pnpm install
```

### Database Setup

```bash
export LLM_SPEC_WEB_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec'
export LLM_SPEC_WEB_APP_TOML_PATH='llm-spec.toml'
export LLM_SPEC_WEB_MOCK_MODE='false'

# Initialize database schema
psql postgresql://postgres:postgres@localhost:5432/llm_spec -f llm_spec/web/schema.sql
```

### Running the Server

```bash
# Start backend server
uv run uvicorn llm_spec.web.main:app --reload --port 8000

# Start frontend dev server (in another terminal)
cd frontend && pnpm dev
```

### Import Existing Suites

```bash
uv run python scripts/migrate_suites_to_web.py \
  --database-url 'postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec' \
  --config llm-spec.toml \
  --suites suites
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /healthz` | Health check |
| `GET/POST/PUT/DELETE /api/suites` | Suite CRUD operations |
| `GET/POST /api/suites/{suite_id}/versions` | Suite version management |
| `GET /api/provider-configs` | List provider configurations |
| `PUT /api/provider-configs/{provider}` | Update provider config |
| `POST /api/runs` | Create a new test run |
| `GET /api/runs` | List runs |
| `GET /api/runs/{run_id}` | Get run details |
| `POST /api/runs/{run_id}/cancel` | Cancel a running test |
| `GET /api/runs/{run_id}/events` | Get run events (polling) |
| `GET /api/runs/{run_id}/events/stream` | SSE event stream |
| `GET /api/runs/{run_id}/result` | Get run result |
| `GET/PUT /api/settings/toml` | TOML configuration |

> [!TIP]
> OpenAPI spec is available at `llm_spec/web/openapi.yaml` (OpenAPI 3.1.0).

## 📊 Reports

Every run generates a unique `run_id` directory in `reports/` containing:
- `run_result.json`: Stable run-level structure (`providers[] -> endpoints[] -> tests[]`).
- `report.md`: Human-readable run-level report rendered from `run_result.json`.
- `report.html`: Visual run-level report rendered from `run_result.json`.

> [!TIP]
> `run_result.json` is the single source of truth; report files are view projections.
> Each `tests[]` item records execution outcome (`result.status`) and failure reason (`result.reason`).

## 🗺️ Roadmap

- [ ] **Multimodal Probing**: Support for image/video/audio input suites.
- [ ] **Binary Streaming**: Validation for binary stream responses (e.g., TTS).
- [ ] **Cross-run Diffs**: Compare API behavior changes between different releases.
- [ ] **CI Integration**: Post reports directly to PRs or dashboards.

---

## 📝 License

MIT
