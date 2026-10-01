"""PROTOTYPE, throwaway. Approach A: BookNLP plus the LLM. The Character list comes from the text, exactly as in
approach B. BookNLP (CPU) then supplies the Speaker for every quote whose speaker it finds in the quote's own
paragraph (an explicit tag); its clusters are matched to the Character list by name, and a tagged speaker the list
missed is added to it. The LLM labels the remaining quotes, and Emotion for all.
(A first variant that built the Character list from BookNLP's clusters alone is in rejected/.)
Run booknlp_run.py first. Run with any Python 3: python approach_a.py [passage-stem ...]"""
import json, pathlib, re, sys, time
import llm
from approach_b import cast_pass, attribution_pass, save

ROOT = pathlib.Path(__file__).parent
NAME = "a-booknlp-llm"
PRONOUNS = {"i", "me", "my", "you", "your", "he", "him", "his", "she", "her", "they", "them", "their", "we", "us", "our", "it"}


def norm(s):
    return re.sub(r"^(the|a|an|my|his|her|their|our|your) ", "", re.sub(r"[^a-z ]", "", s.lower()).strip())


def match_clusters(bn, cast):
    """BookNLP cluster id -> Character name, by shared names; unmatched named clusters keep their own top name."""
    keys = {c["name"]: {norm(c["name"])} | {norm(a) for a in c["aliases"] if norm(a) not in PRONOUNS} for c in cast["characters"]}
    narr = cast["narrator"]
    out, fresh = {}, {}
    for cl in bn["characters"]:
        named = [(norm(n), k) for n, k in cl["proper"] + cl["common"]]
        score = {name: sum(k for n, k in named if n in ks) for name, ks in keys.items()}
        best = max(score, key=score.get) if score else None
        if best and score[best] > 0:
            out[cl["id"]] = best
        elif not named and narr["person"] == "first" and narr["character"] and \
                sum(k for n, k in cl["pronoun"] if n.lower() in ("i", "me", "my")) >= max(3, cl["count"] // 2):
            out[cl["id"]] = narr["character"]  # the first-person narrator's own cluster
        elif named:
            fresh[cl["id"]] = (cl["proper"] + cl["common"])[0][0]
    return out, fresh


def resolve(phrase, lines, quote_id, cast):
    """Is this tagged speaker one of the listed Characters under another name, or a new Character?"""
    para = next(l["para"] for l in lines if l["id"] == quote_id)
    context = llm.render([l for l in lines if para - 2 <= l["para"] <= para], mark_quotes=False)
    names = [c["name"] for c in cast["characters"]]
    schema = {"type": "object", "required": ["same_as", "short_name"], "additionalProperties": False, "properties": {
        "same_as": {"type": "string", "enum": names + ["new"]}, "short_name": {"type": "string", "maxLength": 40}}}
    res = llm.chat("In the passage, a speaker is referred to by the given phrase. Decide whether this is one of the "
                   "listed Characters under another name (for example 'her mother' for a named mother). Answer with "
                   "that Character's name in 'same_as', or 'new' if it is somebody not on the list. In 'short_name' "
                   "give a short name for the speaker, at most four words.",
                   f"CHARACTERS: {'; '.join(names)}\n\nPHRASE: {phrase}\n\nPASSAGE:\n{context}", schema, 60)
    return res["same_as"] if res["same_as"] != "new" else (res["short_name"].strip() or phrase)


def run(stem):
    lines = json.loads((ROOT / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    bn = json.loads((ROOT / "booknlp" / f"{stem}.json").read_text(encoding="utf-8"))
    parts = llm.chunks(lines)
    t0, before = time.time(), dict(llm.STATS)
    cast = cast_pass(parts)
    known, fresh = match_clusters(bn, cast)
    genders = {c["id"]: {"she/her": "female", "he/him/his": "male"}.get(c["gender"], "unknown") for c in bn["characters"]}
    anchors, added, resolved = {}, [], {}
    for i, q in bn["quotes"].items():
        if not q["same_paragraph"]:
            continue
        cid = q["char_id"]
        if cid in fresh and cid not in resolved:  # a tagged speaker the Character list has no name for
            resolved[cid] = resolve(fresh[cid], lines, int(i), cast)
            if resolved[cid] not in [c["name"] for c in cast["characters"]]:
                cast["characters"].append({"name": resolved[cid], "aliases": [fresh[cid]][:1], "gender": genders[cid], "age": "unknown"})
                added.append(resolved[cid])
        name = known.get(cid) or resolved.get(cid)
        if name:
            anchors[int(i)] = name
    labels = attribution_pass(parts, cast, anchors)
    save(NAME, stem, lines, cast, labels, t0, before, anchored=len(anchors), added_characters=added,
         booknlp_seconds=bn["seconds"])


if __name__ == "__main__":
    for stem in sys.argv[1:] or sorted(p.stem for p in (ROOT / "lines").glob("*.json")):
        run(stem)
