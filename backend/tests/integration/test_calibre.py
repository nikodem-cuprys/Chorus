"""Imports through the real Calibre in the Chorus image (ticket 08). Skipped unless
CHORUS_STACK_URL is set; see test_stack.py."""

import io
import os
import struct
import time
import zipfile
from pathlib import Path

import httpx2 as httpx
import pytest

URL = os.environ.get("CHORUS_STACK_URL")
SAMPLES = Path(__file__).resolve().parents[3] / ".scratch" / "chorus" / "samples" / "import"

pytestmark = pytest.mark.skipif(not URL, reason="CHORUS_STACK_URL is not set")


def import_file(client: httpx.Client, name: str, data: bytes) -> dict:
    response = client.post("/api/works", files={"file": (name, data)})
    assert response.status_code == 201, response.text
    work_id = response.json()["id"]
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        work = client.get(f"/api/works/{work_id}").json()
        if work["state"] != "importing":
            return work
        time.sleep(1)
    raise AssertionError(f"{name} was still importing after 10 minutes")


def chapter_texts(client: httpx.Client, work: dict) -> list[str]:
    texts = []
    for chapter in work["chapters"]:
        data = client.get(f"/api/works/{work['id']}/chapters/{chapter['index']}").json()
        words = " ".join("".join(s["text"] for s in b["spans"]) for b in data["blocks"])
        texts.append(" ".join(words.split()))
    return texts


def italics(client: httpx.Client, work: dict) -> list[str]:
    found = []
    for chapter in work["chapters"]:
        data = client.get(f"/api/works/{work['id']}/chapters/{chapter['index']}").json()
        found += [
            s["text"] for b in data["blocks"] for s in b["spans"] if "italic" in s.get("marks", [])
        ]
    return found


def make_docx() -> bytes:
    """A Word document with a title, two "Heading 1" chapters and italic words."""

    def paragraph(text: str, style: str | None = None, italic_word: str | None = None) -> str:
        props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        if italic_word and italic_word in text:
            before, after = text.split(italic_word, 1)
            runs = (
                f'<w:r><w:t xml:space="preserve">{before}</w:t></w:r>'
                f"<w:r><w:rPr><w:i/></w:rPr><w:t>{italic_word}</w:t></w:r>"
                f'<w:r><w:t xml:space="preserve">{after}</w:t></w:r>'
            )
        else:
            runs = f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        return f"<w:p>{props}{runs}</w:p>"

    body = "".join(
        [
            paragraph("The Test Story", "Title"),
            paragraph("Chapter 1", "Heading1"),
            paragraph("It was a dark and stormy night.", italic_word="stormy"),
            paragraph("The rain fell in torrents."),
            paragraph("Chapter 2", "Heading1"),
            paragraph("In the morning it was over.", italic_word="over"),
        ]
    )
    xml = '<?xml version="1.0" encoding="UTF-8"?>'
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    package = "http://schemas.openxmlformats.org/package/2006"
    office = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    word_type = "application/vnd.openxmlformats-officedocument.wordprocessingml"
    styles = (
        f"<w:styles {w}>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="56"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style></w:styles>'
    )

    def relationship(kind: str, target: str) -> str:
        return (
            f'{xml}<Relationships xmlns="{package}/relationships">'
            f'<Relationship Id="rId1" Type="{office}/{kind}" Target="{target}"/></Relationships>'
        )

    files = {
        "[Content_Types].xml": (
            f'{xml}<Types xmlns="{package}/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            f'ContentType="{word_type}.document.main+xml"/>'
            f'<Override PartName="/word/styles.xml" ContentType="{word_type}.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": relationship("officeDocument", "word/document.xml"),
        "word/_rels/document.xml.rels": relationship("styles", "styles.xml"),
        "word/document.xml": f"{xml}<w:document {w}><w:body>{body}</w:body></w:document>",
        "word/styles.xml": f"{xml}{styles}",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as docx:
        for name, content in files.items():
            docx.writestr(name, content)
    return buffer.getvalue()


def locked_mobi() -> bytes:
    """The Alice MOBI with its header saying the text is encrypted (Mobipocket DRM)."""
    data = bytearray((SAMPLES / "alice-gutenberg.mobi").read_bytes())
    record0 = struct.unpack(">I", data[78:82])[0]
    data[record0 + 12 : record0 + 14] = struct.pack(">H", 2)
    return bytes(data)


def test_azw3_and_mobi_give_the_same_work():
    with httpx.Client(base_url=URL, timeout=60) as client:
        azw3 = import_file(client, "alice.azw3", (SAMPLES / "alice-gutenberg.azw3").read_bytes())
        mobi = import_file(client, "alice.mobi", (SAMPLES / "alice-gutenberg.mobi").read_bytes())
        assert azw3["state"] == "imported", azw3["error"]
        assert mobi["state"] == "imported", mobi["error"]
        assert (azw3["source"]["kind"], mobi["source"]["kind"]) == ("azw3", "mobi")
        assert len(azw3["chapters"]) == 12
        assert [c["title"] for c in azw3["chapters"]] == [c["title"] for c in mobi["chapters"]]
        assert chapter_texts(client, azw3) == chapter_texts(client, mobi)


def test_a_docx_keeps_its_headings_and_italics():
    with httpx.Client(base_url=URL, timeout=60) as client:
        work = import_file(client, "story.docx", make_docx())
        assert work["state"] == "imported", work["error"]
        assert work["source"]["kind"] == "docx"
        assert [c["title"] for c in work["chapters"]] == ["Chapter 1", "Chapter 2"]
        assert italics(client, work) == ["stormy", "over"]


def test_an_encrypted_kindle_file_gets_the_drm_message():
    with httpx.Client(base_url=URL, timeout=60) as client:
        work = import_file(client, "locked.mobi", locked_mobi())
        assert work["state"] == "failed"
        assert work["error"]["key"] == "import.error.drm"


def test_a_file_calibre_cannot_read():
    with httpx.Client(base_url=URL, timeout=60) as client:
        work = import_file(client, "notes.xyz", b"not a book at all")
        assert work["state"] == "failed"
        assert work["error"]["key"] == "import.error.unsupported_format"
