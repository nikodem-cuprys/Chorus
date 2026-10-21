# README: host setup, responsible use, credits

Type: task (AFK)
Status: resolved
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

## Answer

Written on 2026-10-21: `README.md` at the repository root, and a `LICENSE` file (MIT, as `pyproject.toml` and the spec already said; there was none).

- **Sections:** what Chorus is (in the glossary's terms: Source, Work, Character, Speaker, Voice, Emotion, Audio drama); what to expect on a 1050 Ti (3.5 h of analysis and about a day of voicing for 100,000 words, chapters playable as they are voiced, pause and resume, the card's tight memory beside a desktop); host setup (driver branch R580 and why, Windows steps with BIOS virtualization, WSL2 without a Linux driver inside, Docker Desktop's WSL2 engine and the GPU check, Linux steps with Docker Engine and the NVIDIA Container Toolkit, Windows 10's end of support); install and first run (`docker compose up -d --build`, the 6 GB model download on the First run screen, the antivirus certificate note, where exports, volumes and the port are, stopping and updating); responsible use; credits and licences.
- **Figures come from the spec:** 3.5 h is one analysis pass (the second labelling run arrives in milestone 3); about 2× real time for voicing; 3.3 GB and 3.1 GB added on the card at peak (`04-models-and-libraries.md`, Measurements); the image about 14 GB and the models 5.9 GB (`docs/development.md`).
- **Licences** match `04-models-and-libraries.md` for every component named: Chatterbox MIT, Kokoro-82M Apache-2.0, Qwen3.5-4B Apache-2.0, Calibre GPL-3.0 and ffmpeg GPL as separate programs, lxml and pypdf BSD-3-Clause, pdfplumber and charset-normalizer MIT, lingua-py Apache-2.0. llama.cpp's licence (MIT) was missing from the spec and is now in its Runtime row. httpx is left out: it is for AO3 by URL (milestone 2) and not yet installed.

Acceptance:

- **The GPU check** in the README runs on this machine: `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi` printed the GTX 1050 Ti, driver 582.28, 4096 MiB. The install commands are the ones every ticket since 02 used, and they reach the Library here.
- **Not tried on a fresh machine:** this machine already had the driver, WSL2 and Docker Desktop. Ticket 18, or the first install elsewhere, should follow the README from the start and note anything missing.
