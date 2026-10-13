from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.importing import ImportRejected
from chorus.importing.pdf import read_pdf
from chorus.languages import get_pack
from tests.pdfs import book, make_pdf, with_bookmarks

SAMPLES = Path(__file__).resolve().parents[2] / ".scratch" / "chorus" / "samples"
FIXTURE = SAMPLES / "import" / "hard-two-column.pdf"


def read(data: bytes, name: str = "book.pdf"):
    return read_pdf(data, lambda _language: get_pack("en"), name)


def paragraphs(chapter) -> list[str]:
    return [b.text for b in chapter.blocks if b.type == "paragraph"]


def source(name: str) -> list[str]:
    """A sample passage as the fixture's builder laid it out: underscores dropped, and in
    Windows-1252 (which has every character these passages use)."""
    text = (SAMPLES / "passages" / name).read_text(encoding="utf-8")
    return [
        " ".join(p.replace("_", "").split()).encode("cp1252", "replace").decode("cp1252")
        for p in text.split("\n\n")
        if p.strip() and not p.startswith("#")
    ]


# ---- The two-column fixture ----


def test_the_two_column_fixture():
    work = read(FIXTURE.read_bytes(), "hard-two-column.pdf")
    assert [c.title for c in work.chapters] == ["CHAPTER I", "CHAPTER II"]
    # Every paragraph comes back exactly as written: the columns are read in order, the running
    # headers and page numbers are gone, and the 60 hyphens at line ends are resolved.
    assert paragraphs(work.chapters[0]) == source("04-jane-eyre-ch1.txt")
    assert paragraphs(work.chapters[1]) == source("03-holmes-scandal-in-bohemia.txt")
    whole = "\n".join(b.text for c in work.chapters for b in c.blocks)
    assert "JANE EYRE AND OTHER STORIES" not in whole
    assert "PUBLIC DOMAIN TEST EDITION" not in whole
    assert work.warnings == [
        {"key": "import.warning.pdf_headers_removed", "params": {"count": 4}},
        {"key": "import.warning.pdf_page_numbers_removed", "params": {"count": 4}},
    ]
    assert work.chapters[0].blocks[1].ref == {"page": 1}


# ---- Headers, footers and page numbers ----


SENTENCES = [
    "The rain had not stopped since morning.",
    "Nobody in the house could remember a wetter spring.",
    "By noon the river had reached the garden wall.",
    "The cook said she had seen worse, and nobody believed her.",
    "At four the lamps were lit early.",
    "Supper was cold, and nobody minded.",
]


def test_running_headers_and_page_numbers_are_removed():
    pages = [[sentence] for sentence in SENTENCES]
    pages[0].insert(0, "# Chapter 1")
    work = read(book(pages, header="THE TITLE OF THE BOOK"))
    text = "\n".join(b.text for c in work.chapters for b in c.blocks)
    assert "THE TITLE OF THE BOOK" not in text
    assert "By noon the river had reached the garden wall." in text
    assert not any(b.text.isdigit() for c in work.chapters for b in c.blocks)
    assert {"key": "import.warning.pdf_headers_removed", "params": {"count": 6}} in work.warnings
    assert {"key": "import.warning.pdf_page_numbers_removed", "params": {"count": 6}} in (
        work.warnings
    )


def test_a_header_with_the_page_number_in_it_is_still_a_header():
    pdf = make_pdf(
        [
            [("R", 8, 72, 805, f"Page {n} — My Book"), ("R", 11, 72, 700, sentence)]
            for n, sentence in enumerate(SENTENCES[:4], start=1)
        ]
    )
    work = read(pdf)
    assert [b.text for b in work.chapters[0].blocks if "My Book" in b.text] == []
    assert " ".join(work.chapters[0].text.split()) == " ".join(SENTENCES[:4])


def test_a_line_near_the_top_that_does_not_repeat_stays():
    pages = [
        [("R", 11, 72, 790, sentence), ("R", 11, 72, 700, "And then the page went on.")]
        for sentence in SENTENCES[:4]
    ]
    work = read(make_pdf(pages))
    assert SENTENCES[2] in work.chapters[0].text


# ---- Hyphens ----


def hyphen_pdf(lines: list[str]) -> bytes:
    return make_pdf([[("R", 11, 72, 700 - 14 * n, line) for n, line in enumerate(lines)]])


def test_line_end_hyphens():
    work = read(
        hyphen_pdf(
            [
                "It was a beauti-",
                "ful morning, and the well-known road ran past a",
                "well-",
                "known inn and on to Saint-",
                "Malo, where the sea-",
                "side lay in a dull and dark and ex-",
                "tremely heavy fog.",
            ]
        )
    )
    assert work.chapters[0].blocks[0].text == (
        "It was a beautiful morning, and the well-known road ran past a well-known inn and on "
        "to Saint-Malo, where the seaside lay in a dull and dark and extremely heavy fog."
    )


# ---- Italics ----


def test_italics_from_the_font_name():
    work = read(hyphen_pdf(["She would {I}never{R} go there again."]))
    spans = [(s.text, s.marks) for s in work.chapters[0].blocks[0].spans]
    assert spans == [("She would ", ()), ("never", ("italic",)), (" go there again.", ())]


# ---- Chapters ----


def test_chapters_from_headings_matching_the_patterns():
    work = read(
        book(
            [
                ["# The Complete Book", "A preface of some length, set before the story."],
                ["# Chapter 1", "The first chapter begins here.", "It goes on."],
                ["# Chapter 2", "The second chapter begins here."],
            ]
        )
    )
    assert [c.title for c in work.chapters] == ["Chapter 1", "Chapter 2"]
    assert [b.text for b in work.front_matter] == [
        "The Complete Book",
        "A preface of some length, set before the story.",
    ]
    assert paragraphs(work.chapters[0]) == ["The first chapter begins here.", "It goes on."]


def test_chapters_from_large_headings_without_numbers():
    work = read(
        book(
            [
                ["# The Boy Who Lived", "Mr and Mrs Dursley were proud to say."],
                ["# The Vanishing Glass", "Nearly ten years had passed."],
            ]
        )
    )
    assert [c.title for c in work.chapters] == ["The Boy Who Lived", "The Vanishing Glass"]
    assert {"key": "import.warning.split_by_headings", "params": {}} in work.warnings


def test_chapters_from_bookmarks():
    data = with_bookmarks(
        book(
            [
                ["Title page text."],
                ["The first part of the story."],
                ["The second part of the story."],
            ]
        ),
        [("Opening", 1), ("Ending", 2)],
    )
    work = read(data)
    assert [(c.title, paragraphs(c)) for c in work.chapters] == [
        ("Opening", ["The first part of the story."]),
        ("Ending", ["The second part of the story."]),
    ]
    assert [b.text for b in work.front_matter] == ["Title page text."]


def test_no_headings_is_one_chapter():
    work = read(book([["Just some text."], ["And more text."]]))
    assert len(work.chapters) == 1
    assert {"key": "import.warning.no_chapters", "params": {}} in work.warnings


# ---- Rejections ----


def test_a_pdf_of_images_is_rejected_as_scanned():
    with pytest.raises(ImportRejected) as rejected:
        read(make_pdf([[], []], image_only=True))
    assert rejected.value.key == "import.error.scanned_pdf"


def test_a_cover_image_page_is_skipped_with_a_warning():
    pages = [[]] + [[("R", 11, 72, 700, f"Text of page {n}.")] for n in range(2, 5)]
    work = read(make_pdf(pages, image_only=True))
    assert {"key": "import.warning.pdf_pages_without_text", "params": {"count": 1}} in (
        work.warnings
    )


def test_a_password_protected_pdf_is_rejected():
    data = with_bookmarks(book([["Secret text."]]), [], password="secret")
    with pytest.raises(ImportRejected) as rejected:
        read(data)
    assert rejected.value.key == "import.error.drm"


def test_not_a_pdf():
    with pytest.raises(ImportRejected) as rejected:
        read(b"%PDF-1.4 this is not really a pdf")
    assert rejected.value.key == "import.error.unreadable"


# ---- Through the API ----


def test_pdf_import_through_the_api():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/works", files={"file": ("hard-two-column.pdf", FIXTURE.read_bytes())}
        )
        work = client.get(f"/api/works/{response.json()['id']}").json()
        assert work["state"] == "imported"
        assert work["source"]["kind"] == "pdf"
        assert [c["title"] for c in work["chapters"]] == ["CHAPTER I", "CHAPTER II"]
        assert work["language"] == "en" and work["language_source"] == "detector"

        scanned = client.post(
            "/api/works", files={"file": ("scan.pdf", make_pdf([[]], image_only=True))}
        )
        failed = client.get(f"/api/works/{scanned.json()['id']}").json()
        assert failed["error"] == {"key": "import.error.scanned_pdf", "params": {}}
