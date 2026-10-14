"""The Script: a Work's text cut into lines, the part of analysis that needs no model
(docs/spec/03-pipeline.md, Analysis steps 1 and 2).

**Kinds of text** come only from the import's markup: a heading inside a chapter is a chapter
title, a letter block a letter, Project Gutenberg's header and licence never voiced, and so on
(`PASSAGE_OF_BLOCK`). Anything not marked is narration. A chapter whose title came from the
table of contents, with no heading in its text, gets a chapter-title line made from the title,
and the Script opens with a Work title and author line made from the metadata.

**Line splitting:** narration and verse are split at the Language pack's quotation marks. Each
quotation is one line, and the narration between quotations inside a paragraph is one line. A
quotation left open at the end of a paragraph runs on into the next one when that paragraph
opens with the quotation mark again (the English convention for a speech of several
paragraphs), or when its next quotation mark, within `LOOKAHEAD` paragraphs, is the closing one
(a song inside a speech); otherwise it ends with its paragraph. Other kinds are one line per
block, so a letter set as its own block stays whole, while a letter read aloud inside quotation
marks is an ordinary quotation.

**What is voiced** in M1 follows ticket 21's defaults, with no switches yet (`VOICED`). The
front and back matter are voiced like a chapter (a TXT file's first chapter has no heading of
its own, so it is front matter), except their lists, which are contents lists and lists of
illustrations: never voiced.
"""

from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from chorus.importing import Block, Span
from chorus.languages import LanguagePack, QuotationRules
from chorus.models import Chapter, Line, Work

PASSAGES = (
    "narration", "chapter_title", "work_title", "epigraph", "letter", "verse", "footnote", "list",
    "ao3_note", "never_voiced",
)  # fmt: skip
PASSAGE_OF_BLOCK = {
    "paragraph": "narration",
    "quote": "narration",
    "heading": "chapter_title",
    "epigraph": "epigraph",
    "letter": "letter",
    "verse": "verse",
    "list_item": "list",
    "footnote": "footnote",
}
# Ticket 21's defaults: summaries, author notes and footnotes are not voiced.
VOICED = frozenset(
    {"narration", "chapter_title", "work_title", "epigraph", "letter", "verse", "list"}
)
# Passages split at quotations; every other one is a line per block.
SPLIT = frozenset({"narration", "verse"})
# How many paragraphs an open quotation looks ahead for its closing mark.
LOOKAHEAD = 3


@dataclass
class Draft:
    """A line before it is saved."""

    paragraph: int | None
    last_paragraph: int | None
    spans: list[Span]
    kind: str  # narration or quote
    passage: str

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


def passage_of(block: Block, notes: bool = False, matter: bool = False) -> str | None:
    """The kind of passage a block is; None for a Section break, which is no line. `matter`:
    the block is in the front or back matter."""
    if block.type == "section_break":
        return None
    if block.boilerplate or (matter and block.type == "list_item"):
        return "never_voiced"
    if notes:
        return "ao3_note"  # chapter notes; recognised in AO3 Sources only from milestone 2
    return PASSAGE_OF_BLOCK.get(block.type, "narration")


# ---- Spans ----


def _slice(spans: list[Span], start: int, end: int) -> list[Span]:
    out, offset = [], 0
    for span in spans:
        a, b = max(start, offset), min(end, offset + len(span.text))
        if a < b:
            out.append(Span(span.text[a - offset : b - offset], span.marks))
        offset += len(span.text)
    return out


def _strip(spans: list[Span]) -> list[Span]:
    spans = [s for s in spans if s.text]
    while spans and not spans[0].text.strip():
        spans = spans[1:]
    while spans and not spans[-1].text.strip():
        spans = spans[:-1]
    if spans:
        spans[0] = Span(spans[0].text.lstrip(), spans[0].marks)
        spans[-1] = Span(spans[-1].text.rstrip(), spans[-1].marks)
    return spans


# ---- Quotation marks ----


def choose_pairs(blocks: list[Block], rules: QuotationRules) -> tuple[tuple[str, str], ...]:
    """The pack's alternative pairs (‘ ’ for English) when the text opens more quotations with
    them than with its main pairs."""
    if not rules.alternative_pairs:
        return rules.pairs
    text = "".join(b.text for b in blocks)

    def opened(pairs: tuple[tuple[str, str], ...]) -> float:
        return sum(text.count(o) / (2 if o == c else 1) for o, c in pairs)

    return (
        rules.alternative_pairs
        if opened(rules.alternative_pairs) > opened(rules.pairs)
        else rules.pairs
    )


def _closes(text: str, i: int, pair: tuple[str, str]) -> bool:
    """A closing mark followed by a letter is an apostrophe ("don’t"), never a closing mark."""
    return text[i] == pair[1] and not (i + 1 < len(text) and text[i + 1].isalpha())


@dataclass
class _Quotation:
    pair: tuple[str, str]
    pieces: list[tuple[int, int, int]]  # (paragraph, start, end), one per paragraph
    start: int  # where the piece in the current paragraph starts


def _runs_on(blocks: list[tuple[Block, str | None]], n: int, pair: tuple[str, str]) -> bool:
    """Whether a quotation left open at the end of paragraph `n` runs on into the next."""
    if n + 1 >= len(blocks) or blocks[n + 1][1] not in SPLIT:
        return False
    if blocks[n + 1][0].text.lstrip().startswith(pair[0]):
        return True
    if pair[0] == pair[1]:
        return False  # with straight marks, an opening mark cannot be told from a closing one
    for block, passage in blocks[n + 1 : n + 1 + LOOKAHEAD]:
        if passage not in SPLIT:
            return False
        text = block.text
        for i, char in enumerate(text):
            if char == pair[0]:
                return False
            if _closes(text, i, pair):
                return True
    return False


def split(
    blocks: list[tuple[Block, str | None]], pairs: tuple[tuple[str, str], ...]
) -> list[Draft]:
    """One part's blocks (front matter, a chapter, back matter), each with its passage, into
    lines. Paragraph numbers are indexes into `blocks`."""
    openers = {o: (o, c) for o, c in pairs}
    lines: list[Draft] = []

    def narration(n: int, start: int, end: int, passage: str) -> None:
        spans = _strip(_slice(blocks[n][0].spans, start, end))
        if spans:
            lines.append(Draft(n, n, spans, "narration", passage))

    def quotation(q: _Quotation, passage: str) -> None:
        spans: list[Span] = []
        for p, start, end in q.pieces:
            if spans:
                spans.append(Span("\n"))
            spans += _strip(_slice(blocks[p][0].spans, start, end))
        lines.append(Draft(q.pieces[0][0], q.pieces[-1][0], _strip(spans), "quote", passage))

    carried: _Quotation | None = None
    carried_passage = "narration"
    for n, (block, passage) in enumerate(blocks):
        if passage is None:
            continue
        text = block.text
        if passage not in SPLIT:
            spans = _strip(list(block.spans))
            if spans:
                lines.append(Draft(n, n, spans, "narration", passage))
            continue

        quote, pos, i = carried, 0, 0
        if quote is not None:
            carried = None
            quote.start = 0
            lead = len(text) - len(text.lstrip())
            if text[lead : lead + 1] == quote.pair[0]:
                i = lead + 1  # the opening mark repeated, not a new quotation
        while i < len(text):
            if quote is None:
                if text[i] in openers:
                    narration(n, pos, i, passage)
                    quote = _Quotation(openers[text[i]], [], i)
                    carried_passage = passage
            elif _closes(text, i, quote.pair):
                quote.pieces.append((n, quote.start, i + 1))
                quotation(quote, carried_passage)
                quote, pos = None, i + 1
            i += 1
        if quote is None:
            narration(n, pos, len(text), passage)
        else:
            quote.pieces.append((n, quote.start, len(text)))
            if _runs_on(blocks, n, quote.pair):
                carried = quote
            else:
                quotation(quote, carried_passage)
    return lines


# ---- The Work ----


def _chapter_lines(chapter: Chapter, pairs: tuple[tuple[str, str], ...]) -> list[Draft]:
    blocks = [(b, passage_of(b, notes=True)) for b in map(Block.from_dict, chapter.notes_before)]
    blocks += [(b, passage_of(b)) for b in map(Block.from_dict, chapter.blocks)]
    blocks += [(b, passage_of(b, notes=True)) for b in map(Block.from_dict, chapter.notes_after)]
    lines = split(blocks, pairs)
    first = next((p for b, p in blocks if p not in (None, "ao3_note")), None)
    if chapter.title and first != "chapter_title":
        lines.insert(0, Draft(None, None, [Span(chapter.title)], "narration", "chapter_title"))
    return lines


def build_script(session: Session, work: Work, pack: LanguagePack) -> None:
    """Replaces the Work's lines with a new Script cut from its imported text."""
    session.execute(delete(Line).where(Line.work_id == work.id))
    blocks = [Block.from_dict(b) for c in work.chapters for b in c.blocks]
    pairs = choose_pairs(blocks, pack.quotation)

    def matter(raw: list[dict]) -> list[Draft]:
        blocks = [Block.from_dict(b) for b in raw]
        return split([(b, passage_of(b, matter=True)) for b in blocks], pairs)

    position = 0

    def save(drafts: list[Draft], part: str, chapter: Chapter | None) -> None:
        nonlocal position
        for draft in drafts:
            session.add(
                Line(
                    work_id=work.id,
                    chapter_id=chapter.id if chapter else None,
                    part=part,
                    position=position,
                    paragraph=draft.paragraph,
                    last_paragraph=draft.last_paragraph,
                    spans=[s.to_dict() for s in draft.spans],
                    text=draft.text,
                    kind=draft.kind,
                    passage=draft.passage,
                    voiced=draft.passage in VOICED,
                )
            )
            position += 1

    front = matter(work.front_matter)
    if work.title:
        said = pack.work_title.say(work.title, work.authors) if pack.work_title else work.title
        front.insert(0, Draft(None, None, [Span(said)], "narration", "work_title"))
    save(front, "front", None)
    for chapter in work.chapters:
        save(_chapter_lines(chapter, pairs), "chapter", chapter)
    save(matter(work.back_matter), "back", None)
