"""PROTOTYPE, throwaway (ticket 18). Which lines should the review queue ask about?
Scores ways of picking queue lines against the 21 lines approach B got wrong on the six sample passages
(reference labels from ticket 08's score.py, made by Claude, not by the user).
Each rule looks only at what Chorus has at that point: the text, the Character list and the labels.
Run with any Python 3: python rules.py"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
from score import GOLD, person  # noqa: E402

SAID = (r"said|says|cried|replied|asked|answered|thought|returned|continued|whispered|called|exclaimed|remarked|"
        r"added|observed|began|repeated|interrupted|shouted|muttered|went on|inquired|demanded|pleaded|sighed")


def load():
    out = []
    for f in sorted((ATTR / "lines").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        s = json.loads((ATTR / "scripts" / "b-llm-only" / f.name).read_text(encoding="utf-8"))
        stem, gold = d["passage"], GOLD[d["passage"]]
        doubt_f = ROOT / "doubt" / f.name
        doubt = json.loads(doubt_f.read_text(encoding="utf-8")) if doubt_f.exists() else None
        for l in d["lines"]:
            if l["kind"] == "quote":
                lab = s["labels"].get(str(l["id"]))
                l["label"] = lab
                l["wrong"] = not (lab and person(stem, lab["speaker"]) in gold[l["id"]])
        rerun_f = ROOT / "rerun" / f.name
        rerun = json.loads(rerun_f.read_text(encoding="utf-8")) if rerun_f.exists() else None
        out.append(dict(stem=stem, lines=d["lines"], cast=s["characters"], narrator=s["narrator"], doubt=doubt,
                        rerun=rerun))
    return out


PRON = re.compile(r"^(you|he|she|her|him|his|i|me|my dear|they|them|it|we|us)$", re.I)


def names_of(c):
    # pronoun aliases dropped, as the ticket 09 prototype does
    return [n for n in [c["name"], *c["aliases"]] if len(n) > 2 and not PRON.match(n)]


def mentions(text, c):
    return any(re.search(r"\b" + re.escape(n) + r"\b", text, re.I) for n in names_of(c))


def context(p):
    """Per paragraph: its narration, and how deep it is in a run of paragraphs with speech and no narration."""
    paras, order = {}, []
    for l in p["lines"]:
        if l["para"] not in paras:
            order.append(l["para"])
        paras.setdefault(l["para"], []).append(l)
    run, run_at = 0, {}
    for q in order:
        has_narr = any(l["kind"] == "narration" and l["text"].strip() for l in paras[q])
        has_speech = any(l["kind"] == "quote" for l in paras[q])
        run = 0 if has_narr or not has_speech else run + 1
        run_at[q] = run
    return paras, order, run_at


# ---- rules: each returns the set of quote ids it would ask about ----

def r_no_speaker(p):
    cast = {c["name"] for c in p["cast"]}
    return {l["id"] for l in quotes(p) if not l["label"] or l["label"]["speaker"] == "Unknown"
            or (l["label"]["speaker"] not in cast and l["label"]["speaker"] != "Narrator")}


def r_narrator(p):
    return {l["id"] for l in quotes(p) if l["label"] and l["label"]["speaker"] == "Narrator"}


def r_thought(p):
    return {l["id"] for l in quotes(p) if l["label"] and l["label"]["kind"] == "thought"}


def r_mentions_self(p):
    by = {c["name"]: c for c in p["cast"]}
    return {l["id"] for l in quotes(p) if l["label"] and l["label"]["speaker"] in by
            and mentions(l["text"], by[l["label"]["speaker"]])}


def r_untagged_run(p, depth=4):
    _, _, run_at = context(p)
    return {l["id"] for l in quotes(p) if run_at[l["para"]] >= depth}


def tagged_speaker(p, paras, l):
    """A Character named next to a speech verb in the narration of the line's own paragraph, if exactly one."""
    narr = " ".join(x["text"] for x in paras[l["para"]] if x["kind"] == "narration")
    hits = set()
    for c in p["cast"]:
        for n in names_of(c):
            n = re.escape(n)
            if re.search(rf"\b(?:{SAID})\s+(?:the\s+)?{n}\b|\b{n}\s+(?:\w+\s+)?(?:{SAID})\b", narr, re.I):
                hits.add(c["name"])
    return hits.pop() if len(hits) == 1 else None


def r_tag_conflict(p):
    """The paragraph's own narration says "said X", and the label is someone else."""
    paras, _, _ = context(p)
    out = set()
    for l in quotes(p):
        t = tagged_speaker(p, paras, l)
        if t and l["label"] and l["label"]["speaker"] != t:
            out.add(l["id"])
    return out


def r_same_twice(p, both=False):
    """Two paragraphs in a row with speech from the same Speaker, the second with no narration at all:
    in an untagged exchange speakers should alternate."""
    paras, order, _ = context(p)
    out, prev, prev_ids = set(), None, set()
    for q in order:
        qs = [l for l in paras[q] if l["kind"] == "quote" and l["label"]]
        if not qs:
            if any(l["text"].strip() for l in paras[q]):
                prev = None  # a paragraph of pure narration breaks the exchange
            continue
        sp = {l["label"]["speaker"] for l in qs}
        bare = not any(l["kind"] == "narration" and l["text"].strip() for l in paras[q])
        if bare and prev and len(sp) == 1 and sp == prev:
            out |= {l["id"] for l in qs} | (prev_ids if both else set())
        prev, prev_ids = (sp if len(sp) == 1 else None), {l["id"] for l in qs}
    return out


def r_new_untagged(p):
    """A paragraph with no narration brings in a Speaker who is neither of the last two Speakers:
    nobody announced them."""
    paras, order, _ = context(p)
    out, last = set(), []
    for q in order:
        qs = [l for l in paras[q] if l["kind"] == "quote" and l["label"]]
        if not qs:
            continue
        bare = not any(l["kind"] == "narration" and l["text"].strip() for l in paras[q])
        for l in qs:
            sp = l["label"]["speaker"]
            if bare and len(last) == 2 and sp not in last and sp not in ("Narrator", "Unknown"):
                out.add(l["id"])
            if sp not in last:
                last = (last + [sp])[-2:]
    return out


def r_inline_fragment(p, words=3):
    """A short quotation in the middle of a narration sentence ("he called me 'Rat!'", a scare-quoted word)."""
    paras, _, _ = context(p)
    out = set()
    for q, ls in paras.items():
        for i, l in enumerate(ls):
            if l["kind"] != "quote" or len(l["text"].split()) > words or i == 0:
                continue
            before = ls[i - 1]
            if before["kind"] == "narration" and before["text"].strip() and not re.search(r"[.!?:;,—-]\s*$", before["text"].strip()):
                out.add(l["id"])
    return out


def r_addresses_self(p):
    """The line addresses its own Speaker by name (a name set off by commas), stricter than a mention."""
    by = {c["name"]: c for c in p["cast"]}
    out = set()
    for l in quotes(p):
        c = by.get(l["label"]["speaker"]) if l["label"] else None
        if c and any(re.search(rf"(?:^|[,“\"]\s*){re.escape(n)}\s*[,!?.]|,\s*{re.escape(n)}\b", l["text"], re.I)
                     for n in names_of(c)):
            out.add(l["id"])
    return out


def r_first_lines(p, n=3):
    """The first few quoted lines of a Work: the Character list is thinnest there."""
    return {l["id"] for l in quotes(p)[:n]}


def r_group(p):
    """The narration around the line gives it to several people ("they cried", "the three")."""
    paras, _, _ = context(p)
    out = set()
    for l in quotes(p):
        narr = " ".join(x["text"] for x in paras[l["para"]] if x["kind"] == "narration")
        if re.search(rf"\b(they|both|all|the (?:two|three|others))\s+(?:\w+\s+)?(?:{SAID})\b", narr, re.I):
            out.add(l["id"])
    return out


def r_rare_speaker(p, n=2):
    """Lines of a Speaker with at most n lines in the whole Work."""
    count = {}
    for l in quotes(p):
        if l["label"]:
            count[l["label"]["speaker"]] = count.get(l["label"]["speaker"], 0) + 1
    return {l["id"] for l in quotes(p) if l["label"] and l["label"]["speaker"] not in ("Narrator", "Unknown")
            and count[l["label"]["speaker"]] <= n}


def r_llm_doubt(p, level="unsure"):
    """Second pass: the model rated its own label (doubt.py). Missing ratings count as doubt."""
    if p["doubt"] is None:
        return set()
    d = p["doubt"]["lines"]
    bad = {"unsure", "wrong"} if level == "unsure" else {"wrong"}
    return {l["id"] for l in quotes(p) if d.get(str(l["id"]), {}).get("verdict", "unsure") in bad}


def r_llm_disagrees(p):
    """Second pass named a different Speaker than the first."""
    if p["doubt"] is None:
        return set()
    d = p["doubt"]["lines"]
    return {l["id"] for l in quotes(p) if l["label"] and d.get(str(l["id"]), {}).get("speaker")
            not in (None, l["label"]["speaker"])}


def r_rerun_differs(p):
    """A blind second labelling run in smaller chunks (rerun.py) named a different Speaker, or none."""
    if p["rerun"] is None:
        return set()
    r = p["rerun"]["labels"]
    return {l["id"] for l in quotes(p) if l["label"] and r.get(str(l["id"]), {}).get("speaker") != l["label"]["speaker"]}


def quotes(p):
    return [l for l in p["lines"] if l["kind"] == "quote"]


RULES = {
    "no Speaker found": r_no_speaker, "quote given to the Narrator": r_narrator, "marked as a thought": r_thought,
    "mentions its own Speaker": r_mentions_self, "untagged run, 4 deep": r_untagged_run,
    "narration tags someone else": r_tag_conflict, "same Speaker twice in a row": r_same_twice,
    "same Speaker twice, both lines": lambda p: r_same_twice(p, both=True),
    "new Speaker with no tag": r_new_untagged, "short quote inside narration": r_inline_fragment,
    "addresses its own Speaker": r_addresses_self, "first 3 lines of the Work": r_first_lines,
    "narration gives it to a group": r_group, "Speaker with 1-2 lines": r_rare_speaker,
    "model: unsure or wrong": r_llm_doubt, "model: wrong only": lambda p: r_llm_doubt(p, "wrong"),
    "model: names another Speaker": r_llm_disagrees, "second run disagrees": r_rerun_differs,
}
TICKET_09 = ["no Speaker found", "quote given to the Narrator", "marked as a thought", "mentions its own Speaker",
             "untagged run, 4 deep"]
STRATEGIES = {
    "ticket 09's rules": TICKET_09,
    "text rules, tight": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                          "same Speaker twice in a row", "addresses its own Speaker"],
    "text rules, tight + group": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                                  "same Speaker twice in a row", "addresses its own Speaker",
                                  "narration gives it to a group"],
    "text rules, wide": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                         "same Speaker twice, both lines", "addresses its own Speaker", "new Speaker with no tag",
                         "short quote inside narration"],
    "model doubt only": ["model: unsure or wrong"],
    "model disagreement only": ["model: names another Speaker"],
    "tight + model disagreement": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                                   "same Speaker twice in a row", "addresses its own Speaker",
                                   "model: names another Speaker"],
    "second run only": ["second run disagrees"],
    "tight + second run": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                           "same Speaker twice in a row", "addresses its own Speaker", "second run disagrees"],
    "wide + second run": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                          "same Speaker twice, both lines", "addresses its own Speaker", "new Speaker with no tag",
                          "short quote inside narration", "second run disagrees"],
    "tight + model doubt": ["no Speaker found", "quote given to the Narrator", "narration tags someone else",
                            "same Speaker twice in a row", "addresses its own Speaker", "model: unsure or wrong"],
}


def evaluate(passages):
    flagged = {name: {p["stem"]: fn(p) for p in passages} for name, fn in RULES.items()}
    wrong = {p["stem"]: {l["id"] for l in quotes(p) if l["wrong"]} for p in passages}
    n_quotes, n_wrong = sum(len(quotes(p)) for p in passages), sum(len(w) for w in wrong.values())
    rows = []
    for name in RULES:
        asked = sum(len(v) for v in flagged[name].values())
        hit = sum(len(flagged[name][s] & wrong[s]) for s in wrong)
        rows.append((name, asked, hit))
    strat = []
    for name, rules in STRATEGIES.items():
        asked = {s: set().union(*(flagged[r][s] for r in rules)) for s in wrong}
        missed = {s: sorted(wrong[s] - asked[s]) for s in wrong if wrong[s] - asked[s]}
        strat.append((name, sum(len(a) for a in asked.values()), sum(len(asked[s] & wrong[s]) for s in wrong), missed))
    return n_quotes, n_wrong, rows, strat


if __name__ == "__main__":
    P = load()
    n_quotes, n_wrong, rows, strat = evaluate(P)
    print(f"{n_quotes} quoted lines, {n_wrong} wrong. Self-check present: {all(p['doubt'] for p in P)}; second run present: {all(p['rerun'] for p in P)}\n")
    print(f"{'rule':34} asked  catches  wasted")
    for name, asked, hit in rows:
        print(f"{name:34} {asked:5} {hit:8} {asked - hit:7}")
    print(f"\n{'strategy':34} questions  catches  missed")
    for name, asked, hit, missed in strat:
        print(f"{name:34} {asked:9} {hit:5}/{n_wrong}  {missed}")
