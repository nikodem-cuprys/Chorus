"""The plain-text reader.

Encoding: the byte-order mark if there is one, else UTF-8, else what `charset-normalizer`
detects; the encoding used is always among the import warnings. Paragraphs are separated by
blank lines and their hard-wrapped lines are joined (indented lines, as in verse, keep their
breaks). Chapters start at paragraphs of one or two short lines that match the Language pack's
heading patterns; a lone number ("II.") only starts a chapter when the file has no other kind
of heading, so numbered sections inside numbered stories stay inside their story. Three or
more blank lines, or a line of asterisks, are a Section break.

Project Gutenberg files are recognised by their START and END lines: the header and the
licence become front and back matter marked as boilerplate (never voiced), and the header's
Title, Author and Language lines become the metadata. Gutenberg's `[Illustration: …]` notes
are dropped, except for a chapter heading inside one; `_underscores_` become italics.
"""

import codecs
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from charset_normalizer import from_bytes
from lingua import Language

from chorus.importing import (
    GUTENBERG_END,
    GUTENBERG_START,
    SECTION_BREAK_TEXT,
    Block,
    ImportedChapter,
    ImportedWork,
    ImportRejected,
    Span,
)
from chorus.languages import ChapterHeadings

BOMS = [
    (codecs.BOM_UTF32_LE, "utf-32", "UTF-32"),
    (codecs.BOM_UTF32_BE, "utf-32", "UTF-32"),
    (codecs.BOM_UTF8, "utf-8-sig", "UTF-8"),
    (codecs.BOM_UTF16_LE, "utf-16", "UTF-16"),
    (codecs.BOM_UTF16_BE, "utf-16", "UTF-16"),
]
GUTENBERG_FIELD = re.compile(r"^(Title|Author|Language):\s*(.+)$", re.M)
# Lines indented this much, all through a paragraph, are set out (verse), not wrapped prose;
# some Gutenberg texts indent every prose line by one space.
VERSE_INDENT = re.compile(r"^(?: {2,}|\t)")
ITALIC = re.compile(r"(?<![A-Za-z_])_([^_]+?)_(?![A-Za-z0-9_])")

# A heading line, and a subtitle line under it, are at most this long.
HEADING_CHARS = 80
SUBTITLE_WORDS = 10
SECTION_BREAK_BLANK_LINES = 3


@dataclass
class _Paragraph:
    lines: list[str]
    line: int  # 1-based number of its first line in the file
    gap: int  # blank lines before it

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class _Chapter:
    title: str
    blocks: list[Block] = field(default_factory=list)

    @property
    def only_headings(self) -> bool:
        return all(b.type == "heading" for b in self.blocks)


def decode(data: bytes) -> tuple[str, dict]:
    """The text and the warning naming the encoding used."""
    for bom, codec, name in BOMS:
        if data.startswith(bom):
            return data.decode(codec), {
                "key": "import.warning.encoding",
                "params": {"encoding": name},
            }
    try:
        return data.decode("utf-8"), {
            "key": "import.warning.encoding",
            "params": {"encoding": "UTF-8"},
        }
    except UnicodeDecodeError:
        pass
    matches = from_bytes(data)
    best = matches.best()
    if best is None:
        raise ImportRejected("import.error.unreadable", "no encoding fits")
    # English text with a few accented letters often fits several Windows code pages exactly
    # as well (curly quotes and dashes are the same bytes in all of them); a tie goes to the
    # most common one, Windows-1252. A Polish text in Windows-1250 does not tie.
    for match in matches:
        if (match.chaos, match.coherence) == (
            best.chaos,
            best.coherence,
        ) and "cp1252" in match.could_be_from_charset:
            best = match
            break
    name = codecs.lookup(best.encoding).name
    try:
        if data.decode("cp1252") == str(best):
            name = "cp1252"  # reads the same either way
    except UnicodeDecodeError:
        pass
    if re.fullmatch(r"cp12\d\d", name):
        name = f"Windows-{name[2:]}"
    else:
        name = name.upper()
    return str(best), {"key": "import.warning.encoding_detected", "params": {"encoding": name}}


def read_txt(
    data: bytes, headings_for: Callable[[str | None], ChapterHeadings | None], name: str = ""
) -> ImportedWork:
    text, encoding_warning = decode(data)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("﻿", "")
    lines = text.split("\n")

    work = ImportedWork(title=re.sub(r"\.[^.]*$", "", name), authors=[], chapters=[])
    work.warnings.append(encoding_warning)

    start, end = 0, len(lines)
    start_match, end_match = GUTENBERG_START.search(text), GUTENBERG_END.search(text)
    if start_match:
        start = text.count("\n", 0, start_match.start()) + 1
        _read_gutenberg_header(text[: start_match.start()], work)
    if end_match and (not start_match or end_match.start() > start_match.start()):
        end = text.count("\n", 0, end_match.start())

    header = _paragraphs(lines[:start], 0)
    body = _drop_illustrations(_paragraphs(lines[start:end], start), headings_for(work.language))
    licence = _paragraphs(lines[end:], end)

    front, chapters, found_headings = _chapters(body, headings_for(work.language))
    work.front_matter = [_block(p, boilerplate=True) for p in header] + front
    work.back_matter = [_block(p, boilerplate=True) for p in licence]
    if not found_headings:
        work.warn("import.warning.no_chapters")
    work.chapters = [ImportedChapter(c.title or None, _trim(c.blocks)) for c in chapters]
    work.chapters = [c for c in work.chapters if c.blocks]
    if not work.chapters:
        raise ImportRejected("import.error.no_text")
    return work


def _read_gutenberg_header(header: str, work: ImportedWork) -> None:
    for key, value in GUTENBERG_FIELD.findall(header):
        value = value.strip()
        if key == "Title":
            work.title = value
        elif key == "Author":
            work.authors = [value]
        elif key == "Language":
            language = getattr(Language, value.upper().replace(" ", "_"), None)
            if language is not None:
                work.language = language.iso_code_639_1.name.lower()


def _paragraphs(lines: list[str], first: int) -> list[_Paragraph]:
    paragraphs: list[_Paragraph] = []
    current: list[str] = []
    gap = 0
    for n, line in enumerate(lines):
        if line.strip():
            if not current:
                paragraphs.append(_Paragraph(current, first + n + 1, gap))
            current.append(line.rstrip())
            gap = 0
        else:
            if current:
                current = []
            gap += 1
    return [p for p in paragraphs if p.lines]


def _drop_illustrations(
    paragraphs: list[_Paragraph], headings: ChapterHeadings | None
) -> list[_Paragraph]:
    """Removes `[Illustration…]` notes, which may run over several paragraphs, keeping any
    heading inside one (Gutenberg's Pride and Prejudice puts "Chapter I." in one)."""
    out: list[_Paragraph] = []
    n = 0
    while n < len(paragraphs):
        paragraph = paragraphs[n]
        if not paragraph.lines[0].lstrip().lower().startswith("[illustration"):
            out.append(paragraph)
            n += 1
            continue
        inner = [paragraph]
        depth = paragraph.text.count("[") - paragraph.text.count("]")
        while depth > 0 and n + len(inner) < len(paragraphs):
            following = paragraphs[n + len(inner)]
            inner.append(following)
            depth += following.text.count("[") - following.text.count("]")
        n += len(inner)
        gap = paragraph.gap
        for part in inner:
            cleaned = [re.sub(r"^\s*\[illustration:?", "", ln, flags=re.I) for ln in part.lines]
            cleaned = [ln.rstrip().rstrip("]").strip() for ln in cleaned]
            cleaned = [ln for ln in cleaned if ln]
            if cleaned and headings and _heading_style(cleaned, headings):
                out.append(_Paragraph(cleaned, part.line, gap))
                gap = 0
        # The blank lines around a dropped illustration are not a Section break.
        if n < len(paragraphs):
            paragraphs[n] = _Paragraph(
                paragraphs[n].lines, paragraphs[n].line, min(paragraph.gap, paragraphs[n].gap)
            )
    return out


def _heading_style(lines: list[str], headings: ChapterHeadings) -> str | None:
    first = lines[0].strip()
    if len(lines) > 2 or len(first) > HEADING_CHARS:
        return None
    if len(lines) == 2 and (
        not _is_subtitle(lines[1]) or headings.style(lines[1].strip()) not in (None, "lone_number")
    ):
        return None  # prose under the heading, or two lines of a contents list
    return headings.style(first)


def _is_subtitle(line: str) -> bool:
    line = line.strip()
    return (
        len(line) <= HEADING_CHARS
        and len(line.split()) <= SUBTITLE_WORDS
        and line[:1].isupper()
        and not line.endswith(",")
    )


def _is_section_break(paragraph: _Paragraph) -> bool:
    text = paragraph.text.strip()
    return len(paragraph.lines) == 1 and bool(SECTION_BREAK_TEXT.match(text)) and len(text) <= 60


def _spans(text: str) -> list[Span]:
    spans, position = [], 0
    for match in ITALIC.finditer(text):
        if match.start() > position:
            spans.append(Span(text[position : match.start()]))
        spans.append(Span(match.group(1), ("italic",)))
        position = match.end()
    if position < len(text):
        spans.append(Span(text[position:]))
    return spans


def _block(paragraph: _Paragraph, block_type: str = "paragraph", **kw) -> Block:
    lines = [re.sub(r"[ \t]+", " ", ln.strip()) for ln in paragraph.lines]
    if len(paragraph.lines) > 1 and all(VERSE_INDENT.match(ln) for ln in paragraph.lines):
        text = "\n".join(lines)  # verse and other set-out lines keep their breaks
    else:
        text = " ".join(lines)
    return Block(block_type, _spans(text), {"line": paragraph.line}, **kw)


def _heading(text: str, line: int, level: int) -> Block:
    return Block("heading", _spans(text), {"line": line}, level)


def _chapters(
    paragraphs: list[_Paragraph], headings: ChapterHeadings | None
) -> tuple[list[Block], list[_Chapter], bool]:
    styles = [_heading_style(p.lines, headings) if headings else None for p in paragraphs]
    present = {s for s in styles if s}
    # Lone numbers are sections, not chapters, when there are other headings.
    cutting = present - {"lone_number"} if present - {"lone_number"} else present

    front: list[Block] = []
    chapters: list[_Chapter] = []

    def blocks() -> list[Block]:
        return chapters[-1].blocks if chapters else front

    def add_break() -> None:
        target = blocks()
        if target and target[-1].type not in ("section_break", "heading"):
            target.append(Block("section_break", [], {}))

    for paragraph, style in zip(paragraphs, styles, strict=True):
        if paragraph.gap >= SECTION_BREAK_BLANK_LINES:
            add_break()
        if style in cutting:
            first = paragraph.lines[0].strip()
            title = first
            heading_blocks = [_heading(first, paragraph.line, 2)]
            if len(paragraph.lines) == 2:
                subtitle = paragraph.lines[1].strip()
                title = f"{first.rstrip('.:')}: {subtitle}"
                heading_blocks.append(_heading(subtitle, paragraph.line + 1, 3))
            if chapters and chapters[-1].only_headings:
                # A part title with nothing under it opens the chapter that follows.
                part = chapters.pop()
                title = f"{part.title.rstrip('.:')}: {title}"
                heading_blocks = part.blocks + heading_blocks
            chapters.append(_Chapter(title, heading_blocks))
        elif style is not None:
            target = blocks()
            for n, line in enumerate(paragraph.lines):
                target.append(_heading(line.strip(), paragraph.line + n, 3))
        elif _is_section_break(paragraph):
            add_break()
        else:
            blocks().append(_block(paragraph))

    if not cutting:
        return [], [_Chapter("", front)], False
    return _trim(front), chapters, True


def _trim(blocks: list[Block]) -> list[Block]:
    while blocks and blocks[0].type == "section_break":
        blocks = blocks[1:]
    while blocks and blocks[-1].type == "section_break":
        blocks = blocks[:-1]
    return blocks
