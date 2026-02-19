"""FastAPI entrypoint for llm-spec web backend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_spec.web.api.provider_configs import router as provider_config_router
from llm_spec.web.api.runs import router as runs_router
from llm_spec.web.api.settings import router as settings_router
from llm_spec.web.api.suites import router as suites_router
from llm_spec.web.api.suites import version_router as suite_versions_router
from llm_spec.web.config import settings
from llm_spec.web.db import Base, engine


def create_app() -> FastAPI:
    app = FastAPI(title="llm-spec web api", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(suites_router)
    app.include_router(suite_versions_router)
    app.include_router(provider_config_router)
    app.include_router(runs_router)
    app.include_router(settings_router)
    return app


app = create_app()


def init_db() -> None:
    """Initialize DB tables (for local development)."""
    Base.metadata.create_all(bind=engine)
