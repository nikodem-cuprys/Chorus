"""PROTOTYPE, throwaway. Approach A: BookNLP plus the LLM. BookNLP (CPU) finds Character clusters and attributes
quotes; the LLM turns the clusters into a clean Character list, and BookNLP's attribution is kept only where the
speaker is mentioned in the quote's own paragraph (an explicit tag). The LLM labels the rest, and Emotion for all.
Run booknlp_run.py first. Run with any Python 3: python approach_a.py [passage-stem ...]"""
import json, pathlib, sys, time
import llm
from approach_b import ATTR_SYSTEM

ROOT = pathlib.Path(__file__).parent
NAME = "a-booknlp-llm"

CAST_SCHEMA = {"type": "object", "required": ["narrator", "characters"], "additionalProperties": False, "properties": {
    "narrator": {"type": "object", "additionalProperties": False, "required": ["person", "character"], "properties": {
        "person": {"type": "string", "enum": ["first", "third"]}, "character": {"type": "string"}}},
    "characters": {"type": "array", "maxItems": 30, "items": {"type": "object", "additionalProperties": False,
        "required": ["name", "aliases", "gender", "age", "clusters"], "properties": {
            "name": {"type": "string"}, "aliases": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
            "gender": {"type": "string", "enum": ["female", "male", "unknown"]},
            "age": {"type": "string", "enum": ["child", "young adult", "adult", "elderly", "unknown"]},
            "clusters": {"type": "array", "items": {"type": "integer"}}}}}}}

CAST_SYSTEM = (
    "A tool has grouped the mentions of people in a work of fiction into numbered clusters. Each cluster lists the "
    "names, descriptions and pronouns used for one person, with counts. The tool often splits one person over several "
    "clusters. Build the list of Characters: give each one canonical name, the other ways they are referred to as "
    "aliases, gender, age if it can be told, and the numbers of all clusters that are this person. Leave out clusters "
    "that are not a specific person. A cluster made mostly of 'I', 'me', 'my' is the first-person narrator: say the "
    "narration is first person and give that Character's canonical name in 'character' (use the name others call "
    "them if any cluster shows it, else 'the narrator'); otherwise the narration is third person and 'character' is ''.")


def run(stem):
    lines = json.loads((ROOT / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    bn = json.loads((ROOT / "booknlp" / f"{stem}.json").read_text(encoding="utf-8"))
    t0, before = time.time(), dict(llm.STATS)
    clusters = "\n".join(
        f"cluster {c['id']} ({c['count']} mentions, {c['gender'] or 'gender unknown'}): "
        + "; ".join(f"{n} x{k}" for n, k in c["proper"] + c["common"] + c["pronoun"])
        for c in bn["characters"] if c["count"] >= 2)
    cast = llm.chat(CAST_SYSTEM, clusters, CAST_SCHEMA, 1500)
    names = [c["name"] for c in cast["characters"]]
    by_cluster = {cid: c["name"] for c in cast["characters"] for cid in c["clusters"]}
    anchors = {int(i): by_cluster[q["char_id"]] for i, q in bn["quotes"].items()
               if q["same_paragraph"] and q["char_id"] in by_cluster}
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
    for part in llm.chunks(lines):
        ids = [l["id"] for l in part if l["kind"] == "quote"]
        if ids:
            user = (f"CHARACTERS (allowed speakers, plus Narrator and Unknown):\n{roster}\n\n"
                    + (f"TEXT JUST BEFORE (for context, do not label):\n{prev_tail}\n\n" if prev_tail else "")
                    + f"TEXT TO LABEL:\n{llm.render(part, anchors=anchors)}\n\n"
                    + f"Label lines {ids[0]} to {ids[-1]} ({len(ids)} lines).")
            for rec in llm.chat(ATTR_SYSTEM, user, schema, 6000)["lines"]:
                if rec["id"] in ids:
                    lab = {k: rec[k] for k in ("speaker", "kind", "emotion", "intensity")}
                    if rec["id"] in anchors:
                        lab["speaker"], lab["source"] = anchors[rec["id"]], "booknlp"
                    labels.setdefault(rec["id"], lab)
        prev_tail = " ".join(llm.render(part, mark_quotes=False).split()[-150:])
    out = {"approach": NAME, "passage": stem, "narrator": cast["narrator"], "characters": cast["characters"],
           "labels": labels, "scenes": llm.scenes(lines), "anchored": len(anchors),
           "missing": [l["id"] for l in lines if l["kind"] == "quote" and l["id"] not in labels],
           "seconds": round(time.time() - t0 + bn["seconds"], 1), "booknlp_seconds": bn["seconds"],
           "stats": {k: round(llm.STATS[k] - before[k], 1) for k in llm.STATS}}
    (ROOT / "scripts" / NAME).mkdir(parents=True, exist_ok=True)
    (ROOT / "scripts" / NAME / f"{stem}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(stem, "| characters", len(names), "| anchored by BookNLP", len(anchors), "| labelled", len(labels),
          "| missing", len(out["missing"]), "|", out["seconds"], "s", flush=True)


if __name__ == "__main__":
    for stem in sys.argv[1:] or sorted(p.stem for p in (ROOT / "lines").glob("*.json")):
        run(stem)
