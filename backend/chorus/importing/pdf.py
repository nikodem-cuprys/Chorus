"""The PDF reader, for PDFs with a text layer: `pdfplumber` for characters with font, size and
position, `pypdf` for bookmarks and metadata.

Per page: words are read with their fonts; lines in the top and bottom bands that repeat across
pages (digits ignored) are running headers and go, as do lines that are only a page number.
Two-column pages are read column by column, split at the middle of the widest vertical gap no
word crosses. Lines then become paragraphs from line spacing and first-line indents, and are
joined across column and page breaks unless the column ended on a short line, ended early, or
the next line opens a quotation right after one closed. Larger type is a heading; three blank
lines' worth of space is a Section break.

A hyphen at a line end followed by a lowercase letter is removed, unless the same hyphenated
word appears elsewhere in the text, or the Language pack's dictionary has both halves but not
the joined word ("well-known").

Chapters come from the bookmarks, else from headings: those matching the pack's heading
patterns, else the largest headings. A PDF with no text layer is rejected, since scanned
PDFs are not supported (no OCR).
"""

import io
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

import pdfplumber
import pypdf
from pdfminer.pdfdocument import PDFPasswordIncorrect

from chorus.importing import (
    SECTION_BREAK_TEXT,
    Block,
    ImportedWork,
    ImportRejected,
    Span,
    base_language,
    normalise_space,
)
from chorus.importing.chapters import Segment, arrange
from chorus.languages import ChapterHeadings, LanguagePack

# The share of the page height at the top and bottom where running headers and page numbers
# are looked for.
BAND = 0.09
PAGE_NUMBER = re.compile(
    r"^[\s\-–—\[\](){}.]*(?:page\s+)?(\d{1,4}|[ivxlcdm]{1,7})(\s+of\s+\d+)?[\s\-–—\[\](){}.]*$",
    re.I,
)
ITALIC_FONT = re.compile(r"italic|oblique|-it\b|it$|boldit|ital", re.I)
BOLD_FONT = re.compile(r"bold|black|heavy|semibold|demi", re.I)
HEADING_SIZE = 1.1  # times the body size
NEW_PARAGRAPH_SPACING = 1.25  # times the usual line spacing
SECTION_BREAK_SPACING = 2.6
SHORT_LINE = 0.8  # of the column width
WORD = re.compile(r"[^\W\d_]+(?:[’'][^\W\d_]+)*")
HYPHENATED = re.compile(r"\b([^\W\d_]+)-([^\W\d_]+)\b")


@dataclass
class _Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    font: str
    marks: tuple[str, ...]


@dataclass
class _Line:
    page: int
    words: list[_Word]
    column: tuple[float, float] = (0.0, 0.0)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.x1 for w in self.words)

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> float:
        return max(w.bottom for w in self.words)

    @property
    def size(self) -> float:
        return max(w.size for w in self.words)


@dataclass
class _Paragraph:
    lines: list[_Line] = field(default_factory=list)
    heading: bool = False
    gap_before: bool = False  # a Section break comes before it


def read_pdf(
    data: bytes,
    pack_for: Callable[[str | None], LanguagePack],
    name: str = "",
    progress: Callable[[int, int], None] | None = None,
) -> ImportedWork:
    """`pack_for(language)` gives the Language pack for the language the PDF states (None when
    it states none): its heading patterns, quotation marks and dictionary are used."""
    work = ImportedWork(title=re.sub(r"\.[^.]*$", "", name), authors=[], chapters=[])
    outline = _read_pypdf(data, work)
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except PDFPasswordIncorrect as exc:
        raise ImportRejected("import.error.drm", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001  (pdfminer raises many kinds on a broken file)
        raise ImportRejected("import.error.unreadable", repr(exc)) from exc

    with pdf:
        pages = []
        for n, page in enumerate(pdf.pages):
            pages.append((page.width, page.height, _words(page)))
            if progress:
                progress(n + 1, len(pdf.pages))

    empty = [n for n, (_, _, words) in enumerate(pages) if not words]
    if len(empty) == len(pages) or len(empty) > len(pages) / 2:
        raise ImportRejected("import.error.scanned_pdf")
    if empty:
        work.warn("import.warning.pdf_pages_without_text", count=len(empty))

    pack = pack_for(work.language)
    headings = pack.chapter_headings
    lines = _remove_page_furniture(pages, work)
    body_size = _body_size(lines)
    starts = {page for _, page, _ in outline}
    paragraphs = _paragraphs(lines, body_size, pack.quotation.pairs, starts)
    blocks = _blocks(paragraphs, lines, pack.dictionary)

    segments = _cut_at_bookmarks(blocks, outline) if len(outline) >= 2 else None
    if segments is None:
        segments = _cut_at_headings(blocks, headings, work)
    chapters, front, back = arrange(segments, headings)
    work.chapters, work.front_matter, work.back_matter = chapters, front, back
    if not chapters:
        raise ImportRejected("import.error.no_text")
    return work


# ---- pypdf: metadata and bookmarks ----


def _read_pypdf(data: bytes, work: ImportedWork) -> list[tuple[str, int, float | None]]:
    """The top-level bookmarks as (title, page index, distance from the page top)."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ImportRejected("import.error.drm", "the PDF needs a password")
    except ImportRejected:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ImportRejected("import.error.unreadable", repr(exc)) from exc

    meta = reader.metadata or {}
    if str(meta.get("/Title") or "").strip():
        work.title = normalise_space(str(meta["/Title"]))
    if str(meta.get("/Author") or "").strip():
        work.authors = [normalise_space(str(meta["/Author"]))]
    language = reader.trailer["/Root"].get("/Lang")
    work.language = base_language(str(language)) if language else None

    entries = []
    try:
        for item in reader.outline:
            if isinstance(item, list):
                continue  # children of the previous entry
            page = reader.get_destination_page_number(item)
            height = float(reader.pages[page].mediabox.height)
            top = getattr(item, "top", None)
            entries.append(
                (normalise_space(str(item.title)), page, height - float(top) if top else None)
            )
    except Exception:  # noqa: BLE001  (a broken outline is no reason to fail the import)
        return []
    return entries


# ---- pdfplumber: words ----


def _marks(font: str, chars: list[dict]) -> tuple[str, ...]:
    font = font.split("+")[-1]
    slanted = any(
        c.get("upright", True) and c["matrix"][3] and abs(c["matrix"][2] / c["matrix"][3]) > 0.1
        for c in chars
    )
    marks = []
    if ITALIC_FONT.search(font) or slanted:
        marks.append("italic")
    if BOLD_FONT.search(font):
        marks.append("bold")
    return tuple(marks)


def _words(page) -> list[_Word]:
    words = page.extract_words(extra_attrs=["fontname", "size"], return_chars=True)
    return [
        _Word(
            w["text"],
            w["x0"],
            w["x1"],
            w["top"],
            w["bottom"],
            round(w["size"], 1),
            w["fontname"],
            _marks(w["fontname"], w["chars"]),
        )
        for w in words
        if w["text"].strip() and w.get("upright", True)
    ]


def _group_lines(words: list[_Word], page: int) -> list[_Line]:
    lines: list[_Line] = []
    for word in sorted(words, key=lambda w: (round(w.bottom), w.x0)):
        line = next(
            (
                ln
                for ln in reversed(lines[-3:])
                if abs(ln.words[-1].bottom - word.bottom) <= 0.4 * min(word.size, ln.size)
            ),
            None,
        )
        if line is None:
            lines.append(_Line(page, [word]))
        else:
            line.words.append(word)
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return sorted(lines, key=lambda ln: ln.top)


def _columns(words: list[_Word], width: float) -> list[list[_Word]]:
    """Splits a page's words at a vertical gap in its middle that (almost) no word crosses."""
    if len(words) < 40:
        return [words]
    xs = range(int(width * 0.3), int(width * 0.7))
    crossing = [sum(1 for w in words if w.x0 < x < w.x1) for x in xs]
    best_count = min(crossing)
    if best_count > 0.02 * len(words):
        return [words]
    # The middle of the widest run of least-crossed positions: the gutter.
    runs, start = [], None
    for i, count in enumerate([*crossing, best_count + 1]):
        if count == best_count and start is None:
            start = i
        elif count != best_count and start is not None:
            runs.append((i - start, start, i - 1))
            start = None
    _, first, last = max(runs)
    best_x = xs[(first + last) // 2]
    left = [w for w in words if w.x1 <= best_x]
    right = [w for w in words if w.x0 >= best_x]
    across = [w for w in words if w.x0 < best_x < w.x1]
    if min(len(left), len(right)) < 0.15 * len(words):
        return [words]
    # Words across the gap (a centred title) go with the column they mostly sit in.
    for w in across:
        (left if (w.x0 + w.x1) / 2 < best_x else right).append(w)
    return [left, right]


# ---- Running headers, footers and page numbers ----


def _remove_page_furniture(pages, work: ImportedWork) -> list[_Line]:
    banded: list[tuple[int, _Line, str]] = []
    kept_words: dict[int, list[_Word]] = defaultdict(list)
    sizes = Counter(round(w.size) for _, _, words in pages for w in words)
    body = sizes.most_common(1)[0][0] if sizes else 10

    for n, (_, height, words) in enumerate(pages):
        band = [w for w in words if w.top < height * BAND or w.bottom > height * (1 - BAND)]
        kept_words[n] = [w for w in words if w not in band]
        for line in _group_lines(band, n):
            key = re.sub(r"\d+", "#", line.text.lower()).strip()
            banded.append((n, line, key))

    # On how many pages each banded line (digits ignored) appears.
    pages_with = Counter(key for _, key in {(n, key) for n, _, key in banded})
    repeat = min(3, max(2, len(pages) // 2))
    headers, numbers = set(), set()
    for n, line, key in banded:
        if PAGE_NUMBER.match(line.text):
            numbers.add(n)
        elif pages_with[key] >= repeat and line.size <= body * HEADING_SIZE:
            headers.add(n)
        else:
            kept_words[n].extend(line.words)
    if headers:
        work.warn("import.warning.pdf_headers_removed", count=len(headers))
    if numbers:
        work.warn("import.warning.pdf_page_numbers_removed", count=len(numbers))

    groups: list[list[_Line]] = []
    for n, (width, _, _) in enumerate(pages):
        for column in _columns(kept_words[n], width):
            column_lines = _group_lines(column, n)
            if column_lines:
                groups.append(column_lines)
    _set_margins(groups)
    return [line for group in groups for line in group]


def _set_margins(groups: list[list[_Line]]) -> None:
    """Gives each column its margins. A column's own lines can mislead (a page holding one
    short or indented line), so columns starting at about the same place on any page share
    the outermost margins among them."""
    edges = [(min(ln.x0 for ln in g), max(ln.x1 for ln in g)) for g in groups]
    for group, (left, right) in zip(groups, edges, strict=True):
        alike = [(a, b) for a, b in edges if abs(a - left) < 40 or abs(b - right) < 40]
        margins = (min(a for a, _ in alike), max(b for _, b in alike))
        for line in group:
            line.column = margins


def _body_size(lines: list[_Line]) -> float:
    sizes = Counter()
    for line in lines:
        for w in line.words:
            sizes[w.size] += len(w.text)
    return sizes.most_common(1)[0][0] if sizes else 10.0


# ---- Lines into paragraphs ----


def _paragraphs(
    lines: list[_Line],
    body: float,
    quotes: tuple[tuple[str, str], ...],
    page_starts: set[int] = frozenset(),
) -> list[_Paragraph]:
    steps = [
        b.top - a.top
        for a, b in zip(lines, lines[1:], strict=False)
        if a.page == b.page and a.column == b.column and abs(a.size - body) < 0.5
        and abs(b.size - body) < 0.5 and b.top > a.top
    ]  # fmt: skip
    leading = statistics.median(steps) if steps else body * 1.2
    # Where a full column ends: the usual bottom of a column's last line.
    last_bottoms = [
        a.bottom
        for a, b in zip(lines, lines[1:], strict=False)
        if (a.page, a.column) != (b.page, b.column)
    ]
    column_end = statistics.median(last_bottoms) if last_bottoms else None
    closing = tuple(c for o, c in quotes if o != c)
    opening = tuple(o for o, c in quotes if o != c)

    paragraphs: list[_Paragraph] = []
    previous: _Line | None = None
    for line in lines:
        heading = line.size > body * HEADING_SIZE
        current = paragraphs[-1] if paragraphs else None
        new, gap = True, False
        if current is not None and previous is not None and current.heading == heading:
            same_column = previous.page == line.page and previous.column == line.column
            if same_column:
                step = line.top - previous.top
                gap = step > leading * SECTION_BREAK_SPACING
                new = step > leading * NEW_PARAGRAPH_SPACING or _indented(line, body)
                if heading:
                    new = step > leading * 2
            else:
                # Across a column or page break the spacing says nothing; other signs do.
                width = previous.column[1] - previous.column[0]
                short = previous.x1 - previous.column[0] < width * SHORT_LINE
                ended = bool(re.search(r"[.!?:”’\"')]$", previous.text))
                early = column_end is not None and previous.bottom < column_end - 0.5 * leading
                turn = (
                    bool(closing)
                    and previous.text.endswith(closing)
                    and line.text.startswith(opening)
                )
                bookmarked = line.page in page_starts and line.page != previous.page
                new = _indented(line, body) or (ended and (short or early)) or turn or bookmarked
        if new:
            paragraphs.append(_Paragraph([line], heading, gap and bool(paragraphs)))
        else:
            current.lines.append(line)
        previous = line
    return paragraphs


def _indented(line: _Line, body: float) -> bool:
    return line.x0 - line.column[0] > 0.6 * body


# ---- Paragraphs into blocks, with hyphens resolved ----


def _vocabulary(lines: list[_Line]) -> tuple[set[str], set[str]]:
    """The words of the text away from line ends, and its hyphenated words."""
    words, hyphenated = set(), set()
    for line in lines:
        inner = line.words[1:-1] if len(line.words) > 2 else []
        for w in inner:
            words.update(m.lower() for m in WORD.findall(w.text))
            hyphenated.update(f"{a}-{b}".lower() for a, b in HYPHENATED.findall(w.text))
    return words, hyphenated


def _join_hyphen(
    left: str, right: str, words: set[str], hyphenated: set[str], dictionary: frozenset[str] | None
) -> bool:
    """Whether "left-" at a line end and "right" on the next line are one word without the
    hyphen."""
    a = WORD.findall(left)[-1].lower() if WORD.findall(left) else ""
    b = WORD.findall(right)[0].lower() if WORD.findall(right) else ""
    if f"{a}-{b}" in hyphenated:
        return False
    joined = a + b
    if joined in words or (dictionary and joined in dictionary):
        return True
    if dictionary and a in dictionary and b in dictionary:
        return False
    return True


def _blocks(
    paragraphs: list[_Paragraph], lines: list[_Line], dictionary: frozenset[str] | None
) -> list[Block]:
    words, hyphenated = _vocabulary(lines)
    blocks: list[Block] = []
    for paragraph in paragraphs:
        if paragraph.gap_before and blocks and blocks[-1].type != "section_break":
            blocks.append(Block("section_break", [], {"page": paragraph.lines[0].page + 1}))
        tokens: list[tuple[str, tuple[str, ...]]] = []
        for line in paragraph.lines:
            for n, word in enumerate(line.words):
                if n == 0 and tokens:
                    last_text, last_marks = tokens[-1]
                    joinable = (
                        last_text.endswith("-")
                        and len(last_text) > 1
                        and last_text[-2].isalpha()
                        and word.text[:1].islower()
                    )
                    if joinable:
                        hyphen = not _join_hyphen(
                            last_text[:-1], word.text, words, hyphenated, dictionary
                        )
                        merged = last_text if hyphen else last_text[:-1]
                        tokens[-1] = (merged + word.text, last_marks)
                        continue
                    # A dash, or a hyphen before a capital ("Saint-Malo"), joins as it is.
                    capital = (
                        last_text.endswith("-")
                        and last_text[-2:-1].isalpha()
                        and word.text[:1].isupper()
                    )
                    if last_text.endswith(("—", "–")) or capital:
                        tokens[-1] = (last_text + word.text, last_marks)
                        continue
                tokens.append((word.text, word.marks))
        spans: list[Span] = []
        for text, marks in tokens:
            if spans:
                if spans[-1].marks == marks:
                    spans[-1] = Span(spans[-1].text + " " + text, marks)
                    continue
                # The space between differently marked words goes with the unmarked one.
                if spans[-1].marks and not marks:
                    text = " " + text
                else:
                    spans[-1] = Span(spans[-1].text + " ", spans[-1].marks)
            spans.append(Span(text, marks))
        text = "".join(s.text for s in spans)
        ref = {"page": paragraph.lines[0].page + 1}
        if SECTION_BREAK_TEXT.match(text) and len(text) <= 20:
            if blocks and blocks[-1].type != "section_break":
                blocks.append(Block("section_break", [], ref))
            continue
        if paragraph.heading:
            # Headings are set apart by type; their marks only repeat that.
            blocks.append(Block("heading", [Span(text)], ref, 2))
        else:
            blocks.append(Block("paragraph", spans, ref))
    return blocks


# ---- Chapters ----


def _cut_at_bookmarks(
    blocks: list[Block], outline: list[tuple[str, int, float | None]]
) -> list[Segment] | None:
    """Each bookmark starts a segment at the first block on its page (at or below where it
    points, when it says)."""
    starts: list[tuple[int, str]] = []
    for title, page, _top in outline:
        index = next((i for i, b in enumerate(blocks) if b.ref.get("page", 0) - 1 >= page), None)
        if index is not None:
            starts.append((index, title))
    starts = sorted(set(starts))
    if len(starts) < 2:
        return None
    segments = [Segment(None, blocks[: starts[0][0]])]
    for (index, title), following in zip(starts, starts[1:] + [(len(blocks), "")], strict=True):
        segments.append(Segment(title, blocks[index : following[0]]))
    return segments


def _cut_at_headings(
    blocks: list[Block], headings: ChapterHeadings | None, work: ImportedWork
) -> list[Segment]:
    # A short paragraph that matches the heading patterns is a heading set in body type.
    for n, block in enumerate(blocks):
        text = block.text
        if (
            block.type == "paragraph"
            and headings
            and len(text) <= 80
            and "\n" not in text
            and headings.is_heading(text)
        ):
            blocks[n] = Block("heading", [Span(text)], block.ref, 2)

    heading_at = [n for n, b in enumerate(blocks) if b.type == "heading"]
    matching = [n for n in heading_at if headings and headings.is_heading(blocks[n].text)]
    cuts = matching or (heading_at if len(heading_at) >= 2 else [])
    # Consecutive headings (a part title, then a chapter title) open one chapter.
    cuts = [n for n in cuts if n == 0 or blocks[n - 1].type != "heading"]
    if not cuts:
        work.warn("import.warning.no_chapters")
        return [Segment("", blocks)]
    if not matching:
        work.warn("import.warning.split_by_headings")
    segments = [Segment(None, blocks[: cuts[0]])]
    for start, end in zip(cuts, cuts[1:] + [len(blocks)], strict=True):
        segments.append(Segment("", blocks[start:end]))
    return segments
