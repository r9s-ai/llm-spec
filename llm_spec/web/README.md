# llm-spec Web Backend

A FastAPI-based web API for managing and executing llm-spec test suites.

## Architecture

The web backend follows a layered architecture:

```
llm_spec/web/
├── api/                    # API route layer (Controller)
│   ├── deps.py            # Dependency injection
│   ├── suites.py          # Suite routes
│   ├── runs.py            # Run routes
│   ├── provider_configs.py # Provider config routes
│   └── settings.py        # Settings routes
│
├── core/                   # Core functionality
│   ├── db.py              # Database connection
│   ├── exceptions.py      # Custom exceptions
│   ├── error_handler.py   # Global exception handler
│   └── utils.py           # Utility functions
│
├── models/                 # SQLAlchemy ORM models
│   ├── suite.py           # Suite, SuiteVersion
│   ├── run.py             # RunJob, RunEvent, RunResult
│   └── provider.py        # ProviderConfigModel
│
├── schemas/                # Pydantic request/response models
│   ├── suite.py
│   ├── run.py
│   ├── provider.py
│   └── settings.py
│
├── services/               # Business logic layer
│   ├── suite_service.py
│   ├── run_service.py
│   └── provider_service.py
│
├── repositories/           # Data access layer
│   ├── suite_repo.py
│   ├── run_repo.py
│   └── provider_repo.py
│
├── adapters/               # Adapters
│   └── mock_adapter.py    # Mock adapter
│
├── main.py                 # FastAPI application entry
└── config.py               # Configuration management
```

## Install

```bash
uv sync --extra dev --extra web
```

## Configure DB

```bash
export LLM_SPEC_WEB_DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec'
export LLM_SPEC_WEB_APP_TOML_PATH='llm-spec.toml'
export LLM_SPEC_WEB_MOCK_MODE='false'
psql postgresql://postgres:postgres@localhost:5432/llm_spec -f llm_spec/web/schema.sql
```

## Run

```bash
# Using uvicorn directly
uv run uvicorn llm_spec.web.main:app --reload --port 8000

# Or run as module
uv run python -m llm_spec.web.main
```

OpenAPI spec file:
- `llm_spec/web/openapi.yaml` (OpenAPI 3.1.0)

Import existing suites/provider config:

```bash
uv run python scripts/migrate_suites_to_web.py \
  --database-url 'postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec' \
  --config llm-spec.toml \
  --suites suites
```

## APIs

- `GET /healthz`
- `GET/POST/PUT/DELETE /api/suites`
- `GET/POST /api/suites/{suite_id}/versions`
- `GET /api/suite-versions/{version_id}`
- `GET /api/provider-configs`
- `PUT /api/provider-configs/{provider}`
- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/cancel`
- `GET /api/runs/{run_id}/events?after_seq=0`
- `GET /api/runs/{run_id}/events/stream`
- `GET /api/runs/{run_id}/result`
- `GET /api/runs/{run_id}/tests`
- `GET/PUT /api/settings/toml`

`POST /api/runs` can omit `mode`; backend will use `LLM_SPEC_WEB_MOCK_MODE`.

## Error Handling

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
