# Check that the llama.cpp server does not hang in the Linux container

Type: task (AFK)
Status: resolved
Blocked by: none

## Question

Ticket 11 starts llama.cpp's server once for the whole analysis stage, but build b11318 hung after one or two requests on Windows (ticket 08). Build llama.cpp for `sm_61` in a Linux container on the frozen stack (CUDA 12.x, driver R580, see the map's Notes), load Qwen3.5-4B with an 8k context on the 1050 Ti, and run the full approach B analysis of the six sample passages through the server (several hundred requests, including the blind second labelling run from ticket 18). Record: whether it hangs, speed against the Windows runs of ticket 08, and peak card memory. If it hangs, repeat with the Python binding (llama-cpp-python) and record the same. Resolves with those facts and a statement of which of the two the analysis stage uses.

## Answer

The llama.cpp server does not hang in the Linux container, so the analysis stage uses the server as ticket 11 planned. The Python binding was not needed and was not tried.

Measured 2026-10-07: llama.cpp b11318 (the build that hung on Windows) built from source for `sm_61` on `nvidia/cuda:12.6.3`, in Docker Desktop on WSL2 (Windows 10, driver 582.28), Qwen3.5-4B Q4_K_M, all layers on the card, 8k context, one slot, thinking off, temperature 0. One server process answered everything: approach B and the blind second labelling run of ticket 18 on the six passages (58 requests), repeated four times.

| | Container, server | Windows, ticket 08 and 18 (one process per call) |
|---|---|---|
| Requests | 232, all answered, none cut short, server never restarted | 58 |
| Hangs | none in 2 h 27 min | server hung after one or two requests |
| Generation speed | 18.0 tokens/s | about 19 tokens/s |
| Approach B, six passages | 1215 to 1279 s | 1343 s |
| Second labelling run | 881 to 892 s | 923 s |
| Card in use before loading | 572 MiB | not measured |
| Card peak | 3902 MiB (3330 MiB added) | not measured; llama.cpp projected about 3.0 GB |
| Spill into system memory | none | not measured |
| Speakers right against ticket 08's reference | 259 of 288 | 267 of 288 |

- **Speed:** tokens come out slightly slower than on Windows, but a whole pass is 5 to 10% faster because the model loads once instead of once per call. Times are from rounds 2 to 4; round 1 (1516 s and 953 s) overlapped with a large file deletion on the machine. The longest single request took 208 s.
- **Memory:** right after loading the server holds 3038 MiB; the peak during requests is 3330 MiB above idle. That is over the 2.8 GB budget in the map's Notes. It fitted on the 4 GB card with about 190 MiB to spare while the desktop held 572 MiB; a busier desktop would push it into system memory under WSL2 or fail on Linux. Windows reported 123 to 192 MiB of shared memory for the card throughout, about what ticket 25 saw for runs that fit.
- **Speakers changed:** same prompts, same model file and temperature 0, yet the container run names 259 of 288 Speakers right against 267 on Windows. The difference is in the Character lists: in Jane Eyre the container run lists "I" and "Jane" as two Characters (20 of 29 right against 26), in Holmes 32 of 40 against 39, while Metamorphosis improves (17 of 18 against 11). Round 1 also differs slightly from rounds 2 to 4, which agree with each other. So the result is not reproducible across builds, and one run's score is not a stable measure of approach B. Not investigated further here.
- **Build:** CUDA 12.6.3's compiler rejects gcc 14, which llama.cpp's `cuda.Dockerfile` uses by default (it defaults to CUDA 12.8.1). The image builds with `CUDA_VERSION=12.6.3 GCC_VERSION=13 CUDA_DOCKER_ARCH=61`. The server must be started with one slot (`-np 1`), or the 8k context is divided between slots.
- **Requests per pass:** one pass over the six passages is 58 requests (37 for approach B including the Scene call that ticket 26 later dropped, 21 for the second run), not several hundred; four passes give 232.

Not covered:
- A Linux host, and a card with no desktop on it.
- llama-cpp-python, since the server did not hang.
- Why the Speakers differ from the Windows run, and whether a newer llama.cpp build behaves the same.
- The client ran on Windows and reached the server through the published port, not from a second container.

Files: `../prototypes/llama-server-container/` (`run.py`, `requests.jsonl` with every request, `mem.csv` with the card sampled every two seconds, `run.log.txt`, `server-start.txt`, `scripts/` and `rerun/` from round 1, `score.py`, `score.json`). Image `chorus-llama:b11318-cuda12.6.3-sm61`; the model is in the Docker volume `chorus-models`.

## Comments

- 2026-10-03, not started: this machine cannot run a Linux container yet. Checked: Docker is not installed, WSL is not installed (only the `wsl.exe` stub that prints install help), and `systeminfo` reports "Virtualization Enabled In Firmware: No". The card and driver are fine (GTX 1050 Ti, driver 582.28). Needed from the user before this ticket can run: turn on SVM in the BIOS (AMD Ryzen 5 5600X), run `wsl --install` as administrator and reboot, then install Docker Desktop with the WSL2 backend and confirm `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi` shows the card. Windows 10 build 19045; ticket 05 notes Docker Desktop's Windows 10 support is ending. Left open and unclaimed; ticket 25 waits on the same thing.
