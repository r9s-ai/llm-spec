# llm-spec Web Backend (MVP)

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
uv run uvicorn llm_spec.web.main:app --reload --port 8000
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
