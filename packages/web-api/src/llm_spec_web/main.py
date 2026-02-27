"""FastAPI entrypoint for llm-spec web backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from llm_spec_web.api.batches import router as batches_router
from llm_spec_web.api.provider_configs import router as provider_config_router
from llm_spec_web.api.runs import router as runs_router
from llm_spec_web.api.settings import router as settings_router
from llm_spec_web.api.suites import router as suites_router
from llm_spec_web.api.suites import version_router as suite_versions_router
from llm_spec_web.config import settings
from llm_spec_web.core.db import Base, engine
from llm_spec_web.core.error_handler import llm_spec_exception_handler
from llm_spec_web.core.exceptions import LlmSpecError


def init_db() -> None:
    """Initialize DB tables."""
    _ensure_run_job_columns()
    _ensure_run_test_result_columns()
    Base.metadata.create_all(bind=engine)


def _ensure_run_job_columns() -> None:
    """Best-effort lightweight schema migration for run_job."""
    inspector = inspect(engine)
    if "run_job" not in inspector.get_table_names():
        return
    existing_cols = {col["name"] for col in inspector.get_columns("run_job")}
    ddl_by_col = {
        "route": "ALTER TABLE run_job ADD COLUMN route VARCHAR(128)",
        "model": "ALTER TABLE run_job ADD COLUMN model VARCHAR(128)",
    }
    for col_name, ddl in ddl_by_col.items():
        if col_name in existing_cols:
            continue
        with engine.begin() as conn:
            conn.execute(text(ddl))


def _ensure_run_test_result_columns() -> None:
    """Best-effort lightweight schema migration for run_test_result."""
    inspector = inspect(engine)
    if "run_test_result" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("run_test_result")}
    if "parameter_name" not in existing_cols:
        return

    # Rebuild the table to remove legacy `parameter_name` column.
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS run_test_result_new (
                    id VARCHAR(36) PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL REFERENCES run_job(id) ON DELETE CASCADE,
                    test_id VARCHAR(512) NOT NULL,
                    test_name VARCHAR(255) NOT NULL,
                    parameter_value JSON NULL,
                    status VARCHAR(16) NOT NULL,
                    fail_stage VARCHAR(32) NULL,
                    reason_code VARCHAR(64) NULL,
                    latency_ms INTEGER NULL,
                    raw_record JSON NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO run_test_result_new (
                    id,
                    run_id,
                    test_id,
                    test_name,
                    parameter_value,
                    status,
                    fail_stage,
                    reason_code,
                    latency_ms,
                    raw_record
                )
                SELECT
                    id,
                    run_id,
                    test_id,
                    test_name,
                    parameter_value,
                    status,
                    fail_stage,
                    reason_code,
                    latency_ms,
                    raw_record
                FROM run_test_result
                """
            )
        )
        conn.execute(text("DROP TABLE run_test_result"))
        conn.execute(text("ALTER TABLE run_test_result_new RENAME TO run_test_result"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_run_test_result_run_status "
                "ON run_test_result(run_id, status)"
            )
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifecycle hooks."""
    if settings.auto_init_db:
        init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="llm-spec web api",
        version="0.1.0",
        description="Web API for llm-spec test suite management and execution",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(LlmSpecError, llm_spec_exception_handler)  # type: ignore[arg-type]

    # Health check endpoint
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Health status.
        """
        return {"status": "ok"}

    # Include routers
    app.include_router(suites_router)
    app.include_router(suite_versions_router)
    app.include_router(provider_config_router)
    app.include_router(runs_router)
    app.include_router(batches_router)
    app.include_router(settings_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("llm_spec_web.main:app", host="0.0.0.0", port=8000, reload=True)
