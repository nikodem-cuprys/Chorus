"""PROTOTYPE, throwaway. Run BookNLP (MIT, English only, CPU) on every sample passage and map its quote
attributions back to our line ids. Writes booknlp/<passage>.json. Run with the booknlp env: python booknlp_run.py"""
import csv, json, pathlib, sys, time
from booknlp.booknlp import BookNLP

ROOT = pathlib.Path(__file__).parent
WORK = ROOT / "booknlp"
WORK.mkdir(exist_ok=True)
csv.field_size_limit(10**9)


def tsv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


model = BookNLP("en", {"pipeline": "entity,quote,coref", "model": "big"})
for f in sorted((ROOT / "lines").glob("*.json")):
    stem = f.stem
    if sys.argv[1:] and stem not in sys.argv[1:]:
        continue
    lines = json.loads(f.read_text(encoding="utf-8"))["lines"]
    text, spans, para = "", [], None
    for l in lines:  # rebuild the text and remember where each line sits in it
        text += ("\n\n" if para is not None and l["para"] != para else (" " if text else ""))
        para = l["para"]
        spans.append((len(text), len(text) + len(l["text"]), l))
        text += l["text"]
    (WORK / f"{stem}.txt").write_text(text, encoding="utf-8")
    t = time.time()
    model.process(str(WORK / f"{stem}.txt"), str(WORK / stem), stem)
    secs = round(time.time() - t, 1)
    tokens = tsv(WORK / stem / f"{stem}.tokens")
    start = {int(t["token_ID_within_document"]): int(t["byte_onset"]) for t in tokens}
    end = {int(t["token_ID_within_document"]): int(t["byte_offset"]) for t in tokens}
    para_of = {int(t["token_ID_within_document"]): int(t["paragraph_ID"]) for t in tokens}
    ents = {(int(e["start_token"]), int(e["end_token"])): e for e in tsv(WORK / stem / f"{stem}.entities")}
    quotes = {}
    for q in tsv(WORK / stem / f"{stem}.quotes"):
        qs, qe = start[int(q["quote_start"])], end[int(q["quote_end"])]
        hits = [l for a, b, l in spans if l["kind"] == "quote" and a < qe and qs < b]
        ms, me = int(q["mention_start"]), int(q["mention_end"])
        ent = ents.get((ms, me), {})
        for l in hits:
            quotes[l["id"]] = {"char_id": int(q["char_id"]), "mention": q["mention_phrase"],
                               "mention_type": ent.get("prop", ""),  # PROP name, NOM description, PRON pronoun
                               "same_paragraph": ms >= 0 and para_of.get(ms) == para_of.get(int(q["quote_start"]))}
    book = json.loads((WORK / stem / f"{stem}.book").read_text(encoding="utf-8"))
    chars = [{"id": c["id"], "count": c["count"], "gender": (c.get("g") or {}).get("argmax") if c.get("g") else None,
              "proper": [(m["n"], m["c"]) for m in c["mentions"]["proper"][:6]],
              "common": [(m["n"], m["c"]) for m in c["mentions"]["common"][:6]],
              "pronoun": [(m["n"], m["c"]) for m in c["mentions"]["pronoun"][:4]]} for c in book["characters"]]
    (WORK / f"{stem}.json").write_text(json.dumps({"seconds": secs, "characters": chars, "quotes": quotes},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    nq = sum(l["kind"] == "quote" for l in lines)
    print(stem, "| booknlp", secs, "s | quotes matched", len(quotes), "of", nq, "| characters", len(chars), flush=True)
