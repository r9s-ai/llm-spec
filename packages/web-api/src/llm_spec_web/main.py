"""FastAPI entrypoint for llm-spec web backend."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="llm-spec web api",
        version="0.1.0",
        description="Web API for llm-spec test suite management and execution",
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


def init_db() -> None:
    """Initialize DB tables (for local development).

    This creates all tables defined in the models.
    For production, use Alembic migrations instead.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run("llm_spec_web.main:app", host="0.0.0.0", port=8000, reload=True)
