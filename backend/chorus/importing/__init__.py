"""Import: every reader turns its Source into the same `ImportedWork`, and nothing downstream
knows the Source format (docs/spec/03-pipeline.md, Import).

A block is plain text with marks, never HTML: a list of spans, each with the marks it carries,
plus a reference back to where it came from in the Source.
"""

import hashlib
import re
from dataclasses import dataclass, field

from chorus.jobs import JobFailed

# The kinds of block a reader produces. What is voiced, and how, is decided later from these
# (M1 ticket 09).
BLOCK_TYPES = (
    "paragraph", "heading", "section_break", "quote", "letter", "list_item", "footnote",
)  # fmt: skip
MARKS = ("italic", "bold", "underline", "strike", "small_caps", "superscript")
# A line of nothing but these marks ("* * *", "⁂") is a Section break.
SECTION_BREAK_TEXT = re.compile(r"^[\s*•·⁂◆◇~#=_—–-]+$")
# Project Gutenberg's lines around the book: what comes before START and from END on is its
# header and licence.
GUTENBERG_START = re.compile(
    r"^\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*$", re.I | re.M
)
GUTENBERG_END = re.compile(r"^\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*$", re.I | re.M)


class ImportRejected(JobFailed):
    """A Source Chorus will not import, with a message-catalogue key saying why."""


@dataclass
class Span:
    text: str
    marks: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"text": self.text, "marks": list(self.marks)} if self.marks else {"text": self.text}


@dataclass
class Block:
    type: str
    spans: list[Span]
    # Where it came from, for example {"file": "OEBPS/ch1.xhtml", "path": "/html/body/p[3]"}.
    ref: dict = field(default_factory=dict)
    level: int | None = None  # headings only
    # Text the Source's publisher added, such as Project Gutenberg's header and licence; it is
    # never voiced.
    boilerplate: bool = False

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    def to_dict(self) -> dict:
        data: dict = {"type": self.type, "spans": [s.to_dict() for s in self.spans]}
        if self.level is not None:
            data["level"] = self.level
        if self.boilerplate:
            data["boilerplate"] = True
        if self.ref:
            data["ref"] = self.ref
        return data


@dataclass
class ImportedChapter:
    title: str | None
    blocks: list[Block]
    notes_before: list[Block] = field(default_factory=list)
    notes_after: list[Block] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass
class ImportedWork:
    title: str
    authors: list[str]
    chapters: list[ImportedChapter]
    # The base language code the Source states, if any ("en" for "en-GB").
    language: str | None = None
    front_matter: list[Block] = field(default_factory=list)
    back_matter: list[Block] = field(default_factory=list)
    # summary, tags, series, series_index, rating, warnings, publisher, published
    metadata: dict = field(default_factory=dict)
    is_ao3: bool = False
    cover: bytes | None = None
    cover_type: str | None = None  # file extension, such as "jpg"
    # Message-catalogue keys with parameters.
    warnings: list[dict] = field(default_factory=list)

    def warn(self, key: str, **params: object) -> None:
        self.warnings.append({"key": key, "params": params})


def base_language(code: str | None) -> str | None:
    """`en-GB` → `en`; None for anything that does not look like a language code."""
    if not code:
        return None
    base = re.split(r"[-_]", code.strip().lower(), maxsplit=1)[0]
    return base if re.fullmatch(r"[a-z]{2,3}", base) else None


def normalise_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
