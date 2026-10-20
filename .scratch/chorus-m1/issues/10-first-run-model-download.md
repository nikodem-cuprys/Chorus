# First-run model download

Type: task (AFK)
Status: resolved
Blocked by: 01, 02

## What to build

On first start, Chorus downloads its models in pinned versions into the models volume, and shows progress in the browser.

- Models: Qwen3.5-4B GGUF Q4_K_M, and the Chatterbox 500M weights for `chatterbox-tts==0.1.7`. Each is pinned by repository and revision (or file hash), and the hash is checked after download.
- The First run screen: each model with its size and a progress bar; nothing else is reachable until both are in place.
- An interrupted download resumes; a failed hash is downloaded again.
- After the download, the GPU code never contacts the network (Hugging Face offline mode in the worker).

## Acceptance criteria

- On an empty models volume, the First run screen appears and the downloads complete; on the next start it is skipped.
- Killing the container mid-download and starting again resumes the download.
- With the network cut after first run, analysis and voicing still start.

## Spec

`docs/spec/02-architecture.md` (Services: first run), `docs/spec/06-screens.md` (First run).

## Answer

Built on 2026-10-20: `backend/chorus/firstrun.py`, `/api/system/models` with a `models` server-sent event, and `frontend/src/FirstRun.tsx`.

- **Pins:** Qwen3.5-4B Q4_K_M from `unsloth/Qwen3.5-4B-GGUF` at `e87f1764…` (the file every scoring run used), and the five files `ChatterboxTTS.from_pretrained` of 0.1.7 fetches from `ResembleAI/chatterbox` at `5bb1f6ee…`; 5.9 GB in all. Each file has a revision, a size and a SHA-256. No `huggingface_hub`: plain HTTP to the `/resolve/<revision>/` URLs (`models_url` setting, for tests).
- **When:** the worker runs the First run after the startup check and before its Celery workers, so no job starts without its model. The web service reads progress from the models volume and the downloader's state (checking, last error) from Redis.
- **Resume and hash:** each file goes to `<name>.part`, continued with a Range request after a kill; it is hashed and renamed into place only when the hash matches, so a file at its final name is always a checked one and a later start skips it. A wrong hash is downloaded again, up to 3 times; then, and after a network error, the screen shows the error and Chorus tries again every 30 seconds.
- **Screen:** each model with what it does, its size, a progress bar and its state (waiting, downloading, checking, done); nothing else is reachable until both are in place.
- **Offline:** the image sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. `firstrun.gguf_path()` (llama-server's `-m`) and `firstrun.chatterbox_dir()` (`ChatterboxTTS.from_local`) are where the engines must load from.

Acceptance:

- **Pins checked against Hugging Face:** the five LFS files' sizes and SHA-256 match the server's headers; `tokenizer.json` and `conds.pt` were downloaded through `firstrun` itself and passed their hashes, and a truncated `conds.pt.part` resumed through the real CDN.
- **Tests** (`tests/test_firstrun.py`, against a local stand-in for Hugging Face): an empty volume is downloaded and checked; the next start downloads nothing; a `.part` resumes with `Range: bytes=40000-`; a wrong hash is downloaded again; a hash that keeps failing and a network error are shown and tried again. `FirstRun.test.tsx` covers the screen. `tests/integration/test_stack.py` waits for the First run and checks both models are in place.

Not checked in Docker: Docker was not running, so the empty-volume start, the kill-and-resume in the container and the stack tests were not run.

Left for later:

- **Network cut after first run:** nothing loads a model yet. Tickets 11 and 13 must start llama-server with `gguf_path()` and load Chatterbox with `from_local(chatterbox_dir())`; the third acceptance criterion is checked there.

## Comments

- 2026-10-20, during ticket 11, in Docker: the model files were placed in the `models` volume as `.part` files (copied from ticket 24's volume), and the worker's First run hashed them, renamed them into place and started the queues, so resuming a `.part` works in the container. The third criterion passed there too: with the stack on a network with no route out, an analysis ran in full. Not run: a download from an empty volume, and killing the container mid-download.
