"""PROTOTYPE, throwaway. Split each sample passage into lines: quoted spans and the narration between them.
Every approach labels the same lines, so their Scripts can be compared side by side.
Run with any Python 3: python segment.py"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).parent
PASSAGES = ROOT.parent.parent / "samples" / "passages"
QUOTE = re.compile(r"“[^”]*(?:”|$)", re.S)  # an unclosed quote runs to the end of its paragraph


def segment(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip() and not p.lstrip().startswith("#")]
    lines = []
    for pi, para in enumerate(paras):
        para = re.sub(r"\s*\n\s*", " ", para)
        pos = 0
        for m in QUOTE.finditer(para):
            if para[pos:m.start()].strip():
                lines.append({"para": pi, "kind": "narration", "text": para[pos:m.start()].strip()})
            lines.append({"para": pi, "kind": "quote", "text": m.group().strip()})
            pos = m.end()
        if para[pos:].strip():
            lines.append({"para": pi, "kind": "narration", "text": para[pos:].strip()})
    for i, line in enumerate(lines):
        line["id"] = i
    return lines


if __name__ == "__main__":
    out = ROOT / "lines"
    out.mkdir(exist_ok=True)
    for f in sorted(PASSAGES.glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        lines = segment(text)
        (out / f"{f.stem}.json").write_text(json.dumps({"passage": f.stem, "title": title, "lines": lines},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
        q = [l for l in lines if l["kind"] == "quote"]
        print(f.stem, "| paragraphs", lines[-1]["para"] + 1, "| lines", len(lines), "| quotes", len(q),
              "| unclosed", sum(not l["text"].endswith("”") for l in q))
