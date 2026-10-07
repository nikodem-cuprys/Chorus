"""PROTOTYPE, throwaway (ticket 24). Scores round 1's Speakers (scripts/) against ticket 08's reference labelling,
next to ticket 08's own approach B run on Windows. Writes score.json. Run with any Python 3: python score.py"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
import score as ref  # noqa: E402  (ticket 08's reference labelling and name matching)

out, total = {}, {"container": 0, "windows": 0, "quotes": 0}
for stem, gold in ref.GOLD.items():
    row = {"quotes": len(gold)}
    for name, path in (("container", ROOT / "scripts" / f"{stem}.json"),
                       ("windows", ATTR / "scripts" / "b-llm-only" / f"{stem}.json")):
        labels = json.loads(path.read_text(encoding="utf-8"))["labels"]
        wrong = {i: labels[str(i)]["speaker"] if str(i) in labels else "(no label)" for i in gold
                 if (ref.person(stem, labels[str(i)]["speaker"]) if str(i) in labels else "") not in gold[i]}
        row[name] = len(gold) - len(wrong)
        row[name + "_wrong"] = wrong
        total[name] += row[name]
    total["quotes"] += len(gold)
    out[stem] = row
    print(stem, "| container", row["container"], "| windows", row["windows"], "| of", len(gold))
print("TOTAL", total)
(ROOT / "score.json").write_text(json.dumps({"total": total, "passages": out}, indent=1, ensure_ascii=False), encoding="utf-8")
