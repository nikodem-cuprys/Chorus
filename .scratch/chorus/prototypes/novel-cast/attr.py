"""PROTOTYPE, throwaway (M1 ticket 03). Approach B's attribution pass with the Character list of the whole novel
(from cast.py), given to the prompt in two ways:

  full     every Character on the list, every chunk.
  trimmed  only Characters named (by name or alias) in this chunk or the one before, plus the Speakers of the last
           five labelled lines and the chapter's Narrating Character.

  python attr.py score [cast]          chapters 1-2 as the sample passage of ticket 08, scored against its reference
  python attr.py compare [cast] N ...  chapters N ... of the book, full against trimmed (no reference)

[cast] is the cast.py mode whose list is used (default delta). Results go to out/attr/."""
import json, pathlib, re, sys, time
from collections import Counter

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
import approach_b  # noqa: E402
import book  # noqa: E402
import cast as castmod  # noqa: E402
import llm  # noqa: E402
import score  # noqa: E402

EMOTIONS = [e for e in llm.EMOTIONS if e != "disgusted"]  # ticket 16
RECENT_SPEAKERS = 5


PARTICLES = {"de", "of", "the", "van", "von", "du", "la", "le"}


def clean_alias(alias):
    """A name or title, not a copied sentence fragment ("Jane could not have been wearied by...")."""
    words = alias.split()
    return 0 < len(words) <= 4 and all(w[0].isupper() or w.lower() in PARTICLES for w in words)


def load_cast(mode):
    chars = json.loads((ROOT / "out" / mode / "cast.json").read_text(encoding="utf-8"))["cast"]["characters"]
    return [dict(c, aliases=[a for a in c["aliases"] if clean_alias(a)]) for c in chars]


def chapter_narrators(mode):
    """Each chapter's Narrating Character: the majority answer of its chunks in the cast run."""
    votes = {}
    for line in (ROOT / "out" / mode / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        n = rec.get("narrator") or {}
        who = n.get("character", "") if n.get("person") == "first" else ""
        votes.setdefault(rec["chapter"], Counter())[who] += 1
    return {ch: c.most_common(1)[0][0] for ch, c in votes.items()}


def names_of(c):
    return [c["name"], *c["aliases"]]


def mentioned(c, text):
    return any(re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text, re.I) for n in names_of(c) if len(n) > 2)


def roster(characters, narrator):
    text = "\n".join(f"- {c['name']} ({c['gender']}, {c['age']}); also called: {', '.join(c['aliases']) or '-'}"
                     for c in characters)
    text += (f"\nThe narration is first person; the narrator is {narrator}." if narrator
             else "\nThe narration is third person.")
    return text


def label(parts, characters, narrators, trimmed):
    """parts: [(chapter, lines)]. Returns (labels by quote id, per-chunk records)."""
    labels, records, prev_text, recent = {}, [], "", []
    for chapter, part in parts:
        ids = [l["id"] for l in part if l["kind"] == "quote"]
        text = llm.render(part, mark_quotes=False)
        narrator = narrators.get(chapter, "")
        if trimmed:
            keep = {c["name"] for c in characters if mentioned(c, text + " " + prev_text)}
            keep |= set(recent[-RECENT_SPEAKERS:])
            if narrator:
                keep.add(narrator)
            chars = [c for c in characters if c["name"] in keep]
        else:
            chars = characters
        if ids:
            names = [c["name"] for c in chars]
            schema = {"type": "object", "required": ["lines"], "additionalProperties": False, "properties": {"lines": {
                "type": "array", "items": {"type": "object", "additionalProperties": False,
                    "required": ["id", "speaker", "kind", "emotion", "intensity"], "properties": {
                        "id": {"type": "integer"}, "speaker": {"type": "string", "enum": names + ["Narrator", "Unknown"]},
                        "kind": {"type": "string", "enum": ["speech", "thought", "written"]},
                        "emotion": {"type": "string", "enum": EMOTIONS},
                        "intensity": {"type": "string", "enum": ["normal", "strong"]}}}}}}
            user = (f"CHARACTERS (allowed speakers, plus Narrator and Unknown):\n{roster(chars, narrator)}\n\n"
                    + (f"TEXT JUST BEFORE (for context, do not label):\n{prev_text}\n\n" if prev_text else "")
                    + f"TEXT TO LABEL:\n{llm.render(part)}\n\n"
                    + f"Label lines {ids[0]} to {ids[-1]} ({len(ids)} lines).")
            out, rec = castmod.complete(approach_b.ATTR_SYSTEM, user, schema, 6000)
            rec.update(chapter=chapter, quotes=len(ids), roster=len(chars),
                       roster_tokens=len(castmod.post("/tokenize", {"content": roster(chars, narrator)})["tokens"]))
            got = 0
            for item in (out or {}).get("lines", []):
                if item["id"] in ids and str(item["id"]) not in labels:
                    labels[str(item["id"])] = {k: item[k] for k in ("speaker", "kind", "emotion", "intensity")}
                    got += 1
                    if item["speaker"] not in ("Narrator", "Unknown"):
                        recent.append(item["speaker"])
            rec["labelled"] = got
            records.append(rec)
            print(f"  ch{chapter} | roster {len(chars)} ({rec['roster_tokens']} tokens) | prompt {rec['prompt_tokens']} "
                  f"| {got}/{len(ids)} labelled | {rec.get('seconds')} s | {rec.get('error', rec.get('stop'))}",
                  flush=True)
        prev_text = " ".join(text.split()[-150:])
    return labels, records


def save(name, data):
    out = ROOT / "out" / "attr"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def run_score(mode):
    stem = "01-pride-and-prejudice-ch1-2"
    lines = json.loads((ATTR / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
    parts = [(1, p) for p in llm.chunks(lines)]
    characters = load_cast(mode)
    gold, quotes = score.GOLD[stem], [l["id"] for l in lines if l["kind"] == "quote"]
    result = {}
    for trimmed in (False, True):
        name = f"{mode}-{'trimmed' if trimmed else 'full'}"
        print(name, flush=True)
        t = time.time()
        labels, records = label(parts, characters, {}, trimmed)
        wrong = {}
        for i in quotes:
            lab = labels.get(str(i))
            got = score.person(stem, lab["speaker"]) if lab else "(no label)"
            if got not in gold[i]:
                wrong[i] = got
        result[name] = {"right": len(quotes) - len(wrong), "quotes": len(quotes), "wrong": wrong,
                        "seconds": round(time.time() - t), "chunks": records, "labels": labels}
        print(f"{name}: {len(quotes) - len(wrong)}/{len(quotes)} right; wrong: {wrong}", flush=True)
    save(f"score-{mode}", result)


def run_compare(mode, chapters):
    all_lines = book.lines()
    parts = [(ch, p) for ch, p in book.chunks(all_lines) if ch in chapters]
    characters, narrators = load_cast(mode), chapter_narrators(mode)
    text = {str(l["id"]): l["text"] for l in all_lines}
    runs = {}
    for trimmed in (False, True):
        name = "trimmed" if trimmed else "full"
        print(name, flush=True)
        labels, records = label(parts, characters, narrators, trimmed)
        runs[name] = {"labels": labels, "chunks": records}
    ids = sorted(set(runs["full"]["labels"]) | set(runs["trimmed"]["labels"]), key=int)
    differ = [{"id": i, "text": text[i], "full": runs["full"]["labels"].get(i, {}).get("speaker"),
               "trimmed": runs["trimmed"]["labels"].get(i, {}).get("speaker")}
              for i in ids if runs["full"]["labels"].get(i, {}).get("speaker")
              != runs["trimmed"]["labels"].get(i, {}).get("speaker")]
    print(f"chapters {chapters}: {len(ids)} quotes, {len(differ)} differ", flush=True)
    for d in differ:
        print(f"  [{d['id']}] full={d['full']} trimmed={d['trimmed']}: {d['text'][:90]}")
    save(f"compare-{mode}-" + "-".join(map(str, chapters)), {"runs": runs, "differ": differ, "quotes": len(ids)})


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[1] if len(args) > 1 and not args[1].isdigit() else "delta"
    if args[0] == "score":
        run_score(mode)
    else:
        run_compare(mode, [int(a) for a in args[1:] if a.isdigit()])
