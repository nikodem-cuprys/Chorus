"""PROTOTYPE, throwaway (ticket 19). Can a respelling fix how Chatterbox 500M says a hard name?
Ten names from fantasy and fanfic, each in one carrier sentence that says the name twice, rendered three ways:
  written  - the name as the book spells it
  hyphen   - a respelling with hyphens between syllables ("Her-my-oh-nee")
  fused    - the same respelling as one ordinary-looking word ("Hermyohnee")
"Reliably" is tested with two Voices and, for the Narrator Voice, a second seed.
Run with the frozen-stack env, offline: HF_HOME=../voice-listening-test/hf-cache HF_HUB_OFFLINE=1.
Safe to re-run: finished clips are skipped."""
import json, pathlib, time
import numpy as np, soundfile as sf, torch
from chatterbox.tts import ChatterboxTTS

ROOT = pathlib.Path(__file__).parent
LIB = ROOT.parent / "voice-library" / "library"
RUNS = [("af_bella", 0), ("af_bella", 1), ("bm_lewis", 0)]
SENTENCE = "I asked {n} about it, but {n} only laughed."

# name: (how it should sound, hyphen respelling, fused respelling)
NAMES = {
    "Hermione":   ("her-MY-oh-nee",                         "Her-my-oh-nee",  "Hermyohnee"),
    "Daenerys":   ("duh-NAIR-iss",                          "Duh-nair-iss",   "Danairiss"),
    "Cthulhu":    ("kuh-THOO-loo",                          "Kuh-thoo-loo",   "Kathooloo"),
    "Siobhan":    ("shiv-AWN",                              "Shiv-awn",       "Shivawn"),
    "Niamh":      ("NEEV, one syllable",                    "Neev",           "Neeve"),
    "Nynaeve":    ("nye-NEEV",                              "Nye-neev",       "Nyneeve"),
    "Wei Wuxian": ("way woo-SHYEN",                         "Way Woo-shyen",  "Way Wooshyen"),
    "Kvothe":     ("like the word quote with a soft th: KWOHTH", "Kwoh-th",   "Quothe"),
    "Thranduil":  ("THRAN-doo-il",                          "Thran-doo-il",   "Thrandooill"),
    "Geralt":     ("GEH-ralt, hard G as in get",            "Geh-ralt",       "Gherralt"),
}
STYLES = ["written", "hyphen", "fused"]


def slug(name):
    return name.lower().replace(" ", "-")


def plan():
    for voice, seed in RUNS:
        for name, (_, hyphen, fused) in NAMES.items():
            for style, spoken in zip(STYLES, (name, hyphen, fused)):
                yield dict(key=f"{slug(name)}_{style}_{voice}_s{seed}", name=name, style=style, spoken=spoken,
                           voice=voice, seed=seed, text=SENTENCE.format(n=spoken))


def main():
    todo = [c for c in plan() if not (ROOT / "out" / f"{c['key']}.json").exists()]
    print(f"{len(todo)} clips to render", flush=True)
    if not todo:
        return
    model = ChatterboxTTS.from_pretrained(device="cuda")
    (ROOT / "out").mkdir(exist_ok=True)
    current = None
    for n, c in enumerate(todo, 1):
        if current != c["voice"]:
            model.prepare_conditionals(str(LIB / f"{c['voice']}.wav"))
            current = c["voice"]
        torch.manual_seed(c["seed"])
        t = time.time()
        wav = model.generate(c["text"], exaggeration=0.5, cfg_weight=0.5)
        wav = np.asarray(wav.cpu().numpy(), dtype=np.float32).squeeze()
        sf.write(ROOT / "out" / f"{c['key']}.wav", wav, model.sr)
        (ROOT / "out" / f"{c['key']}.json").write_text(json.dumps(dict(c, audio_s=round(len(wav) / model.sr, 2))),
                                                         encoding="utf-8")
        print(f"[{n}/{len(todo)}] {c['key']} {len(wav) / model.sr:.1f}s audio in {time.time() - t:.0f}s", flush=True)
    print("all done", flush=True)


if __name__ == "__main__":
    main()
