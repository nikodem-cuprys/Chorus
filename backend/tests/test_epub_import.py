import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.importing import ImportRejected
from chorus.importing.epub import read_epub
from chorus.languages import get_pack

SAMPLES = Path(__file__).resolve().parents[2] / ".scratch" / "chorus" / "samples" / "import"
GUTENBERG = SAMPLES / "pride-and-prejudice-gutenberg.epub"
AO3 = SAMPLES / "ao3-style-with-notes.epub"

ROMAN = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
    "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII",
    "XXVIII", "XXIX", "XXX", "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV", "XXXVI", "XXXVII",
    "XXXVIII", "XXXIX", "XL", "XLI", "XLII", "XLIII", "XLIV", "XLV", "XLVI", "XLVII", "XLVIII",
    "XLIX", "L", "LI", "LII", "LIII", "LIV", "LV", "LVI", "LVII", "LVIII", "LIX", "LX", "LXI",
]  # fmt: skip


def english(_language):
    return get_pack("en").chapter_headings


def read(path_or_bytes) -> object:
    data = path_or_bytes.read_bytes() if isinstance(path_or_bytes, Path) else path_or_bytes
    return read_epub(data, english)


def italics(blocks) -> list[str]:
    return [s.text for b in blocks for s in b.spans if "italic" in s.marks]


def make_epub(
    documents: dict[str, str],
    nav: list[tuple[str, str]] | None = None,
    language: str | None = "en",
    extra: dict[str, str] | None = None,
) -> bytes:
    """A minimal EPUB 3 with these XHTML bodies in spine order and, optionally, a nav."""
    manifest = "".join(
        f'<item id="d{n}" href="{name}" media-type="application/xhtml+xml"/>'
        for n, name in enumerate(documents)
    )
    spine = "".join(f'<itemref idref="d{n}"/>' for n in range(len(documents)))
    if nav is not None:
        manifest += (
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        )
    lang = f"<dc:language>{language}</dc:language>" if language else ""
    opf = (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Test</dc:title>'
        f"<dc:creator>A. Writer</dc:creator>{lang}</metadata>"
        f"<manifest>{manifest}</manifest><spine>{spine}</spine></package>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("mimetype", "application/epub+zip")
        book.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        book.writestr("OEBPS/content.opf", opf)
        for name, body in documents.items():
            book.writestr(
                f"OEBPS/{name}",
                '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
                f"<head><title>x</title></head><body>{body}</body></html>",
            )
        if nav is not None:
            items = "".join(f'<li><a href="{href}">{label}</a></li>' for label, href in nav)
            book.writestr(
                "OEBPS/nav.xhtml",
                '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head>'
                f'<body><nav epub:type="toc"><ol>{items}</ol></nav></body></html>',
            )
        for name, content in (extra or {}).items():
            book.writestr(name, content)
    return buffer.getvalue()


def encryption_xml(algorithm: str, uri: str) -> str:
    return (
        '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
        'xmlns:enc="http://www.w3.org/2001/04/xmlenc#"><enc:EncryptedData>'
        f'<enc:EncryptionMethod Algorithm="{algorithm}"/>'
        f'<enc:CipherData><enc:CipherReference URI="{uri}"/></enc:CipherData>'
        "</enc:EncryptedData></encryption>"
    )


# ---- The sample fixtures ----


def test_the_gutenberg_epub():
    work = read(GUTENBERG)
    assert work.title == "Pride and Prejudice"
    assert work.authors == ["Jane Austen"]
    assert work.language == "en"
    assert work.cover_type == "jpg" and work.cover[:2] == b"\xff\xd8"
    assert work.warnings == []

    assert len(work.chapters) == 61
    numbers = [c.title.upper().replace("CHAPTER", "").strip(" .") for c in work.chapters]
    assert numbers == ROMAN
    assert work.chapters[0].title == "Chapter I."
    first = work.chapters[0].blocks
    assert first[0].type == "heading"
    assert first[1].text.startswith("IT is a truth universally acknowledged")
    # Illustration captions in the headings are dropped.
    assert work.chapters[1].title == "CHAPTER II."
    assert "I hope Mr. Bingley will like it" not in work.chapters[1].blocks[0].text

    # Gutenberg's header, the preface and the list of illustrations are front matter; the
    # licence is back matter. None of it is in a chapter.
    assert work.front_matter[0].text.startswith("The Project Gutenberg eBook of")
    assert work.front_matter[0].boilerplate and work.back_matter[0].boilerplate
    assert not any(b.boilerplate for b in work.front_matter if "PREFACE" in b.text)
    assert work.back_matter[0].text.startswith("*** END OF THE PROJECT GUTENBERG EBOOK")
    assert not any("Gutenberg" in c.text for c in work.chapters)


def test_the_gutenberg_epub_keeps_italics():
    work = read(GUTENBERG)
    chapter = work.chapters[0].blocks
    you = next(b for b in chapter if b.text.startswith("“You want to tell me"))
    assert [(s.text, s.marks) for s in you.spans[:3]] == [
        ("“", ()),
        ("You", ("italic",)),
        (" want to tell me, and I have no objection to hearing it.”", ()),
    ]
    assert "Her" in italics(chapter)


def test_the_ao3_layout_epub():
    work = read(AO3)
    assert work.title == "The Morning After"
    assert work.authors == ["test_author"]
    assert work.is_ao3
    assert [c.title for c in work.chapters] == ["Chapter 1: Transformed", "Chapter 2: The Door"]
    assert italics(work.chapters[0].blocks) == ["“What’s happened to me?”"]
    assert italics(work.chapters[1].blocks) == ["“God in Heaven!”"]
    assert work.front_matter[0].text == "The Morning After"
    assert work.front_matter[1].text == "by test_author"
    assert work.back_matter[0].text == "Afterword"
    # The summary in the preface is a block quotation; AO3's own parser (M2) will make it
    # metadata instead.
    assert any(
        b.type == "quote" and b.text.startswith("Gregor wakes up") for b in work.front_matter
    )


# ---- Rejections ----


def test_an_epub_with_encryption_is_rejected_as_drm():
    data = make_epub(
        {"c1.xhtml": "<p>Text.</p>"},
        extra={
            "META-INF/encryption.xml": encryption_xml(
                "http://www.w3.org/2001/04/xmlenc#aes128-cbc", "OEBPS/c1.xhtml"
            )
        },
    )
    with pytest.raises(ImportRejected) as rejected:
        read(data)
    assert rejected.value.key == "import.error.drm"


def test_obfuscated_fonts_are_not_drm():
    data = make_epub(
        {"c1.xhtml": "<p>Text.</p>"},
        extra={
            "META-INF/encryption.xml": encryption_xml(
                "http://www.idpf.org/2008/embedding", "OEBPS/fonts/serif.otf"
            )
        },
    )
    assert read(data).chapters[0].blocks[0].text == "Text."


def test_a_file_that_is_not_a_zip_is_rejected():
    with pytest.raises(ImportRejected) as rejected:
        read(b"not an epub")
    assert rejected.value.key == "import.error.unreadable"


# ---- Chapters without a table of contents ----


def test_without_a_toc_each_spine_document_is_a_chapter():
    work = read(
        make_epub({"a.xhtml": "<h1>One</h1><p>First.</p>", "b.xhtml": "<h1>Two</h1><p>Second.</p>"})
    )
    assert [c.title for c in work.chapters] == ["One", "Two"]
    assert work.warnings == [{"key": "import.warning.split_by_files", "params": {}}]


def test_without_a_toc_a_long_document_is_split_at_headings():
    body = "<h2>One</h2><p>First.</p><h2>Two</h2><h3>A subtitle</h3><p>Second.</p>"
    work = read(make_epub({"all.xhtml": body}))
    assert [c.title for c in work.chapters] == ["One", "Two: A subtitle"]
    assert work.warnings == [{"key": "import.warning.split_by_headings", "params": {}}]


def test_toc_entries_inside_one_document():
    body = (
        '<p>Dedication.</p><h2 id="c1">Chapter 1</h2><p>First.</p>'
        '<p>More of the <span id="c2">first</span>.</p><h2 id="c2b">Chapter 2</h2><p>Second.</p>'
    )
    nav = [("Chapter 1", "all.xhtml#c1"), ("Chapter 2", "all.xhtml#c2b")]
    work = read(make_epub({"all.xhtml": body}, nav=nav))
    assert [c.title for c in work.chapters] == ["Chapter 1", "Chapter 2"]
    assert [b.text for b in work.front_matter] == ["Dedication."]
    assert work.chapters[0].blocks[-1].text == "More of the first."


def test_a_part_title_page_joins_the_next_chapter():
    nav = [("Part One", "p1.xhtml"), ("Chapter 1", "c1.xhtml"), ("Chapter 2", "c2.xhtml")]
    work = read(
        make_epub(
            {
                "p1.xhtml": "<h1>Part One</h1>",
                "c1.xhtml": "<h2>Chapter 1</h2><p>First.</p>",
                "c2.xhtml": "<h2>Chapter 2</h2><p>Second.</p>",
            },
            nav=nav,
        )
    )
    assert [c.title for c in work.chapters] == ["Part One: Chapter 1", "Chapter 2"]


# ---- Blocks and marks ----


def test_block_kinds_and_marks():
    body = (
        "<h2>Chapter 1</h2>"
        "<p>Plain <i>italic</i> <b>bold <i>both</i></b> <span class='smcap'>caps</span> "
        "x<sup>2</sup> soft­hyphen<a href='#n1'>[1]</a>.</p>"
        "<blockquote><p>A quotation.</p></blockquote>"
        "<p>* * *</p>"
        "<ul><li>An item</li></ul>"
        "<div class='letter'><p>Dear Sir,</p></div>"
        "<aside epub:type='footnote' xmlns:epub='http://www.idpf.org/2007/ops'>"
        "<p>A note.</p></aside>"
        "<div class='figcenter'><img src='x.png'/><p class='caption'>A caption</p></div>"
        "<p>Line one<br/>line two</p>"
    )
    blocks = read(make_epub({"c.xhtml": body})).chapters[0].blocks
    assert [(b.type, b.text) for b in blocks] == [
        ("heading", "Chapter 1"),
        ("paragraph", "Plain italic bold both caps x2 softhyphen."),
        ("quote", "A quotation."),
        ("section_break", ""),
        ("list_item", "An item"),
        ("letter", "Dear Sir,"),
        ("footnote", "A note."),
        ("paragraph", "Line one\nline two"),
    ]
    assert [(s.text, s.marks) for s in blocks[1].spans] == [
        ("Plain ", ()),
        ("italic", ("italic",)),
        (" ", ()),
        ("bold ", ("bold",)),
        ("both", ("bold", "italic")),
        (" ", ()),
        ("caps", ("small_caps",)),
        (" x", ()),
        ("2", ("superscript",)),
        (" softhyphen.", ()),
    ]


# ---- Language ----


def test_regional_language_codes_count_as_the_base_language():
    assert read(make_epub({"c.xhtml": "<p>Text.</p>"}, language="en-GB")).language == "en"


def test_no_stated_language():
    assert read(make_epub({"c.xhtml": "<p>Text.</p>"}, language=None)).language is None


# ---- Through the API ----


def upload(client: TestClient, name: str, data: bytes) -> dict:
    response = client.post("/api/works", files={"file": (name, data, "application/epub+zip")})
    assert response.status_code == 201, response.text
    return client.get(f"/api/works/{response.json()['id']}").json()


def test_import_through_the_api():
    with TestClient(create_app()) as client:
        work = upload(client, "ao3.epub", AO3.read_bytes())
        assert work["state"] == "imported"
        assert work["title"] == "The Morning After"
        assert work["language"] == "en" and work["language_source"] == "metadata"
        assert work["has_language_pack"]
        assert [c["title"] for c in work["chapters"]] == [
            "Chapter 1: Transformed",
            "Chapter 2: The Door",
        ]
        chapter = client.get(f"/api/works/{work['id']}/chapters/1").json()
        assert chapter["blocks"][0] == {
            "type": "heading",
            "level": 2,
            "spans": [{"text": "Chapter 1: Transformed"}],
            "ref": {"file": "OEBPS/chapter1.xhtml", "path": "/*/*[2]/*[1]/*[1]"},
        }
        front = client.get(f"/api/works/{work['id']}/matter/front").json()["blocks"]
        assert front[0]["spans"] == [{"text": "The Morning After"}]

        listed = client.get("/api/works").json()
        assert [(w["title"], w["state"]) for w in listed] == [("The Morning After", "imported")]
        jobs = client.get("/api/jobs").json()
        assert [(j["kind"], j["state"], j["work_id"]) for j in jobs] == [
            ("import", "done", work["id"])
        ]


def test_the_cover_is_kept():
    with TestClient(create_app()) as client:
        work = upload(client, "pride.epub", GUTENBERG.read_bytes())
        assert len(work["chapters"]) == 61
        cover = client.get(work["cover_url"])
        assert cover.headers["content-type"] == "image/jpeg"


def test_a_drm_epub_fails_with_the_drm_message():
    data = make_epub(
        {"c1.xhtml": "<p>Text.</p>"},
        extra={"META-INF/encryption.xml": encryption_xml("urn:adobe:adept", "OEBPS/c1.xhtml")},
    )
    with TestClient(create_app()) as client:
        work = upload(client, "locked.epub", data)
        assert work["state"] == "failed"
        assert work["error"] == {"key": "import.error.drm", "params": {}}
        job = client.get("/api/jobs").json()[0]
        assert job["state"] == "failed"
        assert job["error"] == {"key": "import.error.drm", "params": {}}


def test_formats_not_read_yet_fail_with_a_message():
    with TestClient(create_app()) as client:
        work = upload(client, "notes.odt", b"something")
        assert work["state"] == "failed"
        assert work["error"]["key"] == "import.error.unsupported"


def test_the_language_detector_fills_in_a_missing_language():
    text = " ".join(
        ["Es war einmal ein kleines Mädchen, das wohnte mit seiner Mutter in einem Haus am Wald."]
        * 5
    )
    with TestClient(create_app()) as client:
        work = upload(client, "de.epub", make_epub({"c.xhtml": f"<p>{text}</p>"}, language=None))
        assert (work["language"], work["language_source"]) == ("de", "detector")
        assert not work["has_language_pack"]


def test_changing_the_language():
    with TestClient(create_app()) as client:
        work = upload(client, "ao3.epub", AO3.read_bytes())
        url = f"/api/works/{work['id']}"
        changed = client.patch(url, json={"language": "pl"}).json()
        assert (changed["language"], changed["language_source"]) == ("pl", "user")
        assert not changed["has_language_pack"]
        back = client.patch(url, json={"language": "en"}).json()
        assert back["has_language_pack"]
        assert client.patch(url, json={"language": "English"}).status_code == 422

        languages = client.get("/api/languages").json()
        assert {"code": "en", "has_pack": True} in languages
        assert {"code": "pl", "has_pack": False} in languages
