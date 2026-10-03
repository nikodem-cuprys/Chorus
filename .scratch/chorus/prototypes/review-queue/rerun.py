"""PROTOTYPE, throwaway (ticket 18). Second pass, blind: label the quotes again with approach B's own prompt and
Character list, but in smaller chunks (600 words instead of 900) so every line sees different context.
Lines where the two runs name different Speakers are queue candidates. Writes rerun/<passage>.json.
Run with any Python 3: python rerun.py [passage-stem ...]"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
import llm  # noqa: E402
from approach_b import attribution_pass  # noqa: E402


def run(stem):
    lines = json.loads((ATTR / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    script = json.loads((ATTR / "scripts" / "b-llm-only" / f"{stem}.json").read_text(encoding="utf-8"))
    cast = {"narrator": script["narrator"], "characters": script["characters"]}
    t0 = time.time()
    labels = attribution_pass(llm.chunks(lines, max_words=600), cast)
    first = {int(i): lab["speaker"] for i, lab in script["labels"].items()}
    differ = sorted(i for i in first if labels.get(i, {}).get("speaker") != first[i])
    (ROOT / "rerun").mkdir(exist_ok=True)
    (ROOT / "rerun" / f"{stem}.json").write_text(json.dumps(
        {"passage": stem, "labels": {str(i): lab for i, lab in labels.items()}, "seconds": round(time.time() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(stem, "| labelled", len(labels), "of", len(first), "| differ", len(differ), differ, "|",
          round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    for stem in sys.argv[1:] or sorted(p.stem for p in (ATTR / "lines").glob("*.json")):
        if not (ROOT / "rerun" / f"{stem}.json").exists():
            run(stem)
    print("all done", flush=True)
