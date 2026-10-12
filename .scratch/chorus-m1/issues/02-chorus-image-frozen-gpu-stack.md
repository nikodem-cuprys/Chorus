# The Chorus image on the frozen GPU stack

Type: task (AFK, needs the GTX 1050 Ti machine with Docker Desktop on WSL2)
Status: ready-for-agent
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
