"""PROTOTYPE, throwaway (ticket 17). Can a Scene's Mood be heard with no music?
Chorus controls three things: each Character line's Emotion settings (ticket 16, kept fixed here), the
Narrator's delivery, and the pauses put between lines at assembly. This renders two Scenes once for the
Character lines and once per Mood for the Narrator lines; build_page.py then assembles each Scene per Mood
with pauses only, Narrator delivery only, and both.
  jane-eyre     - dialogue-heavy (John Reed finds Jane); the analysis called this Scene "tense"
  metamorphosis - narration-heavy (Gregor wakes); the analysis called its Scenes "tense" then "melancholic"
Run with the frozen-stack env, offline: HF_HOME=../voice-listening-test/hf-cache HF_HUB_OFFLINE=1.
Safe to re-run: finished clips are skipped."""
import json, pathlib, time
import numpy as np, soundfile as sf, torch
from chatterbox.tts import ChatterboxTTS

ROOT = pathlib.Path(__file__).parent
LIB = ROOT.parent / "voice-library" / "library"
EMO = json.loads((ROOT.parent / "emotion-settings" / "emotions.json").read_text(encoding="utf-8"))["emotions"]
NARRATOR = "af_bella"

# Starting guesses, to be corrected by ear. narrator = (exaggeration, cfg_weight) for every Narrator line
# in the Scene; pause = multiplier on every pause at assembly. "calm" is the same as ignoring Mood.
MOODS = {
    "calm":        {"narrator": (0.5, 0.5),   "pause": 1.0},
    "tense":       {"narrator": (0.7, 0.4),   "pause": 0.6},
    "melancholic": {"narrator": (0.3, 0.25),  "pause": 1.6},
    "cheerful":    {"narrator": (0.65, 0.5),  "pause": 0.85},
}
# Base pause in seconds after a line, by what follows it.
PAUSE = {"same": 0.3, "line": 0.45, "para": 0.75}

N = "Narrator"
# (speaker, emotion, intensity, text, what follows: same Script line / next line / new paragraph)
SCENES = {
    "jane-eyre": {
        "title": "Jane Eyre, chapter 1: John Reed finds Jane (dialogue-heavy)",
        "voices": {"John Reed": "am_fenrir", "Jane": "af_heart", "Eliza Reed": "bf_emma"},
        "lines": [
            ("John Reed", "angry", "normal", "Boh! Madam Mope!", "line"),
            (N, None, None, "cried the voice of John Reed; then he paused: he found the room apparently empty.", "para"),
            ("John Reed", "angry", "normal", "Where the dickens is she!", "line"),
            (N, None, None, "he continued.", "line"),
            ("John Reed", "angry", "strong", "Lizzy! Georgy! Joan is not here: tell mama she is run out into the rain, bad animal!", "para"),
            ("Jane", "anxious", "normal", "It is well I drew the curtain,", "line"),
            (N, None, None, "thought I; and I wished fervently he might not discover my hiding-place: nor would John Reed have found it out himself; he was not quick either of vision or conception;", "same"),
            (N, None, None, "but Eliza just put her head in at the door, and said at once:", "para"),
            ("Eliza Reed", "neutral", "normal", "She is in the window-seat, to be sure, Jack.", "para"),
            (N, None, None, "And I came out immediately, for I trembled at the idea of being dragged forth by the said Jack.", "para"),
            ("Jane", "anxious", "normal", "What do you want?", "line"),
            (N, None, None, "I asked, with awkward diffidence.", "para"),
            ("John Reed", "neutral", "normal", "Say, What do you want, Master Reed?", "line"),
            (N, None, None, "was the answer.", "line"),
            ("John Reed", "neutral", "normal", "I want you to come here;", "line"),
            (N, None, None, "and seating himself in an arm-chair, he intimated by a gesture that I was to approach and stand before him.", "para"),
        ],
    },
    "metamorphosis": {
        "title": "Metamorphosis, opening: Gregor wakes (narration-heavy)",
        "voices": {"Gregor": "bm_lewis"},
        "lines": [
            (N, None, None, "One morning, when Gregor Samsa woke from troubled dreams, he found himself transformed in his bed into a horrible vermin.", "same"),
            (N, None, None, "He lay on his armour-like back, and if he lifted his head a little he could see his brown belly, slightly domed and divided by arches into stiff sections.", "same"),
            (N, None, None, "The bedding was hardly able to cover it and seemed ready to slide off any moment.", "same"),
            (N, None, None, "His many legs, pitifully thin compared with the size of the rest of him, waved about helplessly as he looked.", "para"),
            ("Gregor", "anxious", "strong", "What's happened to me?", "line"),
            (N, None, None, "he thought. It wasn't a dream.", "same"),
            (N, None, None, "His room, a proper human room although a little too small, lay peacefully between its four familiar walls.", "para"),
            (N, None, None, "Gregor then turned to look out the window at the dull weather.", "same"),
            (N, None, None, "Drops of rain could be heard hitting the pane, which made him feel quite sad.", "line"),
            ("Gregor", "sad", "normal", "How about if I sleep a little bit longer and forget all this nonsense,", "line"),
            (N, None, None, "he thought, but that was something he was unable to do because he was used to sleeping on his right, and in his present state couldn't get into that position.", "same"),
            (N, None, None, "However hard he threw himself onto his right, he always rolled back to where he was.", "para"),
        ],
    },
}


def plan():
    for scene, s in SCENES.items():
        for i, (spk, emo, inten, text, _) in enumerate(s["lines"]):
            if spk == N:
                for mood, m in MOODS.items():
                    ex, cfg = m["narrator"]
                    yield dict(scene=scene, key=f"{i:02d}_{mood}", voice=NARRATOR, text=text, ex=ex, cfg=cfg)
            else:
                ex, cfg = EMO[emo][inten]
                yield dict(scene=scene, key=f"{i:02d}", voice=s["voices"][spk], text=text, ex=ex, cfg=cfg)


def main():
    todo = [c for c in plan() if not (ROOT / "out" / c["scene"] / "clips" / f"{c['key']}.json").exists()]
    todo.sort(key=lambda c: c["voice"])  # one reference clip at a time
    print(f"{len(todo)} clips to render", flush=True)
    if not todo:
        return
    model = ChatterboxTTS.from_pretrained(device="cuda")
    current = None
    for n, c in enumerate(todo, 1):
        out = ROOT / "out" / c["scene"] / "clips"
        out.mkdir(parents=True, exist_ok=True)
        if current != c["voice"]:
            model.prepare_conditionals(str(LIB / f"{c['voice']}.wav"))
            current = c["voice"]
        torch.manual_seed(0)  # fixed seed per line (ticket 16)
        t = time.time()
        wav = model.generate(c["text"], exaggeration=c["ex"], cfg_weight=c["cfg"])
        wav = np.asarray(wav.cpu().numpy(), dtype=np.float32).squeeze()
        sf.write(out / f"{c['key']}.wav", wav, model.sr)
        (out / f"{c['key']}.json").write_text(json.dumps(dict(c, audio_s=round(len(wav) / model.sr, 2))), encoding="utf-8")
        print(f"[{n}/{len(todo)}] {c['scene']}/{c['key']} {c['voice']} {len(wav) / model.sr:.1f}s audio "
              f"in {time.time() - t:.0f}s", flush=True)
    print("all done", flush=True)


if __name__ == "__main__":
    main()
