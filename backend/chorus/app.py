"""The `web` service: the JSON API under /api, server-sent events, and the built frontend.

Text shown to the user never comes from here: the API sends message-catalogue keys with
parameters (for example `{"key": "job.error.unexpected", "params": {...}}`) and the frontend
turns them into words.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus import assembly, events, firstrun, healthcheck, tasks, voices, voicing, works  # noqa: F401  (tasks: job kinds)
from chorus.config import get_settings
from chorus.db import get_session, get_sessionmaker
from chorus.importing.language import known_languages
from chorus.jobs import enqueue
from chorus.languages import get_packs
from chorus.models import Chapter, Job, JobState, Line, Voice, Work, WorkState

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict:
    return {"status": "ok"}


@api.get("/system/health")
def system_health() -> dict:
    """The worker's startup check; `ok` is null until the worker has run it."""
    return healthcheck.load() or {"checked_at": None, "ok": None, "checks": []}


@api.get("/system/models")
def system_models() -> dict:
    """The First run: each model's size and how much is downloaded; `ready` once all are."""
    return firstrun.status(firstrun.load_activity())


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


def _work(session: Session, work_id: int) -> Work:
    row = session.get(Work, work_id)
    if row is None:
        raise HTTPException(404, detail={"key": "work.error.not_found", "params": {"id": work_id}})
    return row


@api.get("/works")
def list_works(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.scalars(select(Work).order_by(Work.id.desc()))
    return [works.summary(row) for row in rows]


@api.post("/works", status_code=201)
async def import_work(file: UploadFile, session: Session = Depends(get_session)) -> dict:
    """Starts an import; the Work is in the "importing" state until the job is done."""
    data = await file.read()
    if not data:
        raise HTTPException(400, detail={"key": "import.error.empty", "params": {}})
    return works.detail(works.start_import(session, file.filename or "", data))


@api.get("/works/{work_id}")
def get_work(work_id: int, session: Session = Depends(get_session)) -> dict:
    return works.detail(_work(session, work_id))


class WorkChange(BaseModel):
    language: str = Field(pattern="^[a-z]{2,3}$")


@api.patch("/works/{work_id}")
def change_work(work_id: int, body: WorkChange, session: Session = Depends(get_session)) -> dict:
    row = _work(session, work_id)
    works.set_language(session, row, body.language)
    return works.detail(row)


@api.post("/works/{work_id}/analysis", status_code=202)
def analyse_work(work_id: int, session: Session = Depends(get_session)) -> dict:
    """Analyses the Work again from the start, or continues a stopped analysis (one whose
    worker was killed: its Work still says "analysing")."""
    row = _work(session, work_id)
    waiting = session.scalar(
        select(Job.id).where(
            Job.work_id == work_id, Job.kind == "analysis", Job.state == JobState.QUEUED
        )
    )
    if row.state == WorkState.IMPORTING or not row.chapters or waiting is not None:
        raise HTTPException(409, detail={"key": "work.error.busy", "params": {}})
    works.start_analysis(session, row)
    return works.detail(row)


@api.post("/works/{work_id}/voicing", status_code=202)
def voice_work(work_id: int, session: Session = Depends(get_session)) -> dict:
    """Voices every line that has no audio yet, or whose audio no longer matches it; also
    continues a stopped voicing."""
    row = _work(session, work_id)
    waiting = session.scalar(
        select(Job.id).where(
            Job.work_id == work_id, Job.kind == "voicing", Job.state == JobState.QUEUED
        )
    )
    if (row.analysis or {}).get("stage") != "done" or waiting is not None:
        raise HTTPException(409, detail={"key": "work.error.not_analysed", "params": {}})
    voicing.start_voicing(session, row)
    return works.detail(row)


@api.post("/works/{work_id}/assembly", status_code=202)
def assemble_work(work_id: int, session: Session = Depends(get_session)) -> dict:
    """Assembles every part whose lines are all voiced and whose audio is missing or out of
    date, as after a change to the pause settings."""
    row = _work(session, work_id)
    assembly.start_assembly(session, row)
    return works.detail(row)


@api.get("/works/{work_id}/audio/{part}")
def part_audio(work_id: int, part: str, session: Session = Depends(get_session)):
    """A part's assembled audio, as FLAC: "front", "back" or a chapter's index."""
    row = _work(session, work_id)
    if part in ("front", "back"):
        record = (row.matter_audio or {}).get(part)
    else:
        chapter = next((c for c in row.chapters if str(c.index) == part), None)
        record = chapter.audio if chapter else None
    path = assembly.audio_dir(work_id) / record["file"] if record else None
    if path is None or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/flac")


@api.get("/works/{work_id}/lines/{position}/audio")
def line_audio(work_id: int, position: int, session: Session = Depends(get_session)):
    """A line's current take, as FLAC."""
    line = session.scalar(select(Line).where(Line.work_id == work_id, Line.position == position))
    if line is None or not line.take:
        raise HTTPException(404)
    return FileResponse(voicing.lines_dir(work_id) / line.take["file"], media_type="audio/flac")


@api.get("/works/{work_id}/chapters/{index}")
def get_chapter(work_id: int, index: int, session: Session = Depends(get_session)) -> dict:
    row = session.scalar(select(Chapter).where(Chapter.work_id == work_id, Chapter.index == index))
    if row is None:
        raise HTTPException(
            404, detail={"key": "chapter.error.not_found", "params": {"index": index}}
        )
    lines = session.scalars(select(Line).where(Line.chapter_id == row.id).order_by(Line.position))
    return works.chapter_detail(row, list(lines))


@api.get("/works/{work_id}/matter/{part}")
def get_matter(work_id: int, part: str, session: Session = Depends(get_session)) -> dict:
    """The front or back matter: what comes before the first chapter and after the last."""
    row = _work(session, work_id)
    if part not in ("front", "back"):
        raise HTTPException(404)
    blocks = row.front_matter if part == "front" else row.back_matter
    lines = session.scalars(
        select(Line).where(Line.work_id == work_id, Line.part == part).order_by(Line.position)
    )
    return {
        "index": None,
        "title": None,
        "notes_before": [],
        "blocks": blocks,
        "notes_after": [],
        "lines": [line.to_dict() for line in lines],
    }


@api.get("/works/{work_id}/cover")
def get_cover(work_id: int, session: Session = Depends(get_session)) -> FileResponse:
    row = _work(session, work_id)
    if not row.cover_file:
        raise HTTPException(404)
    return FileResponse(works.work_dir(row.id) / row.cover_file)


@api.get("/languages")
def list_languages() -> list[dict]:
    """The languages a Work can be set to; those without a Language pack use the English one."""
    packs = get_packs()
    return [{"code": code, "has_pack": code in packs} for code in known_languages()]


@api.get("/voices")
def list_voices(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.scalars(select(Voice).order_by(Voice.language, Voice.id))
    return [voices.to_dict(row, get_packs()) for row in rows]


@api.get("/voices/{voice_id}/clip")
def voice_clip(voice_id: int, session: Session = Depends(get_session)) -> FileResponse:
    row = session.get(Voice, voice_id)
    if row is None:
        raise HTTPException(
            404, detail={"key": "voice.error.not_found", "params": {"id": voice_id}}
        )
    return FileResponse(voices.clip_path(row, get_packs()), media_type="audio/wav")


@api.get("/events")
async def stream_events(request: Request) -> StreamingResponse:
    """Server-sent events: every job update, as `event: job` with the job as JSON, and the
    First run's progress, as `event: models` with the same body as /api/system/models."""

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # A broken Language pack stops startup here, with a PackError naming the part.
    packs = get_packs()
    with get_sessionmaker()() as session:
        voices.sync_built_in_voices(session, packs)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Chorus", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan
    )
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
