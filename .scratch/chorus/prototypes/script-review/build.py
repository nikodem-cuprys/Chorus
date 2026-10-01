"""PROTOTYPE, throwaway. Build data.js for review.html from the approach B Scripts of ticket 08.
Run with any Python 3: python build.py"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
from score import GOLD, person

passages = []
for f in sorted((ATTR / "lines").glob("*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    script = json.loads((ATTR / "scripts" / "b-llm-only" / f.name).read_text(encoding="utf-8"))
    gold = GOLD[data["passage"]]
    lines = []
    for l in data["lines"]:
        lab = script["labels"].get(str(l["id"]))
        row = {"id": l["id"], "para": l["para"], "quote": l["kind"] == "quote", "text": l["text"]}
        if l["kind"] == "quote":
            row["label"] = lab
            # wrong against the ticket 08 reference; only used for the prototype note in the queue variant
            row["wrong"] = not (lab and person(data["passage"], lab["speaker"]) in gold[l["id"]])
        lines.append(row)
    passages.append({"id": data["passage"], "title": data["title"], "lines": lines,
                     "narrator": script["narrator"], "characters": script["characters"], "scenes": script["scenes"]})

voices = json.loads((ROOT.parent / "voice-library" / "library" / "voices.json").read_text(encoding="utf-8"))
out = "window.DATA = " + json.dumps({"passages": passages, "voices": voices}, ensure_ascii=False) + ";\n"
(ROOT / "data.js").write_text(out, encoding="utf-8")
for p in passages:
    q = [l for l in p["lines"] if l["quote"]]
    names = {c["name"] for c in p["characters"]}
    odd = sorted({l["label"]["speaker"] for l in q if l["label"] and l["label"]["speaker"] not in names})
    print(p["id"], len(p["lines"]), "lines,", len(q), "quotes,", sum(l["wrong"] for l in q), "wrong, no label:",
          sum(not l["label"] for l in q), "speakers outside the Character list:", odd)
