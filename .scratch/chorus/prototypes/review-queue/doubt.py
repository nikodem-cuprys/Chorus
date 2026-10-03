"""PROTOTYPE, throwaway (ticket 18). Second pass: Qwen3.5-4B rates the Speaker labels approach B gave.
The model sees the same chunks with each quote marked [id = Speaker], names who it thinks speaks the line,
and rates the given label sure / unsure / wrong. Writes doubt/<passage>.json.
Run with any Python 3 (uses ticket 08's llama.cpp wrapper): python doubt.py [passage-stem ...]"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
import llm  # noqa: E402

SYSTEM = (
    "You check the speaker labels of the quoted lines of a work of fiction. Each quoted line is marked "
    "[number = Name], the speaker another reader gave it; 'Narrator' means a quotation not said or thought by a "
    "Character, 'Unknown' means no listed Character fitted. For every numbered line give: the speaker you think is "
    "right (exactly one name from the allowed list), and a verdict on the given label: 'sure' if the text clearly "
    "supports it (a tag such as 'said X', or clear turn-taking), 'unsure' if the text leaves real doubt (no tag, "
    "either party could say it, a group speaks, the speaker is not named), 'wrong' if the text points to someone "
    "else. Check each line against the narration around it. Rate every numbered line exactly once, in order.")


def run(stem):
    lines = json.loads((ATTR / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    script = json.loads((ATTR / "scripts" / "b-llm-only" / f"{stem}.json").read_text(encoding="utf-8"))
    cast, narr = script["characters"], script["narrator"]
    names = [c["name"] for c in cast]
    roster = "\n".join(f"- {c['name']} ({c['gender']}, {c['age']}); also called: {', '.join(c['aliases']) or '-'}"
                       for c in cast)
    roster += (f"\nThe narration is first person; the narrator is {narr['character']}."
               if narr["person"] == "first" else "\nThe narration is third person.")
    schema = {"type": "object", "required": ["lines"], "additionalProperties": False, "properties": {"lines": {
        "type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["id", "speaker", "verdict"], "properties": {
                "id": {"type": "integer"}, "speaker": {"type": "string", "enum": names + ["Narrator", "Unknown"]},
                "verdict": {"type": "string", "enum": ["sure", "unsure", "wrong"]}}}}}}
    given = {int(i): lab["speaker"] for i, lab in script["labels"].items()}
    out, prev_tail, t0, before = {}, "", time.time(), dict(llm.STATS)
    for part in llm.chunks(lines):
        ids = [l["id"] for l in part if l["kind"] == "quote"]
        if ids:
            anchors = {i: given.get(i, "Unknown") for i in ids}
            user = (f"CHARACTERS (allowed speakers, plus Narrator and Unknown):\n{roster}\n\n"
                    + (f"TEXT JUST BEFORE (for context, do not rate):\n{prev_tail}\n\n" if prev_tail else "")
                    + f"TEXT TO CHECK:\n{llm.render(part, anchors=anchors)}\n\n"
                    + f"Rate lines {ids[0]} to {ids[-1]} ({len(ids)} lines).")
            for rec in llm.chat(SYSTEM, user, schema, 4000)["lines"]:
                if rec["id"] in ids:
                    out.setdefault(str(rec["id"]), {"speaker": rec["speaker"], "verdict": rec["verdict"]})
        prev_tail = " ".join(llm.render(part, mark_quotes=False).split()[-150:])
    res = {"passage": stem, "lines": out, "seconds": round(time.time() - t0, 1),
           "stats": {k: round(llm.STATS[k] - before[k], 1) for k in llm.STATS}}
    (ROOT / "doubt").mkdir(exist_ok=True)
    (ROOT / "doubt" / f"{stem}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    v = [r["verdict"] for r in out.values()]
    print(stem, "| rated", len(out), "of", len(given), "|", {k: v.count(k) for k in ("sure", "unsure", "wrong")},
          "|", res["seconds"], "s", flush=True)


if __name__ == "__main__":
    for stem in sys.argv[1:] or sorted(p.stem for p in (ATTR / "lines").glob("*.json")):
        if not (ROOT / "doubt" / f"{stem}.json").exists():
            run(stem)
    print("all done", flush=True)
