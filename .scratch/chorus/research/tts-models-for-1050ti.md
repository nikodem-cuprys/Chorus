# TTS models for a GTX 1050 Ti: emotion, cloning, built-in voices

Ticket: [01-tts-models-for-1050ti](../issues/01-tts-models-for-1050ti.md). Researched 2026-09-29.

**Question.** Which free TTS models can run inference on a GTX 1050 Ti (4 GB, Pascal, sm_61, no tensor cores; CPU fallback OK) and offer (a) controllable Emotion, (b) zero-shot cloning from a short clip, (c) built-in Voices for auto-casting? Also: license (commercial use?) and maintenance. Rank 2-4 for the listening test.

## TL;DR

1. **No single model does all three well inside 4 GB.** The models with the best Emotion control (IndexTTS-2/2.5, Qwen3-TTS 1.7B instruct, Zonos) need more than 4 GB. The ones that fit easily (Kokoro, Pocket TTS, Chatterbox-Nano) have weak or no Emotion control.
2. **Shortlist for the listening test (ranked):**
   1. **Chatterbox (original 500M, English)**: MIT, zero-shot cloning, one `exaggeration` emotion dial. About 3.2 GB of FP32 weights, so it is tight on 4 GB. Pins torch 2.6.0, which still has Pascal wheels.
   2. **IndexTTS-2**: the best Emotion control (an 8-dim emotion vector, which maps 1:1 to a Script Emotion, or an emotion reference clip) with timbre and emotion kept separate. Commercial use is allowed below 100M MAU. Does **not** fit in 4 GB as shipped, so it needs FP16 plus encoders on CPU, or CPU-only runs.
   3. **Qwen3-TTS 0.6B-Base (cloning), paired with 1.7B VoiceDesign run offline on CPU** to design each Character's Voice from traits. Apache-2.0, 10 languages. The 0.6B model has no instruct Emotion control; Emotion comes only from the text itself.
   4. **Chatterbox-Nano / Turbo** as the "fits comfortably" baseline: MIT, CPU-capable, paralinguistic tags (`[laugh]`, `[sigh]`…). The code ignores `exaggeration`.
3. **Cross-cutting platform risk:** PyTorch **2.14 (cu126) is the last release with Pascal wheels**; 2.15 drops them. cu128 wheels (PyTorch ≥2.8) already lack sm_50–sm_61. The Chorus Docker image must pin torch ≤2.14+cu126 for every stage. [PyTorch notice, 2026-09-04](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432) · [earlier cu128 notice](https://dev-discuss.pytorch.org/t/cuda-toolkit-version-and-architecture-support-update-maxwell-and-pascal-architecture-support-removed-in-cuda-12-8-and-12-9-builds/3128) · [IndexTTS #815: P100 fails on the default cu128](https://github.com/index-tts/index-tts/issues/815)
4. **FP16 on a 1050 Ti saves memory, not time.** Compute capability 6.1 runs 16-bit FP math at 2 ops/clock/SM against 128 for FP32 ([CUDA C Programming Guide, arithmetic throughput table](https://docs.nvidia.com/cuda/archive/12.6.0/cuda-c-programming-guide/index.html#arithmetic-instructions)). BF16 is not native on Pascal. FlashAttention 2 needs Ampere or newer. Plan on FP32 compute, with half precision at most as a weight-storage trick.

## Hardware facts that shape everything

| Fact | Consequence | Source |
|---|---|---|
| sm_61 is absent from PyTorch cu128/cu129 wheels; cu126 is dropped from 2.15 onward | Pin torch ≤2.14 with cu126 (or use a community build). Repos that pin cu128 (IndexTTS) must be re-pinned. | PyTorch dev-discuss notices above |
| FP16 arithmetic on CC 6.1 is 1/64 of FP32 | Keep compute in FP32. Half-precision weights help only if kernels upcast. Measure in the prototype. | CUDA Programming Guide throughput table |
| No native BF16 on Pascal; `torch.cuda.is_bf16_supported()` counts emulation | IndexTTS-2.5's BF16 path would be emulated. Maintainers refused an FP16 fallback. | [IndexTTS PR #798](https://github.com/index-tts/index-tts/issues/798) |
| FlashAttention 2 needs Ampere or newer | Qwen3-TTS's recommended `flash_attention_2` is unavailable; use SDPA/eager. | [Qwen3-TTS README](https://github.com/QwenLM/Qwen3-TTS) (points to FA2 hardware requirements), [flash-attention](https://github.com/Dao-AILab/flash-attention) |
| 1050 Ti: about 112 GB/s memory bandwidth | Autoregressive TTS decoding is memory-bound. Estimated upper bound: tokens/s ≈ 112 GB/s ÷ weight bytes. | Estimate (not measured) |

## Comparison table

VRAM figures marked **(est.)** are my estimates from the checkpoint file sizes on Hugging Face (the HF tree API) plus activations. Only IndexTTS-2.5 has a measured figure on Pascal. "Fits 4 GB?" is a judgement to be confirmed by the prototype.

| Model (latest) | Params / weights on disk | Fits 4 GB? | Emotion control | Cloning | Built-in Voices | Languages | License (weights) | Commercial? | Maintenance |
|---|---|---|---|---|---|---|---|---|---|
| **Chatterbox** (original, EN) | 0.5B T3 (2.13 GB fp32) + S3Gen 1.06 GB ≈ 3.2 GB | **Tight** (est.). Community reports 6–7 GB default, about 1.5 GB with offload/bf16 ([#44](https://github.com/resemble-ai/chatterbox/issues/44)). Half precision is not officially supported ([#564](https://github.com/resemble-ai/chatterbox/issues/564)). | `exaggeration` (0.25–2; ~0.7+ = dramatic) + `cfg_weight` pacing | Yes, ~10 s clip | None: one default voice. Auto-cast needs a curated clip set. | EN (Multilingual V3: 23 langs, 0.5B) | MIT | Yes. Output carries an imperceptible Perth watermark. | Active (pushed 2026-07; Nano added 2026-04) |
| **Chatterbox-Turbo** | 350M; 1.9 GB + 1.06 GB | Borderline (est.) | Paralinguistic tags `[laugh]` `[chuckle]` `[cough]`. `exaggeration`/`cfg_weight` are **ignored** (code warns). | Yes, ~10 s clip (required) | None | EN | MIT | Yes (watermark) | Active |
| **Chatterbox-Nano** | 110M; 0.87 GB + 1.06 GB | **Yes**; also CPU ("3x realtime on 8 cores") | Tags only | Yes (required) | None | EN | MIT | Yes (watermark) | Active (2026-07) |
| **IndexTTS-2** | GPT 3.5 GB fp32 + S2Mel 1.2 GB + Qwen-0.6B emo 1.2 GB + w2v-BERT | **No** as shipped. Maybe with `use_fp16` + emo-Qwen skipped + encoders on CPU (est.). | **Best**: 8-float emotion vector (happy, angry, sad, afraid, disgusted, melancholic, surprised, calm) or an emotion reference clip with `emo_alpha`, or emotion from text. Timbre and emotion are kept separate. Also duration control. | Yes | None | ZH, EN | bilibili Model Use License | **Yes** unless >100M MAU or >RMB 1B revenue | Active (2026-08) |
| **IndexTTS-2.5** (2026-08-10) | larger; BF16 only | **No**: measured 4.39–4.54 GB allocated **even with reference encoders on CPU**, FP32, GTX 1060 ([PR #795](https://github.com/index-tts/index-tts/issues/795)). FP16 rejected ([#798](https://github.com/index-tts/index-tts/issues/798)). | Same as 2 | Yes | None | ZH, EN, JA, ES, AR | bilibili (same) | Yes (same thresholds) | Active |
| **Qwen3-TTS 1.7B CustomVoice / VoiceDesign** (2026-01-22) | 3.8 GB bf16 (+0.68 GB tokenizer) | **No** on GPU (≈7.6 GB fp32). CPU only. | **Natural-language instruct** ("Very happy.", "angry tone"); VoiceDesign builds a voice from a text description | CustomVoice/VoiceDesign: no | 9 premium speakers (CustomVoice) | 10 (ZH EN JA KO DE FR RU PT ES IT) | Apache-2.0 | Yes | Last push 2026-03 (slowing) |
| **Qwen3-TTS 0.6B-Base** | 1.83 GB bf16 → ~3.7 GB fp32 + 0.68 GB tokenizer | Tight in fp32; fits with half-precision weights (est.) | **No instruct**; follows text semantics only | Yes, 3 s clip + transcript | None (the 0.6B CustomVoice has 9 speakers, no instruct) | 10 | Apache-2.0 | Yes | as above |
| **Fun-CosyVoice 3** 0.5B (2025-12) | LLM 2.0 GB + flow 1.3 GB + HiFT 0.08 GB ≈ 3.4 GB fp32 | Tight (est.). Pins torch 2.3.1 (Pascal OK). | Instruct text (`inference_instruct2` = clone + instruction: emotion, speed, volume, dialect); `[laughter]`, `[breath]` tags | Yes, zero-shot and cross-lingual | Built-in SFT speakers (mostly Chinese) | 9 + 18 Chinese dialects | Apache-2.0 | Yes | Active (repo moved to QwenAudio/CosyVoice, pushed 2026-05). Chinese-first; English emotion instruct is unproven. |
| **Kokoro-82M** v1.0 | 0.33 GB | **Yes** (CPU fine) | None | **No** | **54 voices**, 8 languages | EN, others | Apache-2.0 | Yes | Stale (last push 2025-08) |
| **Pocket TTS** (Kyutai) | 100M; 0.22 GB (24-layer variants 1.3 GB) | **Yes**; CPU-only by design, ~6x RT on 2 cores (M4) | None explicit (the reference clip's style carries over) | Yes (wav → embedding, `export-voice`) | ~25 catalog voices, per-voice licenses listed on HF | EN FR DE PT IT ES NL | CC-BY-4.0 (weights); code MIT | Yes (attribution) | Very active (English model updated 2026-09) |
| **F5-TTS** v1 | ~0.3B | Likely yes (est.) | Via reference clip only | Yes, strong | None | ZH/EN (+ community finetunes) | **CC-BY-NC-4.0** (Emilia data) | **No** | Active (2026-09) |
| **XTTS-v2** (idiap fork `coqui-tts`) | ~0.47B, ~1.9 GB | Likely yes (est.) | Via reference clip only | Yes, 6 s | Some studio speakers | 17 | **CPML** (non-commercial). Coqui the company is gone, so no commercial license can be bought. | **No** | Fork maintained (2026-06); original repo dead since 2024-08 |
| **Zonos v0.1** | 1.6B | **No**: README says ≥6 GB; the hybrid variant needs RTX 30xx+ | Emotion vector (happiness, anger, sadness, fear…), pitch, rate | Yes, 10–30 s | None | EN JA ZH FR DE | Apache-2.0 | Yes | **Stale** (last push 2025-03) |
| **Fish Speech / OpenAudio / Fish S2** | 0.5B–4B | S1-mini maybe; S2 no | Emotion markers | Yes | None | many | **Fish Audio Research License** (2026-03-07) | **No**: commercial needs a separate license | Active |
| **Orpheus 3B** | 3B | Only as a Q4 GGUF via llama.cpp + SNAC (est.) | Tags `<laugh>` `<sigh>` etc. | No official zero-shot | 8 voices | EN (+ multilingual research) | Apache-2.0 tag, but a Llama-3.2 finetune, so check the Llama license | Unclear | Slow (2025-12) |
| **StyleTTS 2** | ~0.1–0.2B | Yes | Style from a reference clip (diffusion) | Yes (LibriTTS model) | None | EN | Code MIT. The pretrained model requires telling listeners the speech is synthetic unless you have voice permission. | Yes with the disclosure condition | **Dead** (2024-08) |
| **OpenVoice V2** | small | Yes | V1 only had style presets; V2 base = MeloTTS | Tone-color converter | MeloTTS speakers | 6 | MIT | Yes | Stale (2025-04) |
| **Piper** (`piper1-gpl`) | tiny | Yes (CPU) | None | No | Many community voices (per-voice licenses) | many | **GPL-3.0** (the old MIT repo is archived) | Yes, but GPL | Active |
| **Parler-TTS mini v1.1** | 0.88B | Yes (est.) | Text description ("a sad, slow female voice") | No | 34 named speakers | EN | Apache-2.0 | Yes | **Dead** (2024-12) |
| **VibeVoice** | 1.5B / 0.5B realtime | 0.5B maybe | Limited | 1.5B TTS **disabled by Microsoft** | Realtime: preset voices | EN + experimental | MIT, but "research only, not for commercial use" | Discouraged | TTS side frozen; ASR active |
| **NeuTTS Air** | ~0.7B, 1.5 GB (GGUF available) | Yes (CPU GGUF) | None | Yes, 3 s | Few samples | EN | Apache-2.0 (Nano: other) | Yes | Active (2026-08) |

Sources for table rows: [Chatterbox README](https://github.com/resemble-ai/chatterbox) and [tts_turbo.py](https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/tts_turbo.py) (`exaggeration`/`cfg_weight` ignored in Turbo/Nano) and [pyproject.toml](https://github.com/resemble-ai/chatterbox/blob/master/pyproject.toml) (torch==2.6.0); [IndexTTS README](https://github.com/index-tts/index-tts), [LICENSE §2.2](https://github.com/index-tts/index-tts/blob/main/LICENSE), [pyproject](https://github.com/index-tts/index-tts/blob/main/pyproject.toml) (torch 2.8 cu128); [Qwen3-TTS README](https://github.com/QwenLM/Qwen3-TTS); [CosyVoice README](https://github.com/QwenAudio/CosyVoice) + [example.py](https://github.com/QwenAudio/CosyVoice/blob/main/example.py) + requirements.txt; [Kokoro-82M card](https://huggingface.co/hexgrad/Kokoro-82M); [Pocket TTS README](https://github.com/kyutai-labs/pocket-tts), [HF card](https://huggingface.co/kyutai/pocket-tts); [F5-TTS README](https://github.com/SWivid/F5-TTS) (weights CC-BY-NC); [XTTS-v2 card](https://huggingface.co/coqui/XTTS-v2) (CPML); [Zonos README](https://github.com/Zyphra/Zonos); [Fish Speech LICENSE](https://github.com/fishaudio/fish-speech/blob/main/LICENSE); [VibeVoice README](https://github.com/microsoft/VibeVoice) (2025-09-05 TTS removal; "Disabled"); licenses, last-push dates and weight sizes from the GitHub repo API and the Hugging Face model API (`/api/models/<id>`, `/tree/main`), queried 2026-09-29.

## Realistic speed on Pascal

There are almost no published sm_61 benchmarks. The only hard number found is IndexTTS-2.5 on a GTX 1060 6 GB in FP32: 34 s to load, then 8–20 s per reference-cache miss ([PR #795](https://github.com/index-tts/index-tts/issues/795)). Synthesis RTF was not reported. Estimates from memory bandwidth, where tokens/s ≲ 112 GB/s ÷ weights:
- Chatterbox T3 (2.1 GB fp32, 25 speech tokens/s of audio): at most ~50 tok/s, i.e. **roughly 0.5–1.5x realtime** after overhead. The HF-transformers decode loop has heavy CPU-GPU sync ([#127](https://github.com/resemble-ai/chatterbox/issues/127)), so expect the low end.
- Chatterbox-Nano (0.87 GB): ~2–4x realtime (est.).
- IndexTTS-2 with partial CPU offload: likely **slower than realtime** (0.1–0.5x est.). This is acceptable under the "slow is fine" constraint.
- Kokoro / Pocket TTS: faster than realtime even on CPU.

For a 10-hour audiobook, 0.3x realtime means about 33 hours of generation. That is acceptable per the map Notes, but it makes resume-after-crash (map: *Long jobs*) mandatory.

## How each model would deliver Chorus's Emotion

- **Emotion vector (IndexTTS-2, Zonos):** the cleanest fit, because the Script's per-line Emotion maps directly onto the vector with an intensity. Chorus's text analysis already produces the Emotion, so IndexTTS's built-in Qwen emotion-from-text model can be left unloaded (saves ~1.2 GB).
- **Scalar intensity (Chatterbox `exaggeration`):** one dial for "how intense". It cannot tell anger from joy. The kind of emotion has to come from the text itself or from a per-emotion reference clip (clone the Character's Voice from an "angry" clip of the same voice). That means every built-in Voice needs several emotional reference clips.
- **Natural-language instruct (Qwen3-TTS 1.7B, CosyVoice 3, Parler):** flexible, but the small models that fit (Qwen 0.6B) lack it, and CosyVoice's instruct is tuned mostly for Chinese.
- **Tags (Chatterbox Turbo/Nano, Orpheus, CosyVoice):** only non-verbal sounds (laugh, sigh, breath). They add colour but are not Emotion control.

## Built-in Voices for auto-casting

None of the cloning-capable models that fit ships a real voice set; Chatterbox ships one default voice. So Chorus's "built-in set" will in practice be **a bundled library of licensed reference clips**, tagged with traits (gender, age, accent, timbre). Candidate sources, each needing its license checked: VCTK / Expresso / EARS clips as curated in [kyutai/tts-voices](https://huggingface.co/kyutai/tts-voices) (per-voice licenses listed; note Expresso is CC-BY-NC), and LibriTTS-R.
An alternative is to **generate the clip library with Qwen3-TTS 1.7B VoiceDesign** (Apache-2.0) from trait descriptions, run once, offline, on CPU, then clone those clips with the runtime model. This removes the dependency on third-party voice licenses and fits the "slow is fine" constraint.
Kokoro's 54 voices cannot feed a cloning model directly, but a Kokoro render can serve as a reference clip.

## Ranked shortlist for the listening test

1. **Chatterbox (original, 500M)**. MIT, fits or nearly fits, Pascal-compatible torch pin, good English cloning, an emotion-intensity dial, active project. Risk: 4 GB headroom. Fallback within the same family: Nano.
2. **IndexTTS-2**. The best Emotion model with a commercial-OK license. Test whether FP16 weights + encoders on CPU + no emo-Qwen fits 4 GB and what the speed is; otherwise run it CPU-only. Must be re-pinned from cu128 to cu126. Skip 2.5 (measured >4.3 GB, BF16-only).
3. **Qwen3-TTS 0.6B-Base (+ 1.7B VoiceDesign on CPU for building the Voice library)**. Apache, 10 languages (good for *More languages*), 3 s cloning. Test whether Emotion from text semantics alone is audible enough.
4. **Chatterbox-Nano** as the comfortable-fit, CPU-capable baseline. If it sounds close to #1, it wins on robustness.

Excluded from the shortlist for licensing reasons, though they fit technically: **F5-TTS** (CC-BY-NC weights), **XTTS-v2** (CPML, and no seller left), **Fish Speech/OpenAudio** (research license). Kokoro is a fine emotionless fallback narrator but cannot clone.

## Open questions and risks

- **Chatterbox watermark:** every output carries the Perth watermark. That is harmless for listening, but YouTube Publishing and any monetization should expect AI-detection; decide whether to disclose (YouTube requires disclosure of realistic synthetic content anyway). Cloning from a user clip also raises consent (Pocket TTS and others prohibit cloning without consent).
- **The torch pin is a system-wide constraint.** Text analysis (LLM) and any ASR must also run on torch ≤2.14 cu126 or on non-torch runtimes (llama.cpp / ONNX Runtime built for sm_61). This belongs in map Notes.
- **Two models may share the 4 GB** (e.g. an analysis LLM and TTS): stages must run sequentially with unloading, never concurrently.
- **Measured VRAM/RTF on a real 1050 Ti** is not available from any source. The listening test ticket should record peak `torch.cuda.max_memory_allocated` and RTF per model.
