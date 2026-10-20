# Models and libraries

Everything here was confirmed to run on a GTX 1050 Ti unless marked otherwise. Every choice allows commercial use.

## Pinned GPU stack

Pascal support ends with CUDA 12.x, driver branch R580 and PyTorch 2.14, so this stack is frozen for as long as the 1050 Ti is the minimum.

| Layer | Pin |
|---|---|
| Host driver | NVIDIA branch R580 (Windows: 582.28 measured; Linux: 580.x). Never R590 or later. |
| Base image | `nvidia/cuda:12.6.3-base-ubuntu24.04`, pinned by digest (old CUDA tags are deleted from Docker Hub six months after end of life; mirroring them is not set up). The `base` flavour is enough: the torch wheel brings its own CUDA runtime, cuBLAS, cuDNN (9.10) and NCCL, and Chatterbox voices a line in the image (M1 ticket 02). |
| llama.cpp build stage | b11318, built in the image's Dockerfile with the cmake options of llama.cpp's own `.devops/cuda.Dockerfile` (`GGML_CUDA`, `GGML_BACKEND_DL`, `GGML_CPU_ALL_VARIANTS`) and `CMAKE_CUDA_ARCHITECTURES=61`, on `nvidia/cuda:12.6.3-devel-ubuntu24.04` with Ubuntu 24.04's gcc 13 (CUDA 12.6.3's compiler rejects gcc 14). Never a `*-cuda13` image. At run time `llama-server` loads the CUDA runtime, cuBLAS and NCCL from the torch wheel; without NCCL its CUDA backend does not load and it runs on the CPU without saying so, which the startup check catches. |
| Python | 3.12 (Ubuntu 24.04's own), in a virtual environment installed with uv |
| Chatterbox | `chatterbox-tts==0.1.7` installed without its dependencies, which pin torch 2.6 and pull in `gradio` for a demo the library never imports; its library dependencies are listed at the frozen versions in `docker/requirements-gpu.txt` |
| PyTorch | `torch==2.14.0+cu126` from `https://download.pytorch.org/whl/cu126`. A plain `pip install torch` gives a CUDA 13 wheel that cannot run on Pascal. |
| torchaudio | `torchaudio==2.11.0+cu126` |
| Environment | `TORCH_DISABLE_NATIVE_JIT=1` |

**GPU-ineligible:** anything that needs torch 2.15 or later, CUDA 13, vLLM, FlashAttention-2, bf16 or tensor cores. Such things can only run on the CPU.

## Analysis model

| | |
|---|---|
| Model | Qwen3.5-4B, GGUF Q4_K_M (2.74 GB file) |
| Weights | `unsloth/Qwen3.5-4B-GGUF` at revision `e87f1764`, `Qwen3.5-4B-Q4_K_M.gguf`, SHA-256 `00fe7986…`: the file every scoring run used. Downloaded on first run (`backend/chorus/firstrun.py` holds the full pins). |
| Licence | Apache-2.0 |
| Runtime | llama.cpp server, pinned to build b11318 (the build measured in the container), all layers on the card. Moving to another build means scoring the sample passages again. |
| Settings | 8k context, one slot (`-np 1`; more slots divide the context), thinking off, temperature 0, JSON-schema constrained output |
| Approach | B: LLM-only chunked attribution with a global Character and alias list, plus a blind second labelling run (see [03-pipeline.md](03-pipeline.md#analysis)) |

**Not chosen:** BookNLP plus an LLM (approach A) scored 259 of 288 against B's 267 on Windows, is English-only, and was dropped. Asking the model to rate its own labels does not work (279 of 288 rated "sure"). A go_emotions baseline and a run with thinking on were never tried.

**Not reproducible across builds:** the same prompts, model file and temperature gave 267 of 288 Speakers right on Windows and 259 in the container; the difference is in the Character lists. Changing the llama.cpp build means scoring the sample passages again.

## Voice model

| | |
|---|---|
| Model | Chatterbox 500M, `chatterbox-tts==0.1.7` |
| Weights | `ResembleAI/chatterbox` at revision `5bb1f6ee`: the five files `from_pretrained` fetches (`ve`, `t3_cfg`, `s3gen` safetensors, `tokenizer.json`, `conds.pt`; 3.19 GB), each checked by SHA-256. Downloaded on first run and loaded with `from_local`; the image sets `HF_HUB_OFFLINE=1`. |
| Licence | MIT |
| Compute | FP32, with the model's two halves (T3, then S3Gen) loaded one at a time |
| Emotion control | `exaggeration` and `cfg_weight` per Emotion and intensity, never `exaggeration` above 0.9 |
| Cloning | zero-shot from a reference clip; the built-in Voices are clones of generated Kokoro clips |
| Seed | fixed per line; the same seed reproduces the same take |

**Fallback, not in use:** half-precision weights (turned into FP32 as each layer runs) together with the split cut the card's extra memory to about 1.5 GB at 4.1 times real time. It is there if the budget shrinks.

**Ranked lower by ear:** IndexTTS-2 (second; Emotions too aggressive; 65 times real time; bilibili licence allows commercial use below 100M monthly users), Chatterbox-Turbo (no audible Emotion), Qwen3-TTS 0.6B (worst). **Excluded as non-commercial:** F5-TTS, XTTS-v2, Fish Speech.

## Emotion settings for Chatterbox 500M

Each value is `exaggeration` / `cfg_weight`. Shipped as `emotions.json` beside the voice model.

| Emotion | Normal | Strong |
|---|---|---|
| neutral | 0.5 / 0.5 | 0.5 / 0.5 |
| happy | 0.6 / 0.5 | 0.75 / 0.45 |
| excited | 0.7 / 0.4 | 0.9 / 0.35 |
| amused | 0.55 / 0.5 | 0.7 / 0.45 |
| angry | 0.7 / 0.4 | 0.9 / 0.3 |
| sad | 0.4 / 0.4 | 0.25 / 0.2 |
| afraid | 0.7 / 0.4 | 0.9 / 0.35 |
| anxious | 0.4 / 0.4 | 0.6 / 0.45 |
| surprised | 0.7 / 0.45 | 0.7 / 0.45 |

Chosen by ear on two Voices (`af_bella`, `bm_lewis`). For excited, afraid, anxious and surprised the dials mostly add liveliness; the words carry the Emotion.

## Built-in Voices (English)

Twelve reference clips of about 11 seconds at 24 kHz, each the same neutral sentence rendered with a Kokoro-82M voice (Apache-2.0) and cloned through Chatterbox. Prebuilt and bundled; Kokoro is not a runtime dependency. A credits list names Kokoro.

| Voice | Gender | Accent | Age | Timbre | Suits the Narrator |
|---|---|---|---|---|---|
| `af_alloy` | female | American | adult | low, dark, measured | no |
| `af_aoede` | female | American | adult | dark | yes |
| `af_bella` | female | American | adult | high, measured | yes (default) |
| `af_heart` | female | American | adult | high | no |
| `af_kore` | female | American | adult | low, dark, measured | no |
| `bf_emma` | female | British | adult | bright | yes |
| `am_eric` | male | American | adult | high, dark, measured | no |
| `am_fenrir` | male | American | young adult | high | yes |
| `am_michael` | male | American | adult | bright, measured | yes |
| `bm_daniel` | male | British | adult | bright, brisk | no |
| `bm_fable` | male | British | adult | low, dark, brisk | no |
| `bm_lewis` | male | British | adult | low | no |

Timbre words are a fixed list of ten: low, high, bright, dark, brisk, measured, warm, soft, gruff, crisp.

## Import libraries

| Use | Library | Licence | How it runs |
|---|---|---|---|
| EPUB, XHTML, AO3 HTML | `lxml` with stdlib `zipfile` | BSD-3-Clause | in-process |
| PDF text, fonts and positions | `pdfplumber` 0.11.10 on `pdfminer.six` | MIT | in-process |
| PDF bookmarks | `pypdf` 6.19 | BSD-3-Clause | in-process |
| MOBI, AZW3 and other formats to EPUB | Calibre `ebook-convert` 7.6.0 (Ubuntu 24.04), headless with `QT_QPA_PLATFORM=offscreen` | GPL-3.0 | separate process |
| TXT encoding detection | `charset-normalizer` | MIT | in-process |
| Language detection | `lingua-py` | Apache-2.0 | in-process, offline, no model download |
| AO3 by URL | `httpx` | BSD-3-Clause | in-process |
| Audio and video assembly | ffmpeg 6.1.1 (Ubuntu 24.04) | GPL when built with libx264 | separate process, so the image is an aggregate, as with Calibre |

**Avoided because AGPL:** EbookLib, PyMuPDF. **Avoided because GPL in-process:** `mobi`.

## Measurements

All on the GTX 1050 Ti with a desktop on the card, in Docker Desktop on WSL2 (Windows 10, driver 582.28), unless noted.

| | Analysis (llama.cpp server) | Voicing, two halves in turn | Voicing in Chorus (M1 ticket 13) | Voicing, unchanged model |
|---|---|---|---|---|
| Card in use before loading | 572 MiB | 417 MiB | 418 MiB | 500 MiB |
| Added on the card at peak | 3,330 MiB | 2,456 MiB | 3,100 MiB | 3,469 MiB |
| Spill into system memory | none | none | none | 862 MiB |
| Speed | 18 tokens/s; about 0.2 s per word over both runs | 2.2 times real time | 2.0 times real time | 3.0 times real time |

- The analysis stage fitted with about 190 MiB to spare beside a desktop holding 572 MiB. A busier desktop would push it into system memory under WSL2, or fail on Linux.
- The unchanged voice model fails with out-of-memory when held to what is free on the card, which is what a Linux host with a desktop would do. Hence the split.
- Voicing in Chorus is the two-halves column on whole passages (65 minutes of audio from the six samples) rather than eight short lines. Its peak is T3's phase: about 3.4 GB on the card in all, leaving about 580 MiB free. S3Gen's working memory grows with the length of a sentence; with PyTorch's default allocator a 35 s sentence left 3.85 GB reserved on the card for 2.4 GB in use (a peak of 3,979 MiB, about 100 MiB free), so the voicing process sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, which brought it to 2.37 GB.
- Not measured: a Linux host, and a card with no desktop on it.
