"""PROTOTYPE, throwaway. Clone every reference clip through Chatterbox 500M on two fixed lines,
and save the speaker embedding Chatterbox derives from each clip (used to pick contrasting Voices).
Run with the frozen-stack env (torch 2.14.0+cu126). Safe to re-run: finished voices are skipped."""
import json, pathlib, time
import numpy as np, soundfile as sf, torch
from chatterbox.tts import ChatterboxTTS

ROOT = pathlib.Path(__file__).parent
LINES = {
    "narration": dict(text="It is a truth universally acknowledged, that a single man in possession of a good fortune "
                           "must be in want of a wife.", exaggeration=0.5, cfg_weight=0.5),
    "dialogue": dict(text="No! I will not go back there. You promised me it was over, and now you ask me to pretend "
                          "that nothing happened?", exaggeration=0.9, cfg_weight=0.4),
}
(ROOT / "lines.json").write_text(json.dumps(LINES, indent=2), encoding="utf-8")
model = ChatterboxTTS.from_pretrained(device="cuda")
for ref in sorted((ROOT / "refs").glob("*.wav")):
    out = ROOT / "out" / ref.stem
    if (out / "info.json").exists():
        print("skip", ref.stem, flush=True)
        continue
    out.mkdir(parents=True, exist_ok=True)
    info = {"voice": ref.stem, "lines": {}}
    model.prepare_conditionals(str(ref))
    info["speaker_emb"] = model.conds.t3.speaker_emb.flatten().cpu().tolist()
    for name, line in LINES.items():
        torch.manual_seed(0)
        t = time.time()
        wav = model.generate(line["text"], exaggeration=line["exaggeration"], cfg_weight=line["cfg_weight"])
        wav = np.asarray(wav.cpu().numpy(), dtype=np.float32).squeeze()
        sf.write(out / f"{name}.wav", wav, model.sr)
        info["lines"][name] = {"gen_s": round(time.time() - t, 1), "audio_s": round(len(wav) / model.sr, 1)}
    (out / "info.json").write_text(json.dumps(info), encoding="utf-8")
    print("done", ref.stem, info["lines"], flush=True)
print("all done", flush=True)
