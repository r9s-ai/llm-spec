# llm-spec Web Backend

This document has been merged into the repo root `README.md` under the **Web UI** section to keep a
single source of truth for setup and API usage.

If you are looking for:
- Web backend setup (SQLite default, `.env`, schema init): see `README.md`
- API endpoints and behavior: see `README.md`
- DB schema reference (SQLite flavor): see `packages/web-api/src/llm_spec_web/schema.sql`
- Task result response shape: `/api/runs/{run_id}/task-result` returns `task_result.v1` with `cases[]`

Note: tables are auto-created on FastAPI startup when `LLM_SPEC_WEB_AUTO_INIT_DB=true` (default).
