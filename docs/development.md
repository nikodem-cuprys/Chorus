# Development

## Run the stack

```sh
docker compose up -d --build              # http://localhost:8000
CHORUS_DEV=true docker compose up -d      # also enables /api/dev (dummy jobs)
docker compose down                       # stop; volumes are kept
```

The first build takes a long time: it compiles llama.cpp for the GTX 1050 Ti and downloads about 7 GB of PyTorch and CUDA libraries (the image is about 13.6 GB). Later builds reuse those layers.

The worker checks the GPU stack when it starts (torch on the card, llama-server seeing the card, Calibre, ffmpeg) and the interface shows what failed. To run the check by hand: `docker compose exec worker python -m chorus.healthcheck`.

If the build fails with "certificate verify failed" or "invalid peer certificate", the host's HTTPS traffic is being re-signed by antivirus or a proxy: see [`certs/README.md`](../certs/README.md).

## Tests

```sh
# backend, without Docker (SQLite, Celery in-process)
cd backend
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # .venv/bin on Linux
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .

# backend, against the running stack (started with CHORUS_DEV=true)
CHORUS_STACK_URL=http://localhost:8000 .venv/Scripts/python -m pytest tests/integration

# frontend
cd frontend
npm ci
npm test
npm run build
```

## Conventions

- **Interface text** lives only in the message catalogue (`frontend/src/i18n/en.json`). The backend never sends display text: errors and job messages are `{"key": ..., "params": {...}}`, which the frontend turns into words with `tMessage`. A frontend test fails on text written straight into JSX.
- **Jobs** are registered with `@job(kind, queue)` in `backend/chorus/jobs.py` and imported in `backend/chorus/tasks.py`. A job reports progress with `ctx.report(...)`, which saves it and sends it to the browser over SSE. The `gpu` queue runs one job at a time; never raise its concurrency.
- **Database changes** go through an Alembic migration in `backend/migrations/versions/`; a test checks that the migrations and the models agree.
- **Language packs** are folders under `backend/chorus/languages/` (`pack.json` plus the files it names); `chorus.languages` loads and checks them at startup and fails naming the broken part. Built-in Voices are copied into the `voice` table from the packs at every startup; change them in the pack, never in the database.
