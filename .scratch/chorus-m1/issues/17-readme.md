# README: host setup, responsible use, credits

Type: task (AFK)
Status: ready-for-agent
Blocked by: 02

## What to build

The repository's README for someone installing Chorus.

- **What Chorus is,** in a few lines, in the glossary's terms.
- **Host prerequisites:** NVIDIA driver branch R580 (and why: the last with Pascal support); on Windows, WSL2 and Docker Desktop with the WSL2 backend, with no Linux NVIDIA driver inside WSL, BIOS virtualization turned on, and the GPU check `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi`; on Linux, Docker Engine and the NVIDIA Container Toolkit. Windows 10 support in Docker Desktop is ending.
- **Install and first run:** `docker compose up`, the model download, where exports appear on the host.
- **What to expect:** about 3.5 hours of analysis and about a day of voicing for a 100,000-word novel on a 1050 Ti; a desktop on the same card leaves little memory to spare.
- **Responsible use:** a few lines on the author's permission (including podfic permission for fanworks), the speaker's consent for cloned voices, and AO3's ban on commercial use.
- **Credits and licences:** Chorus is MIT; Kokoro (Apache-2.0) for the built-in Voice clips; Chatterbox (MIT); Qwen3.5-4B (Apache-2.0); llama.cpp; Calibre and ffmpeg run as separate programs (GPL).

## Acceptance criteria

- Someone following the README on a fresh Windows machine with a 1050 Ti reaches the Library.
- Every licence named matches `docs/spec/04-models-and-libraries.md`.

## Spec

`docs/spec/02-architecture.md` (Services: host prerequisites), `docs/spec/03-pipeline.md` (Permissions and disclosure), `docs/spec/04-models-and-libraries.md`.
