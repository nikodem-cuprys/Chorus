"""PROTOTYPE, throwaway. Render Character reference clips with Kokoro-82M (Apache-2.0).
Transcripts are saved next to each clip (Qwen3-TTS uses them for cloning)."""
import json, pathlib
import numpy as np, soundfile as sf
from kokoro import KPipeline

ROOT = pathlib.Path(__file__).parent / "refs"
REFS = {
    "mrs_bennet": ("b", "bf_emma", "Oh! Single, my dear, to be sure! A single man of large fortune; four or five thousand a year. What a fine thing for our girls! I am sure I shall never forget it."),
    "mr_bennet": ("b", "bm_george", "I see no occasion for that. You and the girls may go, or you may send them by themselves, which perhaps will be still better, for as you are as handsome as any of them."),
    "john_reed": ("a", "am_puck", "Now, I'll teach you to rummage my bookshelves: for they are mine; all the house belongs to me, or will do in a few years. Go and stand by the door, out of the way."),
    "jane": ("b", "bf_isabella", "I was glad of it: I never liked long walks, especially on chilly afternoons. Folds of scarlet drapery shut in my view to the right hand; to the left were the clear panes of glass."),
}
pipes = {}
meta = {}
for name, (lang, voice, text) in REFS.items():
    pipe = pipes.setdefault(lang, KPipeline(lang_code=lang))
    audio = np.concatenate([np.asarray(a) for _, _, a in pipe(text, voice=voice)])
    sf.write(ROOT / f"{name}_kokoro.wav", audio, 24000)
    (ROOT / f"{name}_kokoro.txt").write_text(text, encoding="utf-8")
    meta[name] = {"voice": voice, "seconds": round(len(audio) / 24000, 1)}
print(json.dumps(meta, indent=2))
