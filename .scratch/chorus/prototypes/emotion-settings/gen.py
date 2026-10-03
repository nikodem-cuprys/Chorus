"""PROTOTYPE, throwaway (ticket 16). Render Chatterbox 500M clips to choose the Emotion list and the
settings for each Emotion and intensity. Three parts:
  dials    - one neutral-text line across a grid of exaggeration x cfg_weight: what can the dials do?
  emotions - each candidate Emotion at low/medium/high on a line written for it, plus the same neutral
             line at that Emotion's high settings (do settings alone carry the Emotion?)
  seed     - three lines rendered twice with seed 0 and once with seed 1: does a fixed seed repeat?
Every clip records the speaker similarity between the output and the Voice's reference clip
(Chatterbox's own voice encoder), so "is the Voice still recognisable" has a number beside the ear.
Run with the frozen-stack env (torch 2.14.0+cu126). Safe to re-run: finished clips are skipped.
Usage: python gen.py [part ...]"""
import json, pathlib, sys, time
import numpy as np, soundfile as sf, torch, librosa
from chatterbox.tts import ChatterboxTTS

ROOT = pathlib.Path(__file__).parent
LIB = ROOT.parent / "voice-library" / "library"
VOICES = ["af_bella", "bm_lewis"]  # default Narrator (US woman), British man
NEUTRAL_TEXT = "The carriage will be at the door at nine, and we shall leave the moment it arrives."

# Starting guesses, to be corrected by ear. (exaggeration, cfg_weight) per intensity.
# Chatterbox: higher exaggeration = more expressive and faster; lower cfg_weight = slower, more deliberate.
EMOTIONS = {
    "neutral":   {"text": NEUTRAL_TEXT,
                  "low": (0.5, 0.5), "medium": (0.5, 0.5), "high": (0.5, 0.5)},
    "happy":     {"text": "Oh, how lovely! I never thought we should all be together again so soon.",
                  "low": (0.6, 0.5), "medium": (0.75, 0.45), "high": (0.95, 0.4)},
    "excited":   {"text": "He is coming here, tonight, to this very house, and he has asked for you by name!",
                  "low": (0.7, 0.4), "medium": (0.9, 0.35), "high": (1.2, 0.3)},
    "amused":    {"text": "You think the parrot learned that from the vicar? I should very much like to hear him say it.",
                  "low": (0.55, 0.5), "medium": (0.7, 0.45), "high": (0.85, 0.4)},
    "angry":     {"text": "How dare you open my letters! You had no right, none at all, and you know it.",
                  "low": (0.7, 0.4), "medium": (1.0, 0.3), "high": (1.4, 0.25)},
    "sad":       {"text": "She was gone before the spring came, and the garden she planted never bloomed again.",
                  "low": (0.4, 0.4), "medium": (0.35, 0.35), "high": (0.3, 0.3)},
    "afraid":    {"text": "Please, don't open that door. I heard something moving behind it, I swear I did.",
                  "low": (0.7, 0.4), "medium": (0.9, 0.35), "high": (1.2, 0.3)},
    "anxious":   {"text": "Do you think they noticed? I keep thinking someone saw us leave, and that they will tell.",
                  "low": (0.6, 0.45), "medium": (0.75, 0.4), "high": (0.95, 0.35)},
    "surprised": {"text": "Married? To him? But you told me only last week that you could not bear the man!",
                  "low": (0.7, 0.45), "medium": (0.9, 0.4), "high": (1.2, 0.35)},
    "disgusted": {"text": "Take that thing away from me. It smells as if it has been dead for a week.",
                  "low": (0.5, 0.4), "medium": (0.65, 0.35), "high": (0.85, 0.3)},
}
INTENSITIES = ["low", "medium", "high"]
DIAL_EX = [0.25, 0.5, 0.8, 1.2, 1.6]
DIAL_CFG = [0.5, 0.3]
SEED_LINES = ["neutral", "angry", "sad"]
# Round 2, after the first verdicts: sad "needs stronger" (direction unknown, so try both), anxious
# "lower the better", and angry at 1.2 (the user's ceiling; only 1.0 and 1.4 were heard).
ROUND2 = {
    "sad":     [(0.25, 0.3), (0.25, 0.2), (0.3, 0.15), (0.6, 0.3), (0.8, 0.3)],
    "anxious": [(0.4, 0.4), (0.5, 0.45)],
    "angry":   [(0.8, 0.3), (0.9, 0.3), (1.2, 0.3)],  # 0.8 and 0.9 added after 1.0+ was judged too aggressive
}


def plan(parts):
    for v in VOICES:
        if "dials" in parts:
            for ex in DIAL_EX:
                for cfg in DIAL_CFG:
                    yield dict(part="dials", voice=v, key=f"ex{ex}_cfg{cfg}", text=NEUTRAL_TEXT, ex=ex, cfg=cfg, seed=0)
        if "emotions" in parts:
            for emo, e in EMOTIONS.items():
                for i in (["low"] if emo == "neutral" else INTENSITIES):
                    ex, cfg = e[i]
                    yield dict(part="emotions", voice=v, key=f"{emo}_{i}", emotion=emo, intensity=i,
                               text=e["text"], ex=ex, cfg=cfg, seed=0)
                if emo != "neutral":
                    ex, cfg = e["high"]
                    yield dict(part="emotions", voice=v, key=f"{emo}_neutraltext", emotion=emo, intensity="high",
                               text=NEUTRAL_TEXT, ex=ex, cfg=cfg, seed=0, control=True)
        if "round2" in parts:
            for emo, settings in ROUND2.items():
                for ex, cfg in settings:
                    yield dict(part="round2", voice=v, key=f"{emo}_ex{ex}_cfg{cfg}", emotion=emo,
                               text=EMOTIONS[emo]["text"], ex=ex, cfg=cfg, seed=0)
        if "seed" in parts:
            for emo in SEED_LINES:
                ex, cfg = EMOTIONS[emo]["medium"]
                for run, seed in (("a", 0), ("b", 0), ("c", 1)):
                    yield dict(part="seed", voice=v, key=f"{emo}_seed{seed}{run}", emotion=emo,
                               text=EMOTIONS[emo]["text"], ex=ex, cfg=cfg, seed=seed)


def main():
    parts = sys.argv[1:] or ["dials", "emotions", "seed"]
    todo = [c for c in plan(parts) if not (ROOT / "out" / c["part"] / c["voice"] / f"{c['key']}.json").exists()]
    print(f"{len(todo)} clips to render", flush=True)
    if not todo:
        return
    model = ChatterboxTTS.from_pretrained(device="cuda")
    ref_emb = {}
    for v in VOICES:
        y, _ = librosa.load(LIB / f"{v}.wav", sr=16000)
        ref_emb[v] = model.ve.embeds_from_wavs([y], sample_rate=16000, as_spk=True)
    current = None
    for n, c in enumerate(todo, 1):
        out = ROOT / "out" / c["part"] / c["voice"]
        out.mkdir(parents=True, exist_ok=True)
        if current != c["voice"]:
            model.prepare_conditionals(str(LIB / f"{c['voice']}.wav"))
            current = c["voice"]
        torch.manual_seed(c["seed"])
        t = time.time()
        wav = model.generate(c["text"], exaggeration=c["ex"], cfg_weight=c["cfg"])
        wav = np.asarray(wav.cpu().numpy(), dtype=np.float32).squeeze()
        gen_s = time.time() - t
        sf.write(out / f"{c['key']}.wav", wav, model.sr)
        emb = model.ve.embeds_from_wavs([librosa.resample(wav, orig_sr=model.sr, target_sr=16000)],
                                        sample_rate=16000, as_spk=True)
        sim = float(np.dot(emb, ref_emb[c["voice"]]) / (np.linalg.norm(emb) * np.linalg.norm(ref_emb[c["voice"]])))
        audio_s = len(wav) / model.sr
        info = dict(c, gen_s=round(gen_s, 1), audio_s=round(audio_s, 2),
                    words_per_s=round(len(c["text"].split()) / audio_s, 2), speaker_sim=round(sim, 3))
        (out / f"{c['key']}.json").write_text(json.dumps(info), encoding="utf-8")
        print(f"[{n}/{len(todo)}] {c['part']}/{c['voice']}/{c['key']} sim={sim:.3f} "
              f"{audio_s:.1f}s audio in {gen_s:.0f}s", flush=True)
    print("all done", flush=True)


if __name__ == "__main__":
    main()
