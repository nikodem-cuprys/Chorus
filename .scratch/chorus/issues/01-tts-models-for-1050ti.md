# Free voice models that run on a 1050 Ti with emotion control and voice cloning

Type: research
Status: resolved
Blocked by: none

## Question

Which free text-to-speech models can run inference on a GTX 1050 Ti (4 GB VRAM, Pascal, compute capability 6.1, no tensor cores; CPU fallback acceptable) and offer (a) controllable emotional delivery, (b) zero-shot voice cloning from a short clip, and (c) a set of built-in voices for auto-casting? For each candidate (e.g. Chatterbox, F5-TTS, XTTS-v2, StyleTTS 2, Kokoro, IndexTTS-2, Zonos, Fish Speech, CosyVoice 2, OpenVoice, Orpheus, Piper, Parler-TTS) report: VRAM needed, realistic speed on Pascal, how emotion is controlled (tags, reference audio, an exaggeration parameter), cloning quality, language coverage beyond English, **license (is commercial use allowed?)**, and maintenance status. Rank a shortlist of 2-4 for the listening test.

## Answer

No model covers Emotion, cloning and built-in Voices all at once within 4 GB. Ranked for the listening test: (1) **Chatterbox 500M**: MIT, cloning, `exaggeration` dial, tight fit at ~3.2 GB FP32. (2) **IndexTTS-2**: best Emotion control (8-dim vector); bilibili license allows commercial use below 100M MAU; needs FP16 weights plus CPU offload or CPU-only (2.5 measured >4.3 GB). (3) **Qwen3-TTS 0.6B-Base**: Apache, 3 s cloning, Emotion only from the text; pair it with 1.7B VoiceDesign run on CPU to build the Voice library. (4) **Chatterbox-Nano**: comfortable fit, CPU-capable, tags only.
Non-commercial, so excluded: F5-TTS, XTTS-v2, Fish Speech. Hard constraints for every stage: PyTorch 2.14 cu126 is the last release with Pascal wheels, and FP16 math runs at 1/64 speed on sm_61, so compute stays in FP32.
Details, table and sources: [research/tts-models-for-1050ti.md](../research/tts-models-for-1050ti.md)
