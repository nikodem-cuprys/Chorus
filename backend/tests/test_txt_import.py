import codecs
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.importing import ImportRejected
from chorus.importing.txt import decode, read_txt
from chorus.languages import get_pack

ROOT = Path(__file__).resolve().parents[2] / ".scratch" / "chorus" / "samples"
RAW = ROOT / "raw"
PASSAGES = ROOT / "passages"


def english(_language):
    return get_pack("en").chapter_headings


def read(data: bytes | str, name: str = "book.txt"):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return read_txt(data, english, name)


def texts(blocks) -> list[str]:
    return [b.text for b in blocks]


# ---- The Gutenberg texts ----

GUTENBERG = [
    # file, title, author, chapters, first title, last title
    (
        "pg11.txt", "Alice's Adventures in Wonderland", "Lewis Carroll", 12,
        "CHAPTER I: Down the Rabbit-Hole", "CHAPTER XII: Alice’s Evidence",
    ),
    (
        "pg1260.txt", "Jane Eyre: An Autobiography", "Charlotte Brontë", 38,
        "CHAPTER I", "CHAPTER XXXVIII—CONCLUSION",
    ),
    ("pg1342.txt", "Pride and Prejudice", "Jane Austen", 61, "Chapter I.", "CHAPTER LXI."),
    (
        "pg1661.txt", "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", 12,
        "I. A SCANDAL IN BOHEMIA", "XII. THE ADVENTURE OF THE COPPER BEECHES",
    ),
    (
        "pg2554.txt", "Crime and Punishment", "Fyodor Dostoyevsky", 40,
        "PART I: CHAPTER I", "EPILOGUE",
    ),
    ("pg5200.txt", "Metamorphosis", "Franz Kafka", 3, "I", "III"),
]  # fmt: skip


@pytest.mark.parametrize(
    ("name", "title", "author", "count", "first", "last"), GUTENBERG, ids=[g[0] for g in GUTENBERG]
)
def test_the_gutenberg_texts(name, title, author, count, first, last):
    work = read((RAW / name).read_bytes(), name)
    assert (work.title, work.authors, work.language) == (title, [author], "en")
    assert len(work.chapters) == count
    assert (work.chapters[0].title, work.chapters[-1].title) == (first, last)
    assert work.warnings == [{"key": "import.warning.encoding", "params": {"encoding": "UTF-8"}}]

    # The header and the licence are boilerplate (never voiced), and none of it is in a
    # chapter.
    header = [b for b in work.front_matter if b.boilerplate]
    assert header[0].text.startswith("The Project Gutenberg eBook of")
    assert header[-1].text.startswith("*** START OF THE PROJECT GUTENBERG EBOOK")
    assert all(b.boilerplate for b in work.back_matter)
    assert work.back_matter[0].text.startswith("*** END OF THE PROJECT GUTENBERG EBOOK")
    assert not any("PROJECT GUTENBERG" in c.text.upper() for c in work.chapters)
    assert not any(b.boilerplate for c in work.chapters for b in c.blocks)


def test_crime_and_punishment_parts_open_their_first_chapter():
    work = read((RAW / "pg2554.txt").read_bytes())
    titles = [c.title for c in work.chapters]
    assert [t for t in titles if t.startswith("PART")] == [
        f"PART {n}: CHAPTER I" for n in ("I", "II", "III", "IV", "V", "VI")
    ]
    # The epilogue's numbered sections stay inside it as headings.
    epilogue = work.chapters[-1].blocks
    assert [b.text for b in epilogue if b.type == "heading"] == ["EPILOGUE", "I", "II"]


def test_holmes_sections_stay_inside_their_story():
    work = read((RAW / "pg1661.txt").read_bytes())
    scandal = work.chapters[0].blocks
    assert [b.text for b in scandal if b.type == "heading"] == [
        "I. A SCANDAL IN BOHEMIA",
        "I.",
        "II.",
        "III.",
    ]
    # Every prose line of the next story is indented by one space; it is still prose.
    league = work.chapters[1].blocks
    assert league[1].text.startswith("I had called upon my friend, Mr. Sherlock Holmes, one day")
    assert "\n" not in league[1].text


def test_pride_and_prejudice_heading_inside_an_illustration():
    work = read((RAW / "pg1342.txt").read_bytes())
    first = work.chapters[0].blocks
    assert texts(first[:2]) == [
        "Chapter I.",
        "It is a truth universally acknowledged, that a single man in possession "
        "of a good fortune must be in want of a wife.",
    ]
    assert not any("Illustration" in c.text for c in work.chapters)
    # The blank lines around a dropped illustration are not a Section break.
    assert not any(b.type == "section_break" for b in first)


def test_alice_keeps_italics_and_section_breaks():
    work = read((RAW / "pg11.txt").read_bytes())
    chapter = work.chapters[0].blocks
    italic = [s.text for b in chapter for s in b.spans if "italic" in s.marks]
    assert "through" in italic
    assert any(b.type == "section_break" for c in work.chapters for b in c.blocks)


# ---- Encodings ----


def test_windows_1252():
    text = (PASSAGES / "01-pride-and-prejudice-ch1-2.txt").read_text(encoding="utf-8")
    text = text.replace("Netherfield Park", "Netherfield Park, the café and naïve façade,")
    work = read(text.encode("cp1252"), "pride.txt")
    assert work.warnings[0] == {
        "key": "import.warning.encoding_detected",
        "params": {"encoding": "Windows-1252"},
    }
    blocks = work.front_matter + [b for c in work.chapters for b in c.blocks]
    whole = "\n".join(b.text for b in blocks)
    assert "“My dear Mr. Bennet,” said his lady" in whole
    assert "the café and naïve façade," in whole


def test_windows_1250_polish_is_not_taken_for_1252():
    text = "Litwo! Ojczyzno moja! ty jesteś jak zdrowie. Żółć gęślą jaźń. " * 30
    decoded, warning = decode(text.encode("cp1250"))
    assert decoded == text
    assert warning["params"] == {"encoding": "Windows-1250"}


@pytest.mark.parametrize(
    ("bom", "codec", "name"),
    [
        (codecs.BOM_UTF8, "utf-8", "UTF-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le", "UTF-16"),
        (codecs.BOM_UTF16_BE, "utf-16-be", "UTF-16"),
    ],
)
def test_byte_order_marks(bom, codec, name):
    work = read(bom + "Chapter 1\n\n“Hello,” she said.\n".encode(codec))
    assert work.warnings[0]["params"] == {"encoding": name}
    assert work.chapters[0].blocks[1].text == "“Hello,” she said."


# ---- Structure ----


def test_no_headings_is_one_chapter_with_a_warning():
    work = read("First paragraph,\nwrapped here.\n\nSecond paragraph.\n", "notes.txt")
    assert work.title == "notes"
    assert len(work.chapters) == 1
    assert texts(work.chapters[0].blocks) == ["First paragraph, wrapped here.", "Second paragraph."]
    assert {"key": "import.warning.no_chapters", "params": {}} in work.warnings


def test_section_breaks():
    work = read(
        "Chapter 1\n\nAda.\n\n* * *\n\nBen.\n\n\n\nCal.\n\n***\n\n***\n\nDot.\n\n\n\n"
        "Chapter 2\n\nEve.\n"
    )
    first, second = work.chapters
    assert [b.type for b in first.blocks] == [
        "heading", "paragraph", "section_break", "paragraph", "section_break", "paragraph",
        "section_break", "paragraph",
    ]  # fmt: skip
    assert [b.type for b in second.blocks] == ["heading", "paragraph"]


def test_front_matter_before_the_first_heading():
    work = read("A Title\n\nby Somebody\n\nCHAPTER I\n\nText.\n")
    assert texts(work.front_matter) == ["A Title", "by Somebody"]
    assert not any(b.boilerplate for b in work.front_matter)


def test_a_contents_list_is_not_a_run_of_headings():
    work = read(
        "Contents\n\n CHAPTER I.   One\n CHAPTER II.  Two\n\nCHAPTER I.\nOne\n\nText.\n\n"
        "CHAPTER II.\nTwo\n\nMore.\n"
    )
    assert [c.title for c in work.chapters] == ["CHAPTER I: One", "CHAPTER II: Two"]


def test_verse_keeps_its_lines():
    work = read(
        "Chapter 1\n\n    Twinkle, twinkle, little bat!\n    How I wonder what you’re at!\n"
    )
    assert work.chapters[0].blocks[1].text == (
        "Twinkle, twinkle, little bat!\nHow I wonder what you’re at!"
    )


def test_italics_from_underscores():
    work = read("Chapter 1\n\nShe _would_ go, on _December_ 21_st_.\n")
    spans = [(s.text, s.marks) for s in work.chapters[0].blocks[1].spans]
    assert spans == [
        ("She ", ()),
        ("would", ("italic",)),
        (" go, on ", ()),
        ("December", ("italic",)),
        (" 21", ()),
        ("st", ("italic",)),
        (".", ()),
    ]


def test_an_empty_file_is_rejected():
    with pytest.raises(ImportRejected) as rejected:
        read("\n\n  \n")
    assert rejected.value.key == "import.error.no_text"


# ---- Through the API ----


def test_txt_import_through_the_api():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/works", files={"file": ("pg5200.txt", (RAW / "pg5200.txt").read_bytes())}
        )
        assert response.status_code == 201
        work = client.get(f"/api/works/{response.json()['id']}").json()
        assert work["state"] == "imported"
        assert work["source"]["kind"] == "txt"
        assert (work["title"], work["language"]) == ("Metamorphosis", "en")
        assert [c["title"] for c in work["chapters"]] == ["I", "II", "III"]
        front = client.get(f"/api/works/{work['id']}/matter/front").json()["blocks"]
        assert front[0]["boilerplate"] is True
