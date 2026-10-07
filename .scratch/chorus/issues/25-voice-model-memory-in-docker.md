# Fit Chatterbox 500M on a shared 1050 Ti in Docker

Type: task (AFK)
Status: resolved
Blocked by: none

## Question

Chatterbox 500M needs about 3.7 GB and ran on a shared 1050 Ti only by spilling about 1 GB into Windows shared memory (ticket 14). Ticket 11 assumes it can be cut to fit. In Docker on WSL2, on the frozen stack, measure the two ideas from ticket 11 on the eight lines of ticket 14: weights stored in half precision with FP32 compute, and loading the model's two halves one at a time. For each, and for both together, record: whether it runs, peak card memory, any spill into system memory, speed, and whether the audio is the same by ear as the ticket 14 clips for the same seed. Also record what happens in the container with no change: does the spill still work under WSL2, and what would happen on Linux, which has no such fallback. Resolves with those facts and one of: the setting Chorus uses, or a statement that neither works, which reopens the voice memory decision of ticket 11 (accept the spill, or require a card with no desktop on it).

## Answer

Chorus loads the model's two halves one at a time. That fits the 2.8 GB budget with no spill, is the fastest setting measured, and gives the same audio as the unchanged model. Half-precision weights are not needed; together with the split they are a fallback for a smaller budget (about 1.5 GB) at nearly twice the time. The voice memory decision of ticket 11 stays closed.

Measured 2026-10-07 in Docker Desktop on WSL2 (Windows 10, driver 582.28), Python 3.12, torch 2.14.0+cu126, `chatterbox-tts==0.1.7`, FP32 compute, the eight lines of ticket 14 (56 s of audio), one seed for every setting, desktop on the card.

| | No change | Half-precision weights | Two halves in turn | Both |
|---|---|---|---|---|
| Runs | yes | yes | yes | yes |
| torch peak allocated / reserved | 3700 / 4336 MiB | 2262 / 2874 MiB | 2227 / 2392 MiB | 1241 / 1414 MiB |
| Card in use before loading | 500 MiB | 316 MiB | 417 MiB | 417 MiB |
| Card peak | 3969 MiB | 3272 MiB | 2873 MiB | 1909 MiB |
| Added on the card | 3469 MiB | 2956 MiB | 2456 MiB | 1492 MiB |
| Spill into system memory | 862 MiB | none | none | none |
| Speed (x real time) | 3.0 | 3.6 | 2.2 | 4.1 |
| Audio against "no change" | - | same speech tokens; waveform differs by -45 to -35 dB, line 06 by -14 dB | same speech tokens; waveform differs by less than -75 dB | as half-precision weights |

- **No change in the container:** it runs, and the spill still works under WSL2: 862 MiB went to Windows shared memory, as on native Windows in ticket 14 (978 MiB).
- **Linux:** not run on a Linux host. With torch told to hold no more than what was free on the card (3735 MiB), the unchanged model voiced line 01 and failed on line 02 with `CUDA out of memory` at 3653 MiB allocated. That is what a card with no system-memory fallback would do with a desktop on it. An empty 4 GB card was not tested; the model reserved 4336 MiB when it was allowed to.
- **Two halves in turn:** T3 (text to speech tokens) runs for all lines, leaves the card, then S3Gen (tokens to audio) runs for all lines. Peaks: 2227 MiB while T3 is loaded, 1309 MiB while S3Gen is. S3Gen's part of the reference-clip preparation runs on the CPU during the first pass. Swapping took about 1 s. The stage therefore voices in batches (for example a chapter), not line by line; re-voicing one line pays the swap each time.
- **Half-precision weights:** every weight matrix is stored in half precision and turned into FP32 as its layer runs. It saves about 1.5 GB but T3 becomes about twice as slow per line (the weights are converted at every token step), so on its own it is slower than no change and still adds 2956 MiB.
- **Speed:** the unchanged model is slower than the split because its S3Gen pass ran while spilling (4.7 to 11.4 s per line against 2.9 to 4.9 s). All container runs are far faster than ticket 14's 8.8 on Windows; that was one unseeded run on another stack, so it is not a like-for-like comparison.
- **Spill reading:** Windows reports 35 to 56 MiB of shared memory for the card when idle and about 105 MiB during every run that fits, so "none" means no more than that.
- **Found on the way:** on Linux, torch 2.14 sends some operations to triton kernels that need a C compiler when they first run; the first run failed with "Failed to find C compiler". `TORCH_DISABLE_NATIVE_JIT=1` switches that off and gives the Windows code path. The Chorus image needs that setting or a compiler. The cu126 wheel lists `sm_60`, not `sm_61`, and runs on the card as ticket 05 expected.

Not covered:
- By ear: nobody has listened. The ticket 14 clips had no fixed seed, so no new clip can be the same take as them; the settings are compared with each other instead. `listen.html` puts the ticket 14 clip and the four settings side by side; line 06 under half-precision weights is the one to check.
- A Linux host, and an empty card.
- The base image is `nvidia/cuda:12.6.3-base-ubuntu24.04`, not the `cudnn-runtime` flavour ticket 05 names; the torch wheel brings its own CUDA and cuDNN libraries.
- One run per setting (the two split settings were run twice; the second run is reported, because the first overlapped with a compile and had a bug that left T3 on the card).

Files: `../prototypes/chatterbox-fit/` (`Dockerfile`, `fit.py` runs one setting in the container, `run_all.py` starts the containers and samples the card from Windows, `compare.py`, `listen.html`, `out/summary.json`, `out/compare.json`, per-setting `metrics.json` and `host_mem.csv`). Weights are in the Docker volume `chorus-models`.

## Comments

- 2026-10-03: waits on the same machine setup as ticket 24 (virtualization off in the BIOS, no WSL2, no Docker). See the comment there.
