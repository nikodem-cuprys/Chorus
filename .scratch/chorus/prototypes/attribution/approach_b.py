"""PROTOTYPE, throwaway. Approach B: LLM-only. A Character list with aliases is built chunk by chunk
(the global alias list), then each chunk's quotes get a Speaker and an Emotion.
Run with any Python 3: python approach_b.py [passage-stem ...]"""
import json, pathlib, sys, time
import llm

ROOT = pathlib.Path(__file__).parent
NAME = "b-llm-only"

CHAR_SCHEMA = {"type": "object", "required": ["narrator", "characters"], "additionalProperties": False, "properties": {
    "narrator": {"type": "object", "additionalProperties": False, "required": ["person", "character"], "properties": {
        "person": {"type": "string", "enum": ["first", "third"]}, "character": {"type": "string"}}},
    "characters": {"type": "array", "maxItems": 30, "items": {"type": "object", "additionalProperties": False,
        "required": ["name", "aliases", "gender", "age"], "properties": {
            "name": {"type": "string"}, "aliases": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
            "gender": {"type": "string", "enum": ["female", "male", "unknown"]},
            "age": {"type": "string", "enum": ["child", "young adult", "adult", "elderly", "unknown"]}}}}}}

CHAR_SYSTEM = (
    "You maintain the list of Characters of a work of fiction. A Character is a person (or creature) who speaks or "
    "thinks at least one quoted line. You get the list so far and the next part of the text. Return the full updated "
    "list. Give each Character one canonical name and list every other way the text refers to them as aliases "
    "(titles, first names, nicknames, 'my dear', descriptions). Never list the same person twice; merge instead. "
    "Say whether the narration is in the first or third person; if first person, 'character' is the canonical name "
    "of the narrating Character (use the name others call them, or a short description if never named), else ''.")

ATTR_SYSTEM = (
    "You label the quoted lines of a work of fiction for an audio drama. Each quoted line is marked with its number "
    "in square brackets. For every numbered line give: the speaker (exactly one name from the allowed list; 'Narrator' "
    "if the quotation is not said or thought by a Character, such as a quoted word or title; 'Unknown' only if no "
    "listed Character fits), the kind (speech said aloud, thought, or written text being read or quoted), the "
    "emotion of the delivery, and its intensity. In a back-and-forth with no speaker tags, speakers usually alternate. "
    "If the narration is first person, lines said or thought by the narrating Character get that Character's name, "
    "never 'Narrator'. A line marked [number = Name] already has its speaker; keep that name. "
    "Label every numbered line exactly once, in order.")


def cast_pass(parts):
    """Pass 1: the global Character and alias list, updated chunk by chunk."""
    cast = {"narrator": {"person": "third", "character": ""}, "characters": []}
    for part in parts:
        cast = llm.chat(CHAR_SYSTEM, "LIST SO FAR:\n" + json.dumps(cast, ensure_ascii=False)
                        + "\n\nNEXT PART OF THE TEXT:\n" + llm.render(part, mark_quotes=False), CHAR_SCHEMA, 1500)
    narr = cast["narrator"]
    if narr["person"] == "first" and narr["character"] and narr["character"] not in [c["name"] for c in cast["characters"]]:
        cast["characters"].insert(0, {"name": narr["character"], "aliases": [], "gender": "unknown", "age": "unknown"})
    return cast


def attribution_pass(parts, cast, anchors=None):
    """Pass 2: Speaker and Emotion for every quote. anchors: quote id -> Speaker already known."""
    names = [c["name"] for c in cast["characters"]]
    roster = "\n".join(f"- {c['name']} ({c['gender']}, {c['age']}); also called: {', '.join(c['aliases']) or '-'}"
                       for c in cast["characters"])
    narr = cast["narrator"]
    roster += (f"\nThe narration is first person; the narrator is {narr['character']}."
               if narr["person"] == "first" else "\nThe narration is third person.")
    schema = {"type": "object", "required": ["lines"], "additionalProperties": False, "properties": {"lines": {
        "type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["id", "speaker", "kind", "emotion", "intensity"], "properties": {
                "id": {"type": "integer"}, "speaker": {"type": "string", "enum": names + ["Narrator", "Unknown"]},
                "kind": {"type": "string", "enum": ["speech", "thought", "written"]},
                "emotion": {"type": "string", "enum": llm.EMOTIONS},
                "intensity": {"type": "string", "enum": ["low", "medium", "high"]}}}}}}
    labels, prev_tail = {}, ""
    for part in parts:
        ids = [l["id"] for l in part if l["kind"] == "quote"]
        if ids:
            user = (f"CHARACTERS (allowed speakers, plus Narrator and Unknown):\n{roster}\n\n"
                    + (f"TEXT JUST BEFORE (for context, do not label):\n{prev_tail}\n\n" if prev_tail else "")
                    + f"TEXT TO LABEL:\n{llm.render(part, anchors=anchors)}\n\n"
                    + f"Label lines {ids[0]} to {ids[-1]} ({len(ids)} lines).")
            for rec in llm.chat(ATTR_SYSTEM, user, schema, 6000)["lines"]:
                if rec["id"] in ids:
                    lab = {k: rec[k] for k in ("speaker", "kind", "emotion", "intensity")}
                    if anchors and rec["id"] in anchors:
                        lab["speaker"], lab["source"] = anchors[rec["id"]], "booknlp"
                    labels.setdefault(rec["id"], lab)
        prev_tail = " ".join(llm.render(part, mark_quotes=False).split()[-150:])
    return labels


def save(name, stem, lines, cast, labels, t0, before, **extra):
    out = {"approach": name, "passage": stem, "narrator": cast["narrator"], "characters": cast["characters"],
           "labels": labels, "scenes": llm.scenes(lines),
           "missing": [l["id"] for l in lines if l["kind"] == "quote" and l["id"] not in labels], **extra}
    out["seconds"] = round(time.time() - t0 + extra.get("booknlp_seconds", 0), 1)
    out["stats"] = {k: round(llm.STATS[k] - before[k], 1) for k in llm.STATS}
    (ROOT / "scripts" / name).mkdir(parents=True, exist_ok=True)
    (ROOT / "scripts" / name / f"{stem}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(name, stem, "| characters", len(cast["characters"]), "| labelled", len(labels), "| missing", len(out["missing"]),
          "|", {k: v for k, v in extra.items() if k != "booknlp_seconds"}, "|", out["seconds"], "s", flush=True)


def run(stem):
    lines = json.loads((ROOT / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    parts = llm.chunks(lines)
    t0, before = time.time(), dict(llm.STATS)
    cast = cast_pass(parts)
    save(NAME, stem, lines, cast, attribution_pass(parts, cast), t0, before)


if __name__ == "__main__":
    for stem in sys.argv[1:] or sorted(p.stem for p in (ROOT / "lines").glob("*.json")):
        run(stem)
