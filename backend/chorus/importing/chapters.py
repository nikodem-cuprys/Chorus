"""Arranging a reader's segments of blocks into chapters, front matter and back matter.

Shared by the readers whose Sources have a table of contents or bookmarks (EPUB, PDF): each
segment is the text under one entry, with the entry's label.
"""

from dataclasses import dataclass, field

from chorus.importing import Block, ImportedChapter, normalise_space
from chorus.languages import ChapterHeadings


@dataclass
class Segment:
    label: str | None
    blocks: list[Block] = field(default_factory=list)


def _leading_headings(blocks: list[Block]) -> list[Block]:
    found = []
    for block in blocks:
        if block.type == "heading":
            found.append(block)
        elif block.type != "section_break":
            break
    return found


def _title(segment: Segment) -> str | None:
    texts = [normalise_space(h.text) for h in _leading_headings(segment.blocks)]
    texts = [t for t in texts if t]
    if texts:
        parts = [t.rstrip(".:") for t in texts[:-1]] + [texts[-1]]
        return ": ".join(parts)
    return segment.label or None


def _looks_like_chapter(segment: Segment, headings: ChapterHeadings | None) -> bool:
    if headings is None:
        return False
    candidates = [normalise_space(h.text) for h in _leading_headings(segment.blocks)]
    candidates += [segment.label or ""]
    return any(c and headings.is_heading(c) for c in candidates)


def trim_breaks(blocks: list[Block]) -> list[Block]:
    while blocks and blocks[0].type == "section_break":
        blocks = blocks[1:]
    while blocks and blocks[-1].type == "section_break":
        blocks = blocks[:-1]
    return blocks


def arrange(
    segments: list[Segment], headings: ChapterHeadings | None
) -> tuple[list[ImportedChapter], list[Block], list[Block]]:
    """Segments before the first that looks like a chapter, and after the last, are front and
    back matter. A segment holding nothing but headings (a part title page) joins the next."""
    front = segments[0].blocks if segments and segments[0].label is None else []
    if front:
        segments = segments[1:]
    segments = [s for s in segments if any(b.type != "section_break" for b in s.blocks)]
    chapter_like = [n for n, s in enumerate(segments) if _looks_like_chapter(s, headings)]
    back: list[Block] = []
    if chapter_like:
        for s in segments[: chapter_like[0]]:
            front += s.blocks
        for s in segments[chapter_like[-1] + 1 :]:
            back += s.blocks
        segments = segments[chapter_like[0] : chapter_like[-1] + 1]

    merged: list[Segment] = []
    carry: list[Block] = []
    for segment in segments:
        blocks = carry + segment.blocks
        if all(b.type in ("heading", "section_break") for b in segment.blocks):
            carry = blocks
            continue
        carry = []
        merged.append(Segment(segment.label, blocks))
    if carry and merged:
        merged[-1].blocks += carry

    chapters = []
    for segment in merged:
        blocks = trim_breaks(segment.blocks)
        if blocks:
            chapters.append(ImportedChapter(_title(Segment(segment.label, blocks)), blocks))
    return chapters, trim_breaks(front), trim_breaks(back)
