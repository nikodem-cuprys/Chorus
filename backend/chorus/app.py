"""The `web` service: the JSON API under /api, server-sent events, and the built frontend.

Text shown to the user never comes from here: the API sends message-catalogue keys with
parameters (for example `{"key": "job.error.unexpected", "params": {...}}`) and the frontend
turns them into words.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus import events, healthcheck, tasks  # noqa: F401  (tasks registers every job kind)
from chorus.config import get_settings
from chorus.db import get_session
from chorus.jobs import enqueue
from chorus.models import Job

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict:
    return {"status": "ok"}


@api.get("/system/health")
def system_health() -> dict:
    """The worker's startup check; `ok` is null until the worker has run it."""
    return healthcheck.load() or {"checked_at": None, "ok": None, "checks": []}


@api.get("/jobs")
def list_jobs(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.scalars(select(Job).order_by(Job.id.desc()).limit(50))
    return [row.to_dict() for row in rows]


@api.get("/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    row = session.get(Job, job_id)
    if row is None:
        raise HTTPException(404, detail={"key": "job.error.not_found", "params": {"id": job_id}})
    return row.to_dict()


@api.get("/events")
async def stream_events(request: Request) -> StreamingResponse:
    """Server-sent events: every job update, as `event: job` with the job as JSON."""

    async def lines() -> AsyncIterator[str]:
        yield ": connected\n\n"
        async for message in events.subscribe():
            if await request.is_disconnected():
                break
            yield f"event: {message['event']}\ndata: {json.dumps(message['data'])}\n\n"

    return StreamingResponse(
        lines(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


dev = APIRouter(prefix="/api/dev")


class DevJob(BaseModel):
    queue: str = Field(pattern="^(gpu|other)$")
    steps: int = Field(5, ge=1, le=1000)
    step_seconds: float = Field(0.5, ge=0, le=60)


@dev.post("/jobs", status_code=201)
def start_dev_job(body: DevJob, session: Session = Depends(get_session)) -> dict:
    row = enqueue(session, f"dev.{body.queue}", steps=body.steps, step_seconds=body.step_seconds)
    return row.to_dict()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Chorus", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(api)
    if settings.dev:
        app.include_router(dev)

    dist = settings.frontend_dist.resolve()
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str) -> FileResponse:
            # Every non-API path is the single-page app; it does its own routing.
            if path.startswith("api/"):
                raise HTTPException(404)
            candidate = dist / path
            if path and candidate.is_file() and dist in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
