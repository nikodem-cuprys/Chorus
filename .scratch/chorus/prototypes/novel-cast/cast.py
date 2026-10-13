"""PROTOTYPE, throwaway (M1 ticket 03). The Character pass of approach B over the whole of Pride and Prejudice, through
the llama.cpp server of ticket 24 (one slot, 8k context, temperature 0, thinking off), in two forms:

  full   approach B as prototyped: each chunk the model returns the whole updated list (the Character cap
         raised from 30 to 200; aliases stay capped at 8).
  delta  each chunk the model sees the list so far, compactly, and returns only Characters who are new and new
         aliases of listed ones; the code checks and merges them in. An alias is kept only if it appears in the
         chunk, reads like a name (starts with a capital, no pronoun, no list), and is not already another
         Character's name or alias. (A rule that a new Character's name must appear in the chunk was dropped: it
         refused Mrs. Bennet, whom chapter 1 only calls "his lady".) (The first
         delta run, without these checks, is kept in out/delta-v1: by chunk 24 Jane was an alias of Elizabeth.)

Every chunk is logged to out/<mode>/chunks.jsonl and the list saved, so a run resumes where it stopped.
Run with any Python 3: python cast.py full|delta [--limit N]"""
import json, pathlib, re, sys, time, urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT.parent / "attribution"))
import approach_b  # noqa: E402
import book  # noqa: E402
import llm  # noqa: E402

SERVER = "http://127.0.0.1:8080"
CTX = 8192
TIMEOUT = 1800


def post(path, body):
    req = urllib.request.Request(SERVER + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def prompt(system, user):
    # ChatML with an empty think block, as in tickets 08 and 24
    return (f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n\n</think>\n\n")


def complete(system, user, schema, max_tokens):
    """One request. Returns (parsed or None, record). max_tokens is cut to what is left of the 8k context."""
    text = prompt(system, user)
    n_prompt = len(post("/tokenize", {"content": text})["tokens"])
    budget = min(max_tokens, CTX - n_prompt - 8)
    rec = {"prompt_tokens": n_prompt, "budget": budget}
    if budget < 64:
        rec["error"] = "context full"
        return None, rec
    t = time.time()
    res = post("/completion", {"prompt": text, "n_predict": budget, "temperature": 0, "json_schema": schema,
                               "cache_prompt": False})
    tm = res["timings"]
    rec.update(seconds=round(time.time() - t, 1), completion_tokens=tm["predicted_n"],
               tokens_per_second=round(tm["predicted_per_second"], 2), stop=res.get("stop_type"),
               truncated=res.get("truncated"))
    try:
        return json.loads(res["content"]), rec
    except json.JSONDecodeError:
        rec["error"] = "output cut off or not JSON"
        return None, rec


# ---- full: approach B's own prompt and schema, caps raised ----

def full_schema():
    schema = json.loads(json.dumps(approach_b.CHAR_SCHEMA))
    chars = schema["properties"]["characters"]
    chars["maxItems"] = 200
    # aliases stay at the prototype's 8: at 12 the model pads every list with "he" and "one of them"
    return schema


def full_step(cast, part):
    user = ("LIST SO FAR:\n" + json.dumps(cast, ensure_ascii=False)
            + "\n\nNEXT PART OF THE TEXT:\n" + llm.render(part, mark_quotes=False))
    out, rec = complete(approach_b.CHAR_SYSTEM, user, full_schema(), 6000)
    if out is None:
        return cast, None, rec
    narrator = out["narrator"]
    return {"narrator": narrator, "characters": out["characters"]}, narrator, rec


# ---- delta: only what is new ----

DELTA_SYSTEM = (
    "You maintain the list of Characters of a work of fiction. A Character is a person (or creature) who speaks or "
    "thinks at least one quoted line. You get the list so far (one Character per line: canonical name, gender, age, "
    "then the other ways the text refers to them) and the next part of the text. Return only what is new in this "
    "part: Characters who speak or think a quoted line here and are not on the list under any name, and new aliases "
    "for Characters already on the list. An alias is another name or title the text uses for that person, written "
    "exactly as in the text (a first name, a surname with a title, a nickname, such as 'Lizzy' or 'Miss Bennet'); "
    "never a pronoun, a description such as 'her sister', or a word that names a different person. If the list is "
    "empty, every speaking Character in this part is new. Return an empty list only when nothing is new. Never add a "
    "person "
    "who is already listed under another name: give the new name as an alias instead. For an alias, use the "
    "canonical name exactly as listed. Say whether the narration of this part is in the first or third person; if "
    "first person, 'character' is the canonical name of the narrating Character, else ''.")

DELTA_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["narrator", "new_characters", "new_aliases"],
                "properties": {
                    "narrator": approach_b.CHAR_SCHEMA["properties"]["narrator"],
                    "new_characters": {"type": "array", "maxItems": 15, "items": {
                        "type": "object", "additionalProperties": False, "required": ["name", "aliases", "gender", "age"],
                        "properties": approach_b.CHAR_SCHEMA["properties"]["characters"]["items"]["properties"]}},
                    "new_aliases": {"type": "array", "maxItems": 15, "items": {
                        "type": "object", "additionalProperties": False, "required": ["name", "aliases"],
                        "properties": {"name": {"type": "string"},
                                       "aliases": {"type": "array", "maxItems": 8, "items": {"type": "string"}}}}}}}


def roster_text(characters):
    return "\n".join(f"- {c['name']} ({c['gender']}, {c['age']}): {', '.join(c['aliases']) or '-'}"
                     for c in characters) or "(empty)"


PRONOUNS = {"he", "she", "him", "her", "his", "hers", "they", "them", "their", "you", "your", "i", "me", "my", "we",
            "us", "our", "it", "its", "this", "that"}


def in_text(name, text):
    return re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I) is not None


def alias_refused(alias, text):
    """Why an alias is refused, or None."""
    a = alias.strip()
    if len(a) < 2 or "," in a or a.lower() in PRONOUNS or not a[0].isupper():
        return "not a name"
    if not in_text(a, text):
        return "not in the chunk"
    return None


def delta_step(cast, part):
    text = llm.render(part, mark_quotes=False)
    user = "LIST SO FAR:\n" + roster_text(cast["characters"]) + "\n\nNEXT PART OF THE TEXT:\n" + text
    out, rec = complete(DELTA_SYSTEM, user, DELTA_SCHEMA, 1500)
    if out is None:
        return cast, None, rec
    chars = [dict(c, aliases=list(c["aliases"])) for c in cast["characters"]]
    by_name = {c["name"].lower(): c for c in chars}
    known = {a.lower(): c for c in chars for a in [c["name"], *c["aliases"]]}
    added, merged, unmatched, refused = [], 0, [], Counter()

    def add_alias(target, alias):
        why = alias_refused(alias, text)
        if why is None and alias.lower() in known and known[alias.lower()] is not target:
            why = "names someone else"
        if why:
            refused[why] += 1
        elif alias.lower() not in known:
            target["aliases"].append(alias.strip())
            known[alias.lower()] = target

    for new in out["new_characters"]:
        hit = known.get(new["name"].lower())
        if hit:  # the model re-listed a known person: keep the list unique
            merged += 1
            for a in new["aliases"]:
                add_alias(hit, a)
            continue
        c = dict(new, aliases=[])
        chars.append(c)
        by_name[c["name"].lower()] = c
        known[c["name"].lower()] = c
        for a in new["aliases"]:
            add_alias(c, a)
        added.append(c["name"])
    for item in out["new_aliases"]:
        target = by_name.get(item["name"].lower()) or known.get(item["name"].lower())
        if not target:
            unmatched.append(item["name"])
            continue
        for a in item["aliases"]:
            add_alias(target, a)
    rec.update(added=added, relisted=merged, unmatched_alias_targets=unmatched, refused=dict(refused))
    return {"narrator": out["narrator"], "characters": chars}, out["narrator"], rec


def run(mode, limit=None):
    out = ROOT / "out" / mode
    out.mkdir(parents=True, exist_ok=True)
    log, state_file = out / "chunks.jsonl", out / "cast.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else \
        {"done": 0, "cast": {"narrator": {"person": "third", "character": ""}, "characters": []}}
    parts = book.chunks(book.lines())
    step = full_step if mode == "full" else delta_step
    for i in range(state["done"], len(parts) if limit is None else min(len(parts), limit)):
        chapter, part = parts[i]
        cast, narrator, rec = step(state["cast"], part)
        chars = cast["characters"]
        rec.update(chunk=i, chapter=chapter, words=sum(len(l["text"].split()) for l in part),
                   characters=len(chars), aliases=sum(len(c["aliases"]) for c in chars),
                   narrator=narrator, at=round(time.time()))
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        state = {"done": i + 1, "cast": cast}
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{mode} chunk {i + 1}/{len(parts)} ch{chapter} | chars {len(chars)} | prompt {rec['prompt_tokens']} "
              f"| out {rec.get('completion_tokens')} | {rec.get('seconds')} s | {rec.get('error', rec.get('stop'))}",
              flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    run(args[0], limit)
