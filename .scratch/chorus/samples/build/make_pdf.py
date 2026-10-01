"""Build a deliberately awkward text-layer PDF (no dependencies): two columns,
running headers, page-number footers, words hyphenated across line breaks,
and a chapter that starts mid-page."""
import pathlib, re

PASS = pathlib.Path(r"D:\projcets\Chorus\.scratch\chorus\samples\passages")
OUT = pathlib.Path(r"D:\projcets\Chorus\.scratch\chorus\samples\import\hard-two-column.pdf")

def body(name):
    t = (PASS / name).read_text(encoding="utf-8")
    return [p for p in t.split("\n\n") if p.strip() and not p.startswith("#")]

chapters = [("CHAPTER I", body("04-jane-eyre-ch1.txt")),
            ("CHAPTER II", body("03-holmes-scandal-in-bohemia.txt"))]

W, H = 595, 842                    # A4
MARGIN, GUTTER, TOP, BOTTOM = 50, 24, 780, 70
COLW = (W - 2 * MARGIN - GUTTER) / 2
SIZE, LEAD = 9.5, 11.5
CPL = int(COLW / (SIZE * 0.47))    # rough chars per line for Times-Roman

def wrap(par):
    lines, cur = [], ""
    for word in par.split():
        cand = (cur + " " + word).strip()
        if len(cand) <= CPL:
            cur = cand
            continue
        room = CPL - len(cur) - 2  # space + hyphen
        if len(word) >= 7 and room >= 3 and word[:room].isalpha():
            lines.append(cur + " " + word[:room] + "-")
            cur = word[room:]
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines

# Flatten into (kind, text) items; "gap" separates paragraphs.
items = []
for title, pars in chapters:
    items += [("gap", ""), ("head", title), ("gap", "")]
    for p in pars:
        items += [("line", l) for l in wrap(p.replace("_", ""))] + [("gap", "")]

def esc(s):
    b = s.encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

pages, ops, col, y = [], [], 0, TOP
def new_page():
    global ops, col, y
    if ops:
        pages.append(ops)
    n = len(pages) + 1
    ops = [(b"F2", 8, MARGIN, 805, "JANE EYRE AND OTHER STORIES" if n % 2 else "PUBLIC DOMAIN TEST EDITION"),
           (b"F1", 8, W / 2 - 8, 40, str(n))]
    col, y = 0, TOP
new_page()
for kind, text in items:
    step = LEAD if kind != "gap" else LEAD * 0.5
    if y - step < BOTTOM:
        if col == 0:
            col, y = 1, TOP
        else:
            new_page()
    x = MARGIN + col * (COLW + GUTTER)
    if kind == "line":
        ops.append((b"F1", SIZE, x, y, text))
    elif kind == "head":
        ops.append((b"F2", 11, x, y, text))
    y -= step
pages.append(ops)

objs = []
def add(b):
    objs.append(b)
    return len(objs)
f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>")
f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
pages_id = len(objs) + 1 + 2 * len(pages)
kids = []
for p in pages:
    stream = b"".join(b"BT /%s %.1f Tf %.1f %.1f Td (%s) Tj ET\n" % (f, s, x, y, esc(t)) for f, s, x, y, t in p)
    c = add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    kids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>"
                    % (pages_id, W, H, f1, f2, c)))
assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))) == pages_id
cat = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
offs = []
for i, o in enumerate(objs, 1):
    offs.append(len(out))
    out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
xref = len(out)
out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
out += b"".join(b"%010d 00000 n \n" % o for o in offs)
out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, cat, xref)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(out)
print(OUT, len(pages), "pages")
