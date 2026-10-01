# Listening test of the top voice candidates on the 1050 Ti

Type: prototype
Status: resolved
Blocked by: 01, 05, 06

## Question

Which voice model(s) should Chorus use? Generate the same sample passages with each shortlisted model on a real 1050 Ti: a Narrator, 2-3 Character Voices, a few Emotions, and one cloned Voice. Shortlist from research: Chatterbox 500M, IndexTTS-2, Qwen3-TTS 0.6B-Base, Chatterbox-Nano. Measure real VRAM (about 2.8 GB is usable when a desktop shares the card) and speed on the pinned stack (torch 2.14.0+cu126, FP32). Then decide by listening, taking speed, VRAM and license into account. Resolves with the chosen default model and any fallback.

## Answer

Default voice model: **Chatterbox 500M** (MIT). No fallback chosen. Ranked by listening on 2026-10-01 (8 lines, 5 Speakers, 7 Emotions, about 54 s of audio per model):

| Rank | Model | Listening verdict | Speed (x real time) | torch peak | License |
|---|---|---|---|---|---|
| 1 | Chatterbox 500M (FP32, `exaggeration`/`cfg_weight` per Emotion) | best | 13.7 (4.6 to 26.6 per line) | 3.7 GB | MIT |
| 2 | IndexTTS-2 (FP16, emotion vector per Emotion) | second, but Emotions are too aggressive | 65.1 (32 to 109 per line) | 8.3 GB | bilibili, commercial use below 100M MAU |
| 3 | Chatterbox-Turbo (FP32) | shows no Emotion | 1.6 | 3.3 GB | MIT |
| 4 | Qwen3-TTS 0.6B-Base (FP32) | worst in both quality and Emotion | 8.6 | 6.1 GB | Apache-2.0 |

Voices: the best was young Jane (reference clip from Kokoro `bf_isabella`); the worst was the Narrator (cloned from a LibriVox reader, Annie Coleman).

Caveats:
- Ran on torch 2.8.0+cu126, not the frozen 2.14.0+cu126. Every model peaked at about 3.9 GB on the card, above the 2.8 GB budget, and the idle reading was broken. IndexTTS-2 and Qwen3-TTS allocated well past 4 GB, so they spilled into system memory. Re-measuring the chosen model is [ticket 14](14-rerun-chosen-voice-model-on-frozen-stack.md).
- IndexTTS-2 was tested at vector strengths of 0.7 to 0.9 only; lower strengths were not tried. Its speed (about an hour for 54 s of audio) rules it out as a default either way.
- Chatterbox-Nano from the shortlist was not run; Chatterbox-Turbo was run instead.

Clips, page and metrics: `../prototypes/voice-listening-test/` (`listen.html`, `out/<model>/metrics.json`).
