# First-run model download

Type: task (AFK)
Status: ready-for-agent
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
