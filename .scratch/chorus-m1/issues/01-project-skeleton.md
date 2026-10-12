# Project skeleton: web, worker, queues, database, catalogue

Type: task (AFK)
Status: ready-for-agent
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
