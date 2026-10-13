"""The EPUB 2 and 3 reader, on `zipfile` and `lxml`.

`META-INF/container.xml` names the package; its spine gives the reading order and its
navigation document (or the NCX as fallback) the chapters. The documents are walked into one
stream of blocks with markers where each table-of-contents entry points, and the stream is cut
at those markers. Entries before the first one that looks like a chapter heading (by the
Language pack's patterns) are front matter, entries after the last one back matter; Project
Gutenberg's header and licence always are. Without a usable table of contents, the book is
split at `h1`/`h2` headings, or else one chapter per spine document. Images are dropped.
"""

import posixpath
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import unquote

from lxml import etree, html

from chorus.importing import (
    SECTION_BREAK_TEXT,
    Block,
    ImportedChapter,
    ImportedWork,
    ImportRejected,
    Span,
    base_language,
    normalise_space,
)
from chorus.languages import ChapterHeadings

NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "enc": "http://www.w3.org/2001/04/xmlenc#",
}
EPUB_TYPE = ("{http://www.idpf.org/2007/ops}type", "epub:type")

# Font obfuscation is not DRM: the IDPF and Adobe algorithms only scramble embedded fonts.
FONT_OBFUSCATION = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}
FONT_FILE = re.compile(r"\.(ttf|otf|woff2?)$", re.IGNORECASE)

XHTML_TYPES = {"application/xhtml+xml", "text/html", "application/xml"}
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}

INLINE_MARKS = {
    "i": "italic", "em": "italic", "cite": "italic", "var": "italic", "dfn": "italic",
    "b": "bold", "strong": "bold",
    "u": "underline", "ins": "underline",
    "s": "strike", "strike": "strike", "del": "strike",
    "sup": "superscript",
}  # fmt: skip
CONTAINERS = {
    "body", "div", "section", "article", "main", "header", "footer", "center", "ul", "ol", "dl",
    "table", "thead", "tbody", "tfoot", "blockquote", "aside", "hgroup", "figure", "details",
}  # fmt: skip
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
LEAVES = {"p", "li", "dt", "dd", "pre", "address", "tr", "caption", "summary"} | set(HEADINGS)
BLOCK_TAGS = CONTAINERS | LEAVES | {"hr", "nav"}
SKIPPED = {
    "head", "script", "style", "img", "svg", "image", "figcaption", "nav", "object", "video",
    "audio", "math", "iframe", "map", "noscript", "button", "input", "form",
}  # fmt: skip
# Classes and epub:types of things that are not text to read: figures and their captions, page
# numbers, page breaks.
SKIPPED_CLASS = re.compile(r"\b(fig\w*|caption|illus\w*|pagenum|pageno|page-?num\w*)\b", re.I)
SKIPPED_TYPE = re.compile(r"\b(pagebreak|noteref)\b")
FOOTNOTE_TYPE = re.compile(r"\b(footnote|endnote|rearnote|note)s?\b")
SMALL_CAPS_CLASS = re.compile(r"\b(smcap|smallcaps?|small-caps|sc)\b", re.I)
NOTE_MARKER = re.compile(r"^\W{0,2}[\d*†‡§]{1,3}\W{0,2}$")
INVISIBLE = re.compile(r"[­​‌⁠﻿]")
WHITESPACE = re.compile(r"[ \t\r\n\f\v  -   　]+")


@dataclass(frozen=True)
class Marker:
    """A place in the block stream: where a table-of-contents entry points ("toc", n), where a
    spine document starts ("file", n), or where Project Gutenberg's licence begins ("back")."""

    kind: str
    index: int = 0


@dataclass
class TocEntry:
    file: str
    fragment: str | None
    label: str
    depth: int


@dataclass
class _Segment:
    label: str | None
    blocks: list[Block] = field(default_factory=list)


def read_epub(
    data: bytes, headings_for: Callable[[str | None], ChapterHeadings | None]
) -> ImportedWork:
    """`headings_for(language)` gives the chapter-heading patterns for the language the
    metadata states (None when it states none)."""
    try:
        book = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ImportRejected("import.error.unreadable", str(exc)) from exc
    names = set(book.namelist())
    _reject_drm(book, names)

    opf_path = _package_path(book, names)
    opf = _parse_xml(book.read(opf_path), opf_path)
    root = posixpath.dirname(opf_path)
    manifest = {
        item.get("id"): {
            "href": _resolve(root, item.get("href", "")),
            "type": item.get("media-type", ""),
            "properties": item.get("properties", ""),
        }
        for item in opf.iterfind("opf:manifest/opf:item", NS)
    }
    spine = [
        manifest[ref.get("idref")]["href"]
        for ref in opf.iterfind("opf:spine/opf:itemref", NS)
        if ref.get("idref") in manifest
        and manifest[ref.get("idref")]["type"] in XHTML_TYPES
        and ref.get("linear", "yes") != "no"
        and manifest[ref.get("idref")]["href"] in names
    ]
    if not spine:
        raise ImportRejected("import.error.unreadable", "the spine lists no documents")

    work = ImportedWork(title="", authors=[], chapters=[])
    _read_metadata(opf, work)
    _read_cover(book, opf, manifest, names, work)

    toc = _read_toc(book, opf, manifest, names)
    targets: dict[str, dict[str | None, int]] = {}
    for n, entry in enumerate(toc):
        targets.setdefault(entry.file, {}).setdefault(entry.fragment, n)

    stream: list[Block | Marker] = []
    heading_counts = []
    for n, path in enumerate(spine):
        stream.append(Marker("file", n))
        doc = _parse_document(book.read(path), path)
        walker = _Walker(path, doc, targets.get(path, {}))
        walker.walk()
        stream.extend(walker.stream)
        heading_counts.append(sum(1 for item in walker.stream if _is_top_heading(item)))

    missing = len({(e.file, e.fragment) for e in toc}) - len(
        {i.index for i in stream if isinstance(i, Marker) and i.kind == "toc"}
    )
    front, stream, back = _split_off_boilerplate(stream)
    found = {i.index for i in stream if isinstance(i, Marker) and i.kind == "toc"}
    if len(found) >= 2:
        if missing > 0:
            work.warn("import.warning.toc_entries_not_found", count=missing)
        segments = _cut(stream, lambda m: m.kind == "toc", lambda m: toc[m.index].label)
    elif max(heading_counts, default=0) > 1:
        work.warn("import.warning.split_by_headings")
        segments = _cut_at_headings(stream)
    else:
        work.warn("import.warning.split_by_files")
        segments = _cut(stream, lambda m: m.kind == "file", lambda m: None)

    chapters, more_front, more_back = _arrange(segments, headings_for(work.language))
    for block in front + back:
        block.boilerplate = True
    work.front_matter = front + more_front
    work.back_matter = more_back + back
    work.chapters = chapters
    if not chapters:
        raise ImportRejected("import.error.no_text")
    if not work.title:
        work.title = chapters[0].title or ""
    return work


# ---- The container ----


def _reject_drm(book: zipfile.ZipFile, names: set[str]) -> None:
    if "META-INF/encryption.xml" not in names:
        return
    try:
        doc = etree.fromstring(book.read("META-INF/encryption.xml"), _xml_parser())
    except etree.XMLSyntaxError as exc:
        raise ImportRejected("import.error.drm", str(exc)) from exc
    for data in doc.iter(f"{{{NS['enc']}}}EncryptedData"):
        method = data.find("enc:EncryptionMethod", NS)
        reference = data.find("enc:CipherData/enc:CipherReference", NS)
        algorithm = method.get("Algorithm") if method is not None else None
        uri = reference.get("URI", "") if reference is not None else ""
        if algorithm not in FONT_OBFUSCATION or not FONT_FILE.search(uri):
            raise ImportRejected("import.error.drm", f"{uri} is encrypted with {algorithm}")


def _package_path(book: zipfile.ZipFile, names: set[str]) -> str:
    if "META-INF/container.xml" in names:
        container = _parse_xml(book.read("META-INF/container.xml"), "META-INF/container.xml")
        rootfile = container.find("c:rootfiles/c:rootfile", NS)
        if rootfile is not None and rootfile.get("full-path") in names:
            return rootfile.get("full-path")
    opfs = sorted(n for n in names if n.lower().endswith(".opf"))
    if not opfs:
        raise ImportRejected("import.error.unreadable", "no package document (.opf)")
    return opfs[0]


def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def _parse_xml(data: bytes, name: str) -> etree._Element:
    try:
        return etree.fromstring(data, _xml_parser())
    except etree.XMLSyntaxError:
        try:
            return etree.fromstring(data, etree.XMLParser(recover=True, no_network=True))
        except etree.XMLSyntaxError as exc:
            raise ImportRejected("import.error.unreadable", f"{name}: {exc}") from exc


def _parse_document(data: bytes, name: str) -> etree._Element:
    """XHTML as XML; a document that is not well-formed falls back to the HTML parser."""
    try:
        doc = etree.fromstring(data, _xml_parser())
        if doc is not None:
            return doc
    except etree.XMLSyntaxError:
        pass
    return html.document_fromstring(data)


def _resolve(base: str, href: str) -> str:
    return posixpath.normpath(posixpath.join(base, unquote(href))) if href else ""


def _local(el: etree._Element) -> str:
    if not isinstance(el.tag, str):
        return ""
    return etree.QName(el).localname.lower()


def _text(el: etree._Element) -> str:
    return normalise_space("".join(el.itertext()))


# ---- Metadata and cover ----


def _read_metadata(opf: etree._Element, work: ImportedWork) -> None:
    meta = opf.find("opf:metadata", NS)
    if meta is None:
        return

    def all_of(name: str) -> list[str]:
        return [_text(e) for e in meta.iterfind(f"dc:{name}", NS) if _text(e)]

    titles = all_of("title")
    work.title = titles[0] if titles else ""
    work.authors = all_of("creator")
    languages = all_of("language")
    work.language = base_language(languages[0]) if languages else None

    publisher = all_of("publisher")
    if publisher:
        work.metadata["publisher"] = publisher[0]
        work.is_ao3 = publisher[0].strip().lower() == "archive of our own"
    dates = [(e.get(f"{{{NS['opf']}}}event") or "", _text(e)) for e in meta.iterfind("dc:date", NS)]
    dates = [d for d in dates if d[1]]
    if dates:
        published = next((d for event, d in dates if event == "publication"), dates[0][1])
        work.metadata["published"] = published
    description = all_of("description")
    if description:
        summary = description[0]
        if "<" in summary:
            summary = _text(html.fragment_fromstring(summary, create_parent="div"))
        work.metadata["summary"] = summary
    tags = all_of("subject")
    if tags:
        work.metadata["tags"] = tags
    for el in meta.iterfind("opf:meta", NS):
        name, content = el.get("name"), el.get("content")
        if name == "calibre:series" and content:
            work.metadata["series"] = content
        elif name == "calibre:series_index" and content:
            work.metadata["series_index"] = content
        elif el.get("property") == "belongs-to-collection" and _text(el):
            work.metadata.setdefault("series", _text(el))
        elif el.get("property") == "group-position" and _text(el):
            work.metadata.setdefault("series_index", _text(el))


def _read_cover(
    book: zipfile.ZipFile, opf: etree._Element, manifest: dict, names: set[str], work: ImportedWork
) -> None:
    item = next((i for i in manifest.values() if "cover-image" in i["properties"].split()), None)
    if item is None:
        meta = opf.find("opf:metadata/opf:meta[@name='cover']", NS)
        if meta is not None:
            item = manifest.get(meta.get("content"))
    if item is None:
        item = next(
            (
                i
                for key, i in manifest.items()
                if "cover" in (key or "").lower() and i["type"] in IMAGE_TYPES
            ),
            None,
        )
    if item is None or item["type"] not in IMAGE_TYPES or item["href"] not in names:
        return
    work.cover = book.read(item["href"])
    work.cover_type = IMAGE_TYPES[item["type"]]


# ---- The table of contents ----


def _read_toc(
    book: zipfile.ZipFile, opf: etree._Element, manifest: dict, names: set[str]
) -> list[TocEntry]:
    nav = next((i for i in manifest.values() if "nav" in i["properties"].split()), None)
    if nav is not None and nav["href"] in names:
        entries = _read_nav(book.read(nav["href"]), nav["href"])
        if entries:
            return entries
    spine = opf.find("opf:spine", NS)
    ncx = manifest.get(spine.get("toc")) if spine is not None else None
    if ncx is None:
        ncx = next((i for i in manifest.values() if i["type"] == "application/x-dtbncx+xml"), None)
    if ncx is not None and ncx["href"] in names:
        return _read_ncx(book.read(ncx["href"]), ncx["href"])
    return []


def _entry(base: str, href: str, label: str, depth: int) -> TocEntry:
    path, _, fragment = href.partition("#")
    return TocEntry(_resolve(base, path), unquote(fragment) or None, label, depth)


def _read_nav(data: bytes, path: str) -> list[TocEntry]:
    doc = _parse_document(data, path)
    navs = [e for e in doc.iter() if _local(e) == "nav"]
    toc = next((n for n in navs if "toc" in _epub_type(n)), navs[0] if navs else None)
    if toc is None:
        return []
    base = posixpath.dirname(path)
    entries = []
    for a in toc.iter():
        if _local(a) == "a" and a.get("href"):
            depth = sum(1 for p in a.iterancestors() if _local(p) == "ol")
            entries.append(_entry(base, a.get("href"), _text(a), depth))
    return entries


def _read_ncx(data: bytes, path: str) -> list[TocEntry]:
    doc = _parse_xml(data, path)
    nav_map = doc.find("ncx:navMap", NS)
    if nav_map is None:
        return []
    base = posixpath.dirname(path)
    entries = []
    for point in nav_map.iter(f"{{{NS['ncx']}}}navPoint"):
        content = point.find("ncx:content", NS)
        label = point.find("ncx:navLabel/ncx:text", NS)
        if content is not None and content.get("src"):
            depth = sum(1 for p in point.iterancestors() if _local(p) == "navpoint")
            text = _text(label) if label is not None else ""
            entries.append(_entry(base, content.get("src"), text, depth))
    return entries


# ---- Documents into blocks ----


def _epub_type(el: etree._Element) -> str:
    return " ".join(el.get(name, "") for name in EPUB_TYPE).strip()


def _skipped(el: etree._Element) -> bool:
    return (
        _local(el) in SKIPPED
        or bool(SKIPPED_CLASS.search(el.get("class", "")))
        or bool(SKIPPED_TYPE.search(_epub_type(el)))
        or el.get("hidden") is not None
        or "display:none" in el.get("style", "").replace(" ", "")
    )


def _is_note_reference(el: etree._Element) -> bool:
    """A link to a footnote ("[1]", "*") would be read aloud as a number; it is dropped."""
    return _local(el) == "a" and "#" in el.get("href", "") and bool(NOTE_MARKER.match(_text(el)))


class _Walker:
    """Turns one document into blocks and markers."""

    def __init__(self, path: str, doc: etree._Element, targets: dict[str | None, int]):
        self.path = path
        self.tree = doc.getroottree()
        self.targets = targets
        self.stream: list[Block | Marker] = []
        self._emitted: set[int] = set()
        self._pending: list[Span] = []
        self._pending_ref: dict = {}

    def walk(self) -> None:
        self._mark(self.targets.get(None))
        body = next((e for e in self.tree.getroot().iter() if _local(e) == "body"), None)
        if body is not None:
            self._container(body, "paragraph")
        self._flush("paragraph")

    # Markers

    def _mark(self, index: int | None) -> None:
        if index is not None and index not in self._emitted:
            self._emitted.add(index)
            self.stream.append(Marker("toc", index))

    def _ids(self, el: etree._Element, deep: bool) -> list[int]:
        """The table-of-contents entries that point into `el` (or at it, unless `deep`)."""
        found = []
        for e in el.iter() if deep else (el,):
            if isinstance(e.tag, str):
                for name in ("id", "name"):
                    value = e.get(name)
                    if value is not None and value in self.targets:
                        found.append(self.targets[value])
        return found

    def _mark_ids(self, el: etree._Element, deep: bool) -> None:
        for index in self._ids(el, deep):
            self._mark(index)

    def _has_target(self, el: etree._Element) -> bool:
        return bool(self._ids(el, deep=True))

    # Blocks

    def _ref(self, el: etree._Element) -> dict:
        return {"file": self.path, "path": self.tree.getpath(el)}

    def _emit(self, block_type: str, spans: list[Span], ref: dict, level: int | None = None):
        spans = _tidy(spans)
        text = "".join(s.text for s in spans)
        if not text:
            return
        if block_type != "heading" and SECTION_BREAK_TEXT.match(text) and len(text) <= 20:
            self._section_break(ref)
            return
        self.stream.append(Block(block_type, spans, ref, level))

    def _section_break(self, ref: dict) -> None:
        last = self.stream[-1] if self.stream else None
        if not (isinstance(last, Block) and last.type == "section_break"):
            self.stream.append(Block("section_break", [], ref))

    def _flush(self, block_type: str) -> None:
        if self._pending:
            self._emit(block_type, self._pending, self._pending_ref)
        self._pending, self._pending_ref = [], {}

    def _container(self, el: etree._Element, block_type: str) -> None:
        """Block children are handled one by one; loose text and inline elements between them
        are gathered into paragraphs."""
        self._mark_ids(el, deep=False)
        if el.get("id") == "pg-footer":
            self._flush(block_type)
            self.stream.append(Marker("back"))
        if el.get("id") == "pg-header":
            self._flush(block_type)
            self.stream.append(Marker("front"))
        if el.text:
            self._inline_text(el.text, (), el)
        for child in el:
            if not isinstance(child.tag, str):
                pass
            elif _skipped(child) or _is_note_reference(child):
                self._mark_ids(child, deep=True)
            elif _local(child) in BLOCK_TAGS:
                self._flush(block_type)
                self._block(child, block_type)
            else:
                if self._has_target(child):
                    self._flush(block_type)
                    self._mark_ids(child, deep=True)
                if not self._pending:
                    self._pending_ref = self._ref(child)
                self._pending.extend(_spans(child, ()))
            if child.tail:
                self._inline_text(child.tail, (), el)
        self._flush(block_type)
        if el.get("id") == "pg-header":
            self.stream.append(Marker("front_end"))

    def _inline_text(self, text: str, marks: tuple[str, ...], parent: etree._Element) -> None:
        if not self._pending:
            if not text.strip():
                return
            self._pending_ref = self._ref(parent)
        self._pending.append(Span(text, marks))

    def _block(self, el: etree._Element, block_type: str) -> None:
        tag = _local(el)
        kind = _epub_type(el)
        cls = el.get("class", "")
        if tag == "hr":
            self._mark_ids(el, deep=False)
            self._section_break(self._ref(el))
        elif tag in HEADINGS:
            self._mark_ids(el, deep=True)
            self._emit("heading", _spans(el, ()), self._ref(el), HEADINGS[tag])
        elif tag == "blockquote":
            self._container(el, "quote" if block_type == "paragraph" else block_type)
        elif FOOTNOTE_TYPE.search(kind) or re.search(r"\bfootnote", cls, re.I):
            self._container(el, "footnote")
        elif re.search(r"\bletter\b", cls, re.I):
            self._container(el, "letter")
        elif tag in ("ul", "ol"):
            self._container(el, "list_item" if block_type == "paragraph" else block_type)
        elif tag == "tr":
            self._mark_ids(el, deep=True)
            cells = [_tidy(_spans(c, ())) for c in el if _local(c) in ("td", "th")]
            spans: list[Span] = []
            for cell in (c for c in cells if c):
                if spans:
                    spans.append(Span(" — "))
                spans.extend(cell)
            self._emit("list_item", spans, self._ref(el))
        elif tag in CONTAINERS:
            self._container(el, block_type)
        elif any(_local(c) in BLOCK_TAGS for c in el):
            # A leaf such as <li> or a <p> that holds blocks of its own.
            child_type = "list_item" if tag == "li" and block_type == "paragraph" else block_type
            self._container(el, child_type)
        else:
            self._mark_ids(el, deep=True)
            leaf_type = "list_item" if tag == "li" and block_type == "paragraph" else block_type
            self._emit(leaf_type, _spans(el, ()), self._ref(el))


def _marks_of(el: etree._Element, marks: tuple[str, ...]) -> tuple[str, ...]:
    added = []
    tag = _local(el)
    if tag in INLINE_MARKS:
        added.append(INLINE_MARKS[tag])
    if SMALL_CAPS_CLASS.search(el.get("class", "")) or "small-caps" in el.get("style", ""):
        added.append("small_caps")
    style = el.get("style", "").replace(" ", "")
    if "font-style:italic" in style:
        added.append("italic")
    if "font-weight:bold" in style:
        added.append("bold")
    return marks + tuple(m for m in added if m not in marks)


def _spans(el: etree._Element, marks: tuple[str, ...]) -> list[Span]:
    """The text of an element and its descendants, as spans with marks."""
    marks = _marks_of(el, marks)
    spans: list[Span] = []
    if _local(el) == "br":
        spans.append(Span("\n", marks))
    elif el.text:
        spans.append(Span(el.text, marks))
    for child in el:
        if isinstance(child.tag, str) and not _skipped(child) and not _is_note_reference(child):
            spans.extend(_spans(child, marks))
        if child.tail:
            spans.append(Span(child.tail, marks))
    return spans


def _tidy(spans: list[Span]) -> list[Span]:
    """Collapses whitespace (keeping line breaks from <br>), trims the ends, and joins
    neighbouring spans with the same marks."""
    out: list[Span] = []
    for span in spans:
        text = span.text
        if text != "\n":
            # Soft hyphens and zero-width spaces go; every other run of whitespace is a space.
            text = INVISIBLE.sub("", text)
            text = WHITESPACE.sub(" ", text)
        if not text:
            continue
        if out and out[-1].marks == span.marks:
            out[-1] = Span(out[-1].text + text, span.marks)
        else:
            out.append(Span(text, span.marks))
    # Spaces next to line breaks, and runs of either, collapse into one.
    joined = []
    for span in out:
        text = re.sub(r" *\n[ \n]*", "\n", span.text)
        joined.append(Span(text, span.marks))
    out = joined
    for i in range(1, len(out)):
        prev = out[i - 1].text
        if prev.endswith((" ", "\n")) and out[i].text.startswith(" "):
            out[i] = Span(out[i].text.lstrip(" "), out[i].marks)
        elif prev.endswith(" ") and out[i].text.startswith("\n"):
            out[i - 1] = Span(prev.rstrip(" "), out[i - 1].marks)
    while out and not out[0].text.strip():
        out.pop(0)
    while out and not out[-1].text.strip():
        out.pop()
    if out:
        out[0] = Span(out[0].text.lstrip(), out[0].marks)
        out[-1] = Span(out[-1].text.rstrip(), out[-1].marks)
    return [s for s in out if s.text]


# ---- The stream into chapters ----


def _is_top_heading(item: Block | Marker) -> bool:
    return isinstance(item, Block) and item.type == "heading" and (item.level or 9) <= 2


def _split_off_boilerplate(
    stream: list[Block | Marker],
) -> tuple[list[Block], list[Block | Marker], list[Block]]:
    """Project Gutenberg's header and licence, marked by its own ids, are front and back
    matter whatever the table of contents says."""
    front: list[Block] = []
    if any(isinstance(i, Marker) and i.kind == "front_end" for i in stream):
        start = next(n for n, i in enumerate(stream) if isinstance(i, Marker) and i.kind == "front")
        end = next(
            n for n, i in enumerate(stream) if isinstance(i, Marker) and i.kind == "front_end"
        )
        front = [i for i in stream[start:end] if isinstance(i, Block)]
        stream = stream[:start] + stream[end + 1 :]
    back: list[Block] = []
    cut = next(
        (n for n, i in enumerate(stream) if isinstance(i, Marker) and i.kind == "back"), None
    )
    if cut is not None:
        back = [i for i in stream[cut:] if isinstance(i, Block)]
        stream = stream[:cut]
    return front, stream, back


def _cut(stream, is_cut, label_of) -> list[_Segment]:
    segments = [_Segment(None)]
    for item in stream:
        if isinstance(item, Marker):
            if is_cut(item):
                segments.append(_Segment(label_of(item)))
        else:
            segments[-1].blocks.append(item)
    return segments


def _cut_at_headings(stream) -> list[_Segment]:
    segments = [_Segment(None)]
    for item in stream:
        if isinstance(item, Marker):
            continue
        last = segments[-1].blocks[-1] if segments[-1].blocks else None
        if _is_top_heading(item) and not (isinstance(last, Block) and last.type == "heading"):
            segments.append(_Segment(None))
        segments[-1].blocks.append(item)
    return segments


def _leading_headings(blocks: list[Block]) -> list[Block]:
    found = []
    for block in blocks:
        if block.type == "heading":
            found.append(block)
        elif block.type != "section_break":
            break
    return found


def _title(segment: _Segment) -> str | None:
    texts = [normalise_space(h.text) for h in _leading_headings(segment.blocks)]
    texts = [t for t in texts if t]
    if texts:
        parts = [t.rstrip(".:") for t in texts[:-1]] + [texts[-1]]
        return ": ".join(parts)
    return segment.label or None


def _looks_like_chapter(segment: _Segment, headings: ChapterHeadings | None) -> bool:
    if headings is None:
        return False
    candidates = [normalise_space(h.text) for h in _leading_headings(segment.blocks)]
    candidates += [segment.label or ""]
    return any(c and headings.is_heading(c) for c in candidates)


def _trim_breaks(blocks: list[Block]) -> list[Block]:
    while blocks and blocks[0].type == "section_break":
        blocks = blocks[1:]
    while blocks and blocks[-1].type == "section_break":
        blocks = blocks[:-1]
    return blocks


def _arrange(
    segments: list[_Segment], headings: ChapterHeadings | None
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

    merged: list[_Segment] = []
    carry: list[Block] = []
    for segment in segments:
        blocks = carry + segment.blocks
        if all(b.type in ("heading", "section_break") for b in segment.blocks):
            carry = blocks
            continue
        carry = []
        merged.append(_Segment(segment.label, blocks))
    if carry and merged:
        merged[-1].blocks += carry

    chapters = []
    for segment in merged:
        blocks = _trim_breaks(segment.blocks)
        if blocks:
            chapters.append(ImportedChapter(_title(_Segment(segment.label, blocks)), blocks))
    return chapters, _trim_breaks(front), _trim_breaks(back)
