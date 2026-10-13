"""PROTOTYPE, throwaway (M1 ticket 03). Pride and Prejudice from samples/raw as chapters of lines, split the way
approach B splits the sample passages (attribution/segment.py), and cut into ~900-word chunks inside each chapter.
Run with any Python 3: python book.py  (prints the counts)"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
ATTR = ROOT.parent / "attribution"
sys.path.insert(0, str(ATTR))
import llm  # noqa: E402
import segment  # noqa: E402

RAW = ROOT.parent.parent / "samples" / "raw" / "pg1342.txt"
# "Chapter I.]" (inside the title illustration), "CHAPTER II.", "CHAPTER XIII", "Chapter XLVI."
HEADING = re.compile(r"^\s*chapter [lxvi]+\.?\]?\s*$", re.I)
ILLUSTRATION = re.compile(r"\[(_?Illustration|_?Copyright)[^\]]*\]", re.S)


def chapters():
    """[(number, text)] for the 61 chapters, without Gutenberg's header, licence and illustration captions."""
    body = RAW.read_text(encoding="utf-8").split("*** START OF")[1].split("\n", 1)[1].split("*** END OF")[0]
    out, current = [], None
    for line in body.splitlines():
        if HEADING.match(line):
            current = []
            out.append(current)
        elif current is not None:
            current.append(line)
    return [(n, ILLUSTRATION.sub("", "\n".join(lines)).strip()) for n, lines in enumerate(out, 1)]


def lines():
    """Every line of the book with a global id and paragraph number, and its chapter."""
    out, next_id, next_para = [], 0, 0
    for number, text in chapters():
        chapter_lines = segment.segment(text)
        for line in chapter_lines:
            line.update(id=next_id + line["id"], para=next_para + line["para"], chapter=number)
        out.extend(chapter_lines)
        next_id += len(chapter_lines)
        if chapter_lines:
            next_para = max(l["para"] for l in chapter_lines) + 1
    return out


def chunks(all_lines, max_words=900):
    """Chunks of whole paragraphs, never across a chapter boundary: [(chapter, [lines])]."""
    out = []
    for number in sorted({l["chapter"] for l in all_lines}):
        for part in llm.chunks([l for l in all_lines if l["chapter"] == number], max_words=max_words):
            out.append((number, part))
    return out


if __name__ == "__main__":
    ls = lines()
    cs = chunks(ls)
    words = sum(len(l["text"].split()) for l in ls)
    print(f"chapters {len(chapters())} | lines {len(ls)} | quotes {sum(l['kind'] == 'quote' for l in ls)} "
          f"| words {words} | chunks {len(cs)}")
