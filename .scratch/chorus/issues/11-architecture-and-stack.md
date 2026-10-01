# Architecture and tech stack, including GPU sharing between the language and voice models

Type: grilling
Status: resolved
Blocked by: 04, 07, 08, 12, 14

## Question

What is Chorus's architecture and tech stack? Decide: the backend and frontend stack; how the pipeline stages run as resumable background jobs; how the analysis model and the voice model take turns on a single 4 GB GPU (the load and unload strategy); how the Work, Script, Voices and generated audio are stored; how the YouTube integration fits in; and the Docker packaging. Also decide Chorus's own license, which determines whether AGPL/GPL libraries can be imported in-process or must run as separate processes (see `../research/source-import-libraries.md`). All of it must stay within the constraints in the map's Notes.

## Answer

Decided by the user on 2026-10-01 in a grilling session.

- **License:** MIT. AGPL libraries (EbookLib, PyMuPDF) stay out; Calibre runs as a separate process, as ticket 03 decided.
- **Stack:** Python backend on FastAPI with a JSON API; React + TypeScript frontend built with Vite and served by the backend.
- **Storage:** PostgreSQL for Works, the Script (lines, Characters with aliases, Scenes), Voices and jobs. Audio is one FLAC file per line on a data volume; chapter audio for the player and MP3/M4B exports are assembled from the lines with ffmpeg and cached. A corrected line replaces its file and the chapter is re-assembled.
- **Jobs:** Celery on Redis, two queues. The GPU queue has one slot for analysis and voice generation; the other queue takes import, assembly, export and YouTube upload, so those run while audio is being generated. Every finished chunk or line is saved, so a job continues where it stopped after a crash or reboot.
- **GPU turn-taking:** each GPU stage runs as its own child process that exits when done, which guarantees the card's memory is free: analyse the whole Work, then voice it. A corrected line starts a short voice-only process.
- **Analysis model:** llama.cpp's server is started at the beginning of the analysis stage and stopped at the end, so the model loads once. To verify: that it does not hang inside the Linux container, as build b11318 did on Windows in ticket 08. Fallback: the Python binding (llama-cpp-python).
- **Voice memory:** the architecture assumes Chatterbox 500M can be made to fit. To measure in Docker: half-precision weights with FP32 compute, and loading the model's two halves one at a time. If neither works, this decision is reopened.
- **Engines:** the analysis model and the voice model sit behind interfaces, with one implementation each for now (Qwen3.5-4B through llama.cpp; Chatterbox 500M).
- **Docker:** Compose with four services: web, worker, Redis, PostgreSQL. Web and worker run the same Chorus image (Python, CUDA, PyTorch, llama.cpp, ffmpeg, Calibre, the built frontend). Models are not in the image; pinned versions are downloaded on first run into a models volume, with progress shown.
- **Access:** no login, port published on localhost only by default. Opening it to the network requires setting a single password.
- **Progress:** server-sent events.
- **YouTube:** one plain backend module (YouTube export first; the connect wizard and direct upload in the final milestone). Uploads run on the non-GPU queue; Google tokens are stored encrypted in the database. No general Publishing plug-in interface.

Set by Claude as conventional defaults, not asked: SQLAlchemy with Alembic migrations; one repository with `backend/` and `frontend/` folders.

Options the user turned down: an own job queue in SQLite with one worker, SQLite for storage (both Claude's recommendations), and separate tickets for the two open checks (they are noted in the map instead).
