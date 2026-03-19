"""FastAPI mock server that replays fixture responses by case id."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from llm_spec_mock_server import MockDataLoader

DEFAULT_FIXTURE_DIR = Path("packages/core/tests/integration/mocks")
CASE_ID_HEADER = "X-LLM-Spec-Case-Id"


def _parse_case_id(case_id: str) -> tuple[str, str, str, str]:
    parts = case_id.split(":", 3)
    if len(parts) != 4:
        raise ValueError(f"Invalid case id: {case_id}")
    provider, model, route, test_name = parts
    return provider, model, route, test_name


def _looks_like_stream(path: str, payload: Any) -> bool:
    if "stream" in path.lower():
        return True
    if isinstance(payload, dict):
        stream = payload.get("stream")
        if isinstance(stream, bool):
            return stream
    return False


def create_app(*, fixture_dir: Path = DEFAULT_FIXTURE_DIR) -> FastAPI:
    loader = MockDataLoader(fixture_dir)
    app = FastAPI(
        title="llm-spec mock server",
        version="0.1.0",
        description="HTTP fixture playback server for llm-spec mock providers",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def replay(path: str, request: Request):
        case_id = request.headers.get(CASE_ID_HEADER)
        if not case_id:
            raise HTTPException(status_code=400, detail=f"Missing {CASE_ID_HEADER}")

        try:
            provider, _model, _route, test_name = _parse_case_id(case_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        payload: Any = None
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if body:
                try:
                    payload = json.loads(body.decode("utf-8"))
                except Exception:
                    payload = None

        endpoint = "/" + path
        is_stream = _looks_like_stream(endpoint, payload)

        try:
            fixture = loader.load_response(
                provider=provider,
                endpoint=endpoint,
                test_name=test_name,
                is_stream=is_stream,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if is_stream:
            if isinstance(fixture, dict):
                raise HTTPException(status_code=500, detail="Expected stream fixture")

            def _iter_chunks() -> Iterator[bytes]:
                yield from fixture

            return StreamingResponse(_iter_chunks(), media_type="text/event-stream")

        if not isinstance(fixture, dict):
            raise HTTPException(status_code=500, detail="Expected JSON fixture")

        body = fixture.get("body")
        headers = dict(fixture.get("headers", {}))
        status_code = int(fixture.get("status_code", 200))

        if isinstance(body, (dict, list)):
            return JSONResponse(content=body, headers=headers, status_code=status_code)
        if isinstance(body, str):
            return PlainTextResponse(content=body, headers=headers, status_code=status_code)
        return JSONResponse(content=body, headers=headers, status_code=status_code)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("llm_spec_mock_server.main:app", host="0.0.0.0", port=8010, reload=True)
