<div align="center">

# llm-spec

**A registry-first LLM API parameter compliance testing toolkit**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![TypeScript](https://img.shields.io/badge/typescript-5.6+-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.115+-green)

</div>

`llm-spec` is a config-driven test system for validating whether LLM API parameters are truly supported and stable.

It provides a complete evidence chain:

`Request -> Response -> Validator/Rule -> Test Result`

---

## What Changed (Current Architecture)

This project now uses a **registry-first** design:

- Test suites are loaded from `suites-registry/` files (not stored in DB).
- Provider runtime config is stored in `llm-spec.toml` (not `provider_config` DB table).
- Web backend DB (SQLite by default) stores only run/task data.
- FastAPI auto-creates run tables on startup when `LLM_SPEC_WEB_AUTO_INIT_DB=true`.

---

## Repository Layout

- `packages/core`: test runner engine, adapters, validators
- `packages/web-api`: FastAPI backend
- `packages/web`: React + Vite frontend
- `suites-registry`: community-maintained provider/route/model registry

Registry structure:

```text
suites-registry/
  providers/<provider>/
    provider.toml
    routes/*.json5
    models/*.toml
  assets/
    audio/
    images/
```

---

## Quick Start

### 1) Install dependencies

```bash
uv venv -p 3.11
uv sync --extra dev --extra web
```

### 2) Create runtime config

```bash
cp llm-spec.example.toml llm-spec.toml
# edit API keys/base_url/timeout as needed
```

### 3) (Optional) frontend deps

```bash
cd packages/web
pnpm install
cd ../..
```

---

## Run Test Engine

Run core unit tests:

```bash
uv run pytest packages/core/tests/unit -v
```

Run config-driven integration suites:

```bash
uv run pytest packages/core/tests/integration/test_suite_runner.py -v
```

Mock mode:

```bash
uv run pytest packages/core/tests/integration/test_suite_runner.py --mock -v
```

Useful Make targets:

```bash
make test-core
make test-integration
make test-mock-all
```

---

## Run Web App

### Backend

```bash
cp packages/web-api/src/llm_spec_web/env.example .env
uv run python -m llm_spec_web.main
```

Or:

```bash
make web-backend
```

Backend URL: `http://localhost:8000`

### Frontend

```bash
cd packages/web
pnpm dev
```

Or:

```bash
make web-frontend
```

Frontend URL: `http://localhost:5173`

---

## Web Backend Runtime (SQLite)

Default DB URL:

`sqlite:///./packages/web-api/src/llm_spec_web/.data/llm_spec_web.db`

The backend manages tables via SQLAlchemy metadata (run tables only):

- `task`
- `run_job`
- `run_event`
- `task_result`
- `run_test_result`

Task result payload (`/api/runs/{run_id}/task-result`) now uses a task-centric schema:

- `TaskResult` (`version = "task_result.v1"`)
- flat `cases: CaseResult[]` list (instead of nested `providers[].endpoints[].tests[]`)
- each `CaseResult` carries provider/model/route/endpoint/test-level execution + validation facts

If you want a fresh DB:

```bash
rm -f packages/web-api/src/llm_spec_web/.data/llm_spec_web.db
# restart backend, tables will be recreated automatically
```

Schema reference:

- `packages/web-api/src/llm_spec_web/schema.sql`

---

## Environment Variables

Core web settings:

- `LLM_SPEC_WEB_DATABASE_URL`
- `LLM_SPEC_WEB_APP_TOML_PATH`
- `LLM_SPEC_WEB_AUTO_INIT_DB`
- `LLM_SPEC_WEB_MOCK_MODE`
- `LLM_SPEC_WEB_MOCK_BASE_DIR`
- `LLM_SPEC_WEB_CORS_ORIGINS`
- `LLM_SPEC_WEB_SUITE_REGISTRY_CACHE_TTL_SECONDS`

Default values can be found in:

- `packages/web-api/src/llm_spec_web/config.py`
- `packages/web-api/src/llm_spec_web/env.example`

---

## Registry Model

`llm-spec` expands suites as:

`provider routes/*.json5 × models/*.toml`

Key points:

- `provider.toml` defines provider metadata, `api_family`, optional `routes_from` inheritance.
- `routes/*.json5` defines endpoint/baseline params/tests template.
- `models/*.toml` defines model route coverage and optional overrides.
- Shared upload assets should be placed in `suites-registry/assets/`.

See:

- `suites-registry/DESIGN.md`
- `suites-registry/README.md`
- `suites-registry/CONTRIBUTING.md`

---

## Web Suite Loading & Cache

- `/api/suites` and `/api/suites/{id}/versions` are read-only views over registry files.
- Backend keeps in-memory cache with TTL + file-signature invalidation.
- Manual cache refresh endpoint: `POST /api/suites/cache/refresh`
- Frontend Testing page provides a **Refresh Memory** button and loading animation.

---

## Provider Config Source of Truth

Provider config used by runtime and web API is read/written from:

- `llm-spec.toml`

Example:

```toml
[providers.openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0
api_family = "openai"
```

---

## Development Notes

- Python package manager: `uv`
- Frontend package manager: `pnpm`
- Lint/format/test are configured in `pyproject.toml` and frontend configs.

---

## License

MIT
