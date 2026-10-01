"""PROTOTYPE, throwaway. Save the 12 Voices the user chose by ear (ticket 15) as library/:
one reference clip per Voice plus voices.json with their labels. Run with any Python 3."""
import json, pathlib, shutil

ROOT = pathlib.Path(__file__).parent
TIMBRE_WORDS = ["low", "high", "bright", "dark", "brisk", "measured", "warm", "soft", "gruff", "crisp"]
# voice: (age, timbre words, suits the Narrator) -- pasted from listen.html on 2026-10-01
CHOSEN = {
    "af_alloy": ("adult", ["low", "dark", "measured"], False),
    "af_aoede": ("adult", ["dark"], True),
    "af_bella": ("adult", ["high", "measured"], True),
    "af_heart": ("adult", ["high"], False),
    "af_kore": ("adult", ["low", "dark", "measured"], False),
    "bf_emma": ("adult", ["bright"], True),
    "am_eric": ("adult", ["high", "dark", "measured"], False),
    "am_fenrir": ("young adult", ["high"], True),
    "am_michael": ("adult", ["bright", "measured"], True),
    "bm_daniel": ("adult", ["bright", "brisk"], False),
    "bm_fable": ("adult", ["low", "dark", "brisk"], False),
    "bm_lewis": ("adult", ["low"], False),
}
DEFAULT_NARRATOR = "af_bella"

lib = ROOT / "library"
lib.mkdir(exist_ok=True)
voices = []
for name, (age, timbre, narrator_ok) in CHOSEN.items():
    assert set(timbre) <= set(TIMBRE_WORDS)
    shutil.copyfile(ROOT / "refs" / f"{name}.wav", lib / f"{name}.wav")
    voices.append({
        "id": name, "language": "en", "gender": "female" if name[1] == "f" else "male", "age": age,
        "accent": "American" if name[0] == "a" else "British", "timbre": timbre, "narrator_ok": narrator_ok,
        "clips": {"neutral": f"{name}.wav"},  # more clips per Emotion can be added here later
        "source": f"Kokoro-82M voice {name} (Apache-2.0)",
    })
(lib / "voices.json").write_text(json.dumps({
    "default_narrator": DEFAULT_NARRATOR, "timbre_words": TIMBRE_WORDS,
    "clip_text": (ROOT / "refs" / "_text.txt").read_text(encoding="utf-8"), "voices": voices}, indent=2), encoding="utf-8")
print(len(voices), "voices;", sum(v["gender"] == "female" for v in voices), "women;",
      sum(v["narrator_ok"] for v in voices), "suit the Narrator; default", DEFAULT_NARRATOR)
