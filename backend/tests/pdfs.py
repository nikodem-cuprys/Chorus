"""Minimal PDFs for the PDF reader's tests, written by hand as the sample fixture is
(`.scratch/chorus/samples/build/make_pdf.py`): standard Type 1 fonts, one text run per line."""

import io

import pypdf

FONTS = {
    "R": b"Times-Roman",
    "I": b"Times-Italic",
    "B": b"Helvetica-Bold",
}
WIDTH, HEIGHT = 595, 842


def _escape(text: str) -> bytes:
    data = text.encode("cp1252", "replace")
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def make_pdf(pages: list[list[tuple[str, float, float, float, str]]], image_only=False) -> bytes:
    """Each page is a list of (font, size, x, y, text), with y from the bottom; a run may
    switch font inside its text with "{I}" and "{R}"."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    fonts = {
        key: add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % name
        )
        for key, name in FONTS.items()
    }
    image = add(
        b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Length 4 >>\nstream\n\x00\xff\xff\x00\nendstream"
    )
    pages_id = len(objects) + 1 + 2 * len(pages)
    kids = []
    for runs in pages:
        stream = b""
        if image_only:
            stream += b"q 400 0 0 600 100 120 cm /Im1 Do Q\n"
        for font, size, x, y, text in runs:
            parts = text.split("{")
            ops = b"BT /F%s %.1f Tf %.1f %.1f Td " % (font.encode(), size, x, y)
            for n, part in enumerate(parts):
                if n:
                    key, part = part[0], part[2:]
                    ops += b"/F%s %.1f Tf " % (key.encode(), size)
                if part:
                    ops += b"(%s) Tj " % _escape(part)
            stream += ops + b"ET\n"
        content = add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        font_refs = b" ".join(b"/F%s %d 0 R" % (k.encode(), v) for k, v in fonts.items())
        kids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Resources << /Font << %s >> "
                b"/XObject << /Im1 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_id, WIDTH, HEIGHT, font_refs, image, content)
            )
        )
    assert (
        add(
            b"<< /Type /Pages /Kids [%s] /Count %d >>"
            % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
        )
        == pages_id
    )
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        xref,
    )
    return bytes(out)


def with_bookmarks(data: bytes, bookmarks: list[tuple[str, int]], password: str | None = None):
    """The same PDF with top-level bookmarks (title, page index), optionally encrypted."""
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(data)))
    for title, page in bookmarks:
        writer.add_outline_item(title, page)
    if password:
        writer.encrypt(password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def book(
    paragraphs_by_page: list[list[str]],
    header: str | None = "A RUNNING HEADER",
    numbers: bool = True,
    chars_per_line: int = 70,
) -> bytes:
    """A single-column book: each page's paragraphs wrapped at `chars_per_line`, with an
    indented first line, a running header and a page number. A paragraph starting with "#"
    is a heading in larger bold type."""
    pages = []
    for n, paragraphs in enumerate(paragraphs_by_page, start=1):
        runs = []
        if header:
            runs.append(("R", 8, 72, 805, header))
        if numbers:
            runs.append(("R", 8, 290, 40, str(n)))
        y = 760.0
        for paragraph in paragraphs:
            if paragraph.startswith("#"):
                y -= 10
                runs.append(("B", 14, 72, y, paragraph[1:].strip()))
                y -= 28
                continue
            lines, current = [], ""
            for word in paragraph.split(" "):
                if (
                    current
                    and len(current) + 1 + len(word.replace("{I}", "").replace("{R}", ""))
                    > chars_per_line
                ):
                    lines.append(current)
                    current = word
                else:
                    current = f"{current} {word}".strip()
            lines.append(current)
            for i, line in enumerate(lines):
                runs.append(("R", 11, 90 if i == 0 else 72, y, line))
                y -= 14
        pages.append(runs)
    return make_pdf(pages)
