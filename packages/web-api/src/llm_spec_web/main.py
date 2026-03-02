"""FastAPI entrypoint for llm-spec web backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from llm_spec_web.api.provider_configs import router as provider_config_router
from llm_spec_web.api.runs import router as runs_router
from llm_spec_web.api.settings import router as settings_router
from llm_spec_web.api.suites import router as suites_router
from llm_spec_web.api.tasks import router as tasks_router
from llm_spec_web.config import settings
from llm_spec_web.core.db import Base, engine
from llm_spec_web.core.error_handler import llm_spec_exception_handler
from llm_spec_web.core.exceptions import LlmSpecError


def _migrate_run_job_model_suite_id() -> None:
    """Ensure ``run_job.model_suite_id`` exists and is backfilled from legacy column."""
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "run_job" not in inspector.get_table_names():
            return

        columns = {str(col["name"]) for col in inspector.get_columns("run_job")}
        if "model_suite_id" in columns:
            return

        conn.execute(text("ALTER TABLE run_job ADD COLUMN model_suite_id VARCHAR(128)"))
        if "suite_version_id" in columns:
            conn.execute(
                text(
                    "UPDATE run_job SET model_suite_id = suite_version_id "
                    "WHERE model_suite_id IS NULL"
                )
            )


def init_db() -> None:
    """Initialize DB tables."""
    Base.metadata.create_all(bind=engine)
    _migrate_run_job_model_suite_id()


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
    app.include_router(provider_config_router)
    app.include_router(runs_router)
    app.include_router(tasks_router)
    app.include_router(settings_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("llm_spec_web.main:app", host="0.0.0.0", port=8000, reload=True)
