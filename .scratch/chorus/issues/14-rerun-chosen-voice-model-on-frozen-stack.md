# Re-run the chosen voice model on the frozen stack with a corrected memory measurement

Type: task (AFK)
Status: resolved
Blocked by: 07

## Question

The listening test ran on torch 2.8.0+cu126 (pinned in `../prototypes/voice-listening-test/overrides.txt`), not the frozen stack in the map's Notes (torch 2.14.0+cu126). Every model also peaked at about 3.9 GB on the card, above the 2.8 GB budget, and the harness recorded 0 MiB in use before loading, so the idle reading is broken and any spill into system memory went unmeasured. Fix the idle reading in the harness, then re-run only the model chosen in the listening test (and its fallback, if one is chosen) on the frozen stack. Record: whether it runs at all on the frozen stack, speed, true peak card memory, and whether it spills into system memory. Resolves with those facts and a statement of whether the map's 2.8 GB budget or frozen-stack note has to change.

## Answer

Chatterbox 500M runs on the frozen stack, but not inside the 2.8 GB budget: it spills about 1 GB into system memory. The frozen-stack note stands; the budget note has to change. No fallback was chosen in ticket 07, so only Chatterbox 500M was re-run (2026-10-01, same 8 lines, FP32).

| | torch 2.8.0+cu126 (listening test) | torch 2.14.0+cu126 (this run) |
|---|---|---|
| Runs | yes | yes, no errors, all 8 clips written |
| Speed (x real time) | 13.7 (4.6 to 26.6 per line) | 8.8 (6.0 to 11.5 per line) |
| torch peak allocated / reserved | 3700 / 4354 MiB | 3700 / 4222 MiB |
| Card in use before loading | not measured (read 0) | 504 MiB |
| Card peak (nvidia-smi) | 3970 MiB | 3919 MiB |
| Process peak on the card | not measured | 3386 MiB |
| Process peak in system memory (spill) | not measured | 978 MiB |

- **Frozen stack:** works with torch 2.14.0+cu126 and torchaudio 2.11.0+cu126; every other package pinned to the listening-test versions (`chatterbox-tts==0.1.7`). The wheel includes `sm_61` kernels.
- **Memory:** the model needs about 3.7 GB allocated (3.1 GB right after loading). With a desktop holding 0.5 GB of the card, about 3.4 GB sat on the card and about 1 GB went to Windows shared GPU memory. So it does not fit in 2.8 GB, and with a desktop on the card it does not fit in the remaining 3.6 GB either. An empty 4 GB card would be a tight fit (3.7 GB allocated, 4.2 GB reserved); not tested.
- **Speed:** one run per stack with random sampling, so the difference between 13.7 and 8.8 is not evidence that 2.14 is faster. Read both as "roughly 9 to 14 times slower than real time while spilling".
- **Harness fix:** the idle reading is now taken before loading, and Windows GPU counters record dedicated and shared memory for the card and for the process (`harness.py`).

Not covered:
- Ran on native Windows with Python 3.11 and driver 582.28, not in Docker/WSL2 with Python 3.12 and driver branch R580 as the map pins.
- The spill relies on the Windows driver's system-memory fallback. On native Linux there is no such fallback, so the same load would likely fail with out-of-memory; not tested.
- The new clips were not compared by ear with the listening-test clips.
- Ways to cut memory (half-precision weights with FP32 compute, loading the two halves of the model one at a time) were not tried.

Files: `../prototypes/voice-listening-test/out/chatterbox-500m-frozen/` (clips, `metrics.json`), `frozen-run.log`, `overrides-frozen.txt`, `constraints-frozen.txt`. The environment lives outside the repo at `C:\Users\nikod\AppData\Local\chorus-frozen` (D: was nearly full).
