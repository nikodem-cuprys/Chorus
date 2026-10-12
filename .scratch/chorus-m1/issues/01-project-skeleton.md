# Project skeleton: web, worker, queues, database, catalogue

Type: task (AFK)
Status: resolved
Blocked by: none

## What to build

The empty app that every later ticket builds into, running under Docker Compose (without the GPU yet).

- One repository with `backend/` (Python 3.12, FastAPI, JSON API, SQLAlchemy, Alembic) and `frontend/` (React, TypeScript, Vite; the built frontend is served by the backend).
- Docker Compose with four services: `web`, `worker`, `redis`, `postgres`. `web` and `worker` run the same image. Volumes for data, models and postgres, and a host folder bind-mounted for exports.
- Celery on Redis with two queues: `gpu` with one slot, and `other` with several.
- A job record (Work or none, kind, queue, state, progress) and a server-sent events endpoint the frontend subscribes to for job progress.
- The interface's message catalogue from the first screen: every string goes through it, English only. A placeholder Library page proves the wiring.
- The port is published on localhost only. No login.
- Backend tests with `pytest`, frontend tests with the frontend's test runner, both runnable with one command each.

## Acceptance criteria

- `docker compose up` starts the four services; the browser at `http://localhost:<port>` shows the Library placeholder.
- A dummy job on each queue runs, and its progress reaches the browser over SSE.
- Two dummy jobs on `gpu` never run at the same time.
- No interface string is hard-coded outside the catalogue (a test or lint rule checks it).
- The port is not reachable from another machine by default.

## Spec

`docs/spec/02-architecture.md` (Stack, Services, Jobs, Access, Interface language).

## Answer

Built on 2026-10-12. How to run and test it: `docs/development.md`.

- **Layout:** `backend/` (package `chorus`: `app.py` API and SSE, `jobs.py` job machinery, `worker.py` worker entry point, `models.py`, `db.py`, `config.py`, `events.py`, `dev_jobs.py`; Alembic in `migrations/`) and `frontend/` (React 19, Vite 8, TypeScript 5.9; catalogue in `src/i18n/`). `Dockerfile` and `compose.yaml` at the root.
- **Jobs:** a job is a `job` row plus a Celery task registered with `@job(kind, queue)`; `ctx.report(...)` saves progress and publishes it on a Redis channel that `/api/events` streams as server-sent events. The `worker` service runs one Celery worker per queue: `gpu` with concurrency 1, `other` with 4. Tasks are acknowledged late and requeued if a worker dies, ready for resume in ticket 15.
- **Messages:** the backend sends catalogue keys with parameters, never display text; the frontend's `t`/`tMessage` turn them into words.
- **Pins:** FastAPI 0.143.0, SQLAlchemy 2.1.4, Alembic 1.20.0, Celery 5.6.3 with redis 6.4.0 (the newest kombu 5.6 allows; 8.x conflicts), psycopg 3.3.6; `httpx2` for Starlette's test client. TypeScript 5.9.3 rather than 7.0, whose compiler API is still marked unstable and is used by the catalogue test. Images `python:3.12-slim-bookworm`, `node:24-slim`, `redis:7.4-alpine`, `postgres:17`, uv 0.13.0. Pinning base images by digest is ticket 02.

Acceptance, checked:

- `docker compose up` starts all four services; web, Redis and PostgreSQL report healthy, and `/` serves the built frontend with its assets.
- `tests/integration/test_stack.py` against the running stack: two GPU jobs and one other job all report progress up to 100% over SSE, the GPU jobs ran one after the other, and the other job ran alongside them. Passed.
- The catalogue test parses every `.tsx` file and fails on JSX text, text attributes and string-literal children; it passes, and a self-test shows it catches each kind.
- The port is bound to `127.0.0.1` (checked from `docker compose config` in a test) and did not answer on any of the machine's four other addresses.
- Backend: 10 unit tests (SQLite, Celery eager) and ruff pass; frontend: 7 tests and `tsc` pass.

Not checked: the page in a real browser, since the Chrome extension was not connected. The page's job list is covered by component tests, and the SSE stream and served assets were checked with curl.

Found on the way: Norton's HTTPS scanning re-signs traffic inside Docker builds too, so pip, uv and npm failed with certificate errors. The image now trusts any `*.crt` placed in `certs/` (gitignored; how to export one is in `certs/README.md`). This machine's Norton root is there. Ticket 02's GPU image needs the same `certs/` step, and so will model downloads at first run (ticket 10).
