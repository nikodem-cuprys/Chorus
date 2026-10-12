# The Chorus image on the frozen GPU stack

Type: task (AFK, needs the GTX 1050 Ti machine with Docker Desktop on WSL2)
Status: resolved
Blocked by: 01

## What to build

The single Chorus image that `web` and `worker` run, with GPU access for `worker`.

- Base `nvidia/cuda:12.6.3-base-ubuntu24.04`, pinned by digest. Python 3.12.
- `torch==2.14.0+cu126` and `torchaudio==2.11.0+cu126` from the cu126 index; `chatterbox-tts==0.1.7` with the rest of its pins from `.scratch/chorus/prototypes/voice-listening-test/constraints-frozen.txt` and `overrides-frozen.txt`.
- llama.cpp's server at build b11318, built in a separate stage from llama.cpp's `.devops/cuda.Dockerfile` with `CUDA_VERSION=12.6.3 GCC_VERSION=13 CUDA_DOCKER_ARCH=61`. The working setups are in `.scratch/chorus/prototypes/llama-server-container/` and `.scratch/chorus/prototypes/chatterbox-fit/Dockerfile`.
- ffmpeg and Calibre (`ebook-convert`, running headless).
- `TORCH_DISABLE_NATIVE_JIT=1`.
- A startup health check: a CUDA matrix multiply through torch (a wrong wheel fails with "no kernel image is available"), `llama-server --version`, and `ebook-convert --version`. A failure shows a clear message in the browser instead of the app.
- Compose gives `worker` the GPU.

## Acceptance criteria

- The image builds from a clean checkout; its size is recorded in this ticket.
- On the 1050 Ti the health check passes; with a deliberately wrong torch wheel it fails with a readable message.
- `ebook-convert` converts the AZW3 fixture in `.scratch/chorus/samples/` to EPUB inside the container with no display.
- The `base` flavour is confirmed to be enough (no missing CUDA or cuDNN library at runtime); if not, what was needed is noted here and in `docs/spec/04-models-and-libraries.md`.

## Spec

`docs/spec/02-architecture.md` (Services, GPU turn-taking), `docs/spec/04-models-and-libraries.md` (Pinned GPU stack, Import libraries).

## Answer

Built and checked on 2026-10-12 on the GTX 1050 Ti (Docker Desktop on WSL2, Windows 10, driver 582.28).

- **Image:** `Dockerfile` with four stages: the frontend; llama.cpp's source at b11318 with the web UI its server embeds; `llama-server` built on `nvidia/cuda:12.6.3-devel-ubuntu24.04` with llama.cpp's own cmake options and `CMAKE_CUDA_ARCHITECTURES=61` (Ubuntu 24.04's gcc 13, so no `GCC_VERSION` override is needed); and the Chorus image on `nvidia/cuda:12.6.3-base-ubuntu24.04`. All four base images are pinned by digest. Python 3.12 is Ubuntu's own, in `/opt/venv`, installed with uv; Calibre 7.6.0 and ffmpeg 6.1.1 come from Ubuntu.
- **Python packages:** `docker/requirements-gpu.txt` (torch 2.14.0+cu126, torchaudio 2.11.0+cu126 and Chatterbox's library dependencies at the frozen versions) and `docker/constraints-gpu.txt` (the frozen constraints of tickets 14 and 25, without the web packages the app pins itself). `chatterbox-tts==0.1.7` is installed with `--no-deps`: it pins torch 2.6 and requires `gradio` for a demo that the library never imports.
- **llama-server** runs through `docker/llama-server.sh`, which puts the torch wheel's CUDA runtime, cuBLAS and NCCL on the library path. Without NCCL, `libggml-cuda.so` does not load and llama.cpp falls back to the CPU without an error; this happened on the first build.
- **Startup check:** `chorus/healthcheck.py`, run by the worker in its own process before Celery starts, so its CUDA context is gone afterwards (checked: the card's memory is the same with the worker running or stopped). It runs a matrix multiply through torch, `llama-server --list-devices` (which must list a CUDA device), `ebook-convert --version` and `ffmpeg -version`. The result is stored in Redis and served at `/api/system/health`; the interface shows a problem page with catalogue messages and the technical detail when a check fails.
- **Compose:** the worker reserves the GPU; web does not.

Acceptance, checked:

- **Builds from a clean checkout:** yes. **Image size: 13.6 GB** as Docker reports it; the Python environment layer is 7.4 GB (torch and its CUDA libraries), the Ubuntu packages (Calibre, ffmpeg, Python) 1.2 GB, llama.cpp 152 MB. The first build took about 1 h 40 min, nearly all of it downloads on a slow connection (cuDNN restarted five times).
- **Health check on the 1050 Ti:** all four pass: `torch 2.14.0+cu126, CUDA 12.6, NVIDIA GeForce GTX 1050 Ti, sm_61`; `CUDA0: NVIDIA GeForce GTX 1050 Ti (4095 MiB, 3357 MiB free)`; `calibre 7.6.0`; `ffmpeg 6.1.1`. The integration test `test_the_startup_check_passes_on_this_machine` and ticket 01's stack tests pass against the running stack.
- **Wrong torch wheel:** with torch 2.14.0+cpu in a side environment the check fails with `health.torch.wrong_build` ("The Chorus image has the wrong PyTorch build (2.14.0+cpu, for CUDA none)…"), stored and served by the API. A cu128 wheel, which would take the "no kernel image" path instead, was not downloaded (several GB on this connection); that path is covered by a unit test of its message.
- **`ebook-convert`** turns `alice-gutenberg.azw3` into an EPUB inside the container with no display (31 files, `content.opf`).
- **`base` flavour is enough:** Chatterbox 500M loads (42 s) and voices a line with the `af_bella` clip in the image (3.1 s of audio in 33 s including warm-up, 3,489 MiB peak allocated by the unchanged model); cuDNN 9.10.2 comes from the wheel. Recorded in `docs/spec/04-models-and-libraries.md`.

Not done: mirroring the base images to a registry of our own (the spec's note is now "pinned by digest; mirroring is not set up"). The llama.cpp build reports itself as `0.5.0-dev (build 1, commit db33d3c)` because it is cloned without history; the tag b11318 is in the Dockerfile.
