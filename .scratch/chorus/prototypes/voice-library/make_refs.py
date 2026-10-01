"""PROTOTYPE, throwaway. Render one neutral reference clip per English Kokoro voice (Apache-2.0).
Run with the kokoro env from ../voice-listening-test: python make_refs.py"""
import pathlib
import numpy as np, soundfile as sf
from kokoro import KPipeline

ROOT = pathlib.Path(__file__).parent
TEXT = ("The house stood at the end of a long gravel road, behind a row of old chestnut trees. "
        "Every morning the post arrived at nine, and every evening the lamps were lit before the sun went down.")
(ROOT / "refs").mkdir(exist_ok=True)
(ROOT / "refs" / "_text.txt").write_text(TEXT, encoding="utf-8")
pipes = {}
for pt in sorted((ROOT / "kokoro-voices").glob("*.pt")):
    out = ROOT / "refs" / f"{pt.stem}.wav"
    if out.exists():
        continue
    lang = pt.stem[0]  # a = American, b = British
    pipe = pipes.setdefault(lang, KPipeline(lang_code=lang))
    audio = np.concatenate([np.asarray(a) for _, _, a in pipe(TEXT, voice=str(pt))])
    sf.write(out, audio, 24000)
    print(pt.stem, round(len(audio) / 24000, 1), "s", flush=True)
