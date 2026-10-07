"""PROTOTYPE, throwaway (ticket 25). Runs inside the container. Compares each setting's clips with the unchanged
model's clips for the same seed: are the speech tokens identical, and how far apart are the waveforms."""
import json, pathlib

import numpy as np
import soundfile as sf

OUT = pathlib.Path("/out")
base = json.loads((OUT / "no-change" / "metrics.json").read_text())
res = {}
for d in sorted(p for p in OUT.iterdir() if (p / "metrics.json").exists() and p.name != "no-change"):
    m, rows = json.loads((d / "metrics.json").read_text()), []
    for b, l in zip(base["lines"], m["lines"]):
        if not (d / f"{l['id']}.wav").exists():
            continue
        x, _ = sf.read(OUT / "no-change" / f"{l['id']}.wav")
        y, _ = sf.read(d / f"{l['id']}.wav")
        n = min(len(x), len(y))
        diff = x[:n] - y[:n]
        rows.append({"id": l["id"], "same_tokens": l["tokens"] == b["tokens"], "same_length": len(x) == len(y),
                     "correlation": round(float(np.corrcoef(x[:n], y[:n])[0, 1]), 4),
                     "difference_db": round(float(10 * np.log10(np.mean(diff**2) / np.mean(x[:n]**2) + 1e-12)), 1)})
    res[d.name] = rows
    print(d.name, *rows, sep="\n  ")
(OUT / "compare.json").write_text(json.dumps(res, indent=1))
