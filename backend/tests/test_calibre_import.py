"""The Calibre route, with a stand-in for `ebook-convert` (Calibre itself runs in the Chorus
image; `tests/integration/test_calibre.py` converts the real samples there)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.config import get_settings
from chorus.importing import ImportRejected, calibre
from chorus.importing.calibre import convert_to_epub

AO3 = Path(__file__).resolve().parents[2] / ".scratch" / "chorus" / "samples" / "import"
AO3 = AO3 / "ao3-style-with-notes.epub"


@pytest.fixture
def fake_calibre(tmp_path, monkeypatch):
    """Installs a stand-in for ebook-convert whose body is the given Python code; it gets
    `source` and `target` as paths."""

    def install(body: str) -> None:
        script = tmp_path / "ebook_convert.py"
        script.write_text(
            "import shutil, sys, time\nfrom pathlib import Path\n"
            "source, target = Path(sys.argv[1]), Path(sys.argv[2])\n" + body,
            encoding="utf-8",
        )
        monkeypatch.setattr(calibre, "_command", lambda: [sys.executable, str(script)])

    return install


def rejected(data: bytes, extension: str) -> ImportRejected:
    with pytest.raises(ImportRejected) as caught:
        convert_to_epub(data, extension)
    return caught.value


def test_a_converted_book_is_read_as_epub_and_keeps_its_own_kind(fake_calibre):
    fake_calibre(
        f"assert source.suffix == '.azw3' and source.read_bytes() == b'kindle book'\n"
        f"shutil.copy({str(AO3)!r}, target)\n"
        "print('Output saved to', target)\n"
    )
    with TestClient(create_app()) as client:
        response = client.post("/api/works", files={"file": ("Story.AZW3", b"kindle book")})
        work = client.get(f"/api/works/{response.json()['id']}").json()
    assert work["state"] == "imported", work["error"]
    assert work["source"]["kind"] == "azw3"
    assert [c["title"] for c in work["chapters"]] == [
        "Chapter 1: Transformed",
        "Chapter 2: The Door",
    ]


def test_drm_is_recognised(fake_calibre):
    fake_calibre(
        "print('Traceback (most recent call last):')\n"
        "print('calibre.ebooks.DRMError: This file is locked with DRM')\n"
        "sys.exit(1)\n"
    )
    assert rejected(b"locked", ".azw").key == "import.error.drm"


def test_a_format_calibre_cannot_read(fake_calibre):
    fake_calibre("print('ValueError: No plugin to handle input format: xyz')\nsys.exit(1)\n")
    error = rejected(b"?", ".xyz")
    assert (error.key, error.params) == ("import.error.unsupported_format", {"format": "xyz"})


def test_a_file_without_an_extension_is_not_sent_to_calibre(fake_calibre):
    fake_calibre("raise SystemExit('should not run')\n")
    assert rejected(b"?", "").key == "import.error.unsupported_format"


def test_any_other_failure(fake_calibre):
    fake_calibre("print('Conversion error: something odd')\nsys.exit(1)\n")
    error = rejected(b"?", ".docx")
    assert error.key == "import.error.conversion_failed"
    assert "something odd" in error.detail


def test_the_time_limit(fake_calibre, monkeypatch):
    monkeypatch.setattr(get_settings(), "calibre_timeout_seconds", 1)
    fake_calibre("time.sleep(30)\n")
    error = rejected(b"slow", ".mobi")
    assert (error.key, error.params) == ("import.error.conversion_timeout", {"minutes": 1})


def test_calibre_missing(monkeypatch):
    monkeypatch.setattr(calibre, "_command", lambda: ["no-such-ebook-convert"])
    assert rejected(b"?", ".mobi").key == "import.error.converter_missing"


def test_a_failed_conversion_fails_the_work(fake_calibre):
    fake_calibre("print('calibre.ebooks.DRMError')\nsys.exit(1)\n")
    with TestClient(create_app()) as client:
        response = client.post("/api/works", files={"file": ("locked.mobi", b"x")})
        work = client.get(f"/api/works/{response.json()['id']}").json()
    assert (work["state"], work["error"]) == ("failed", {"key": "import.error.drm", "params": {}})
    assert work["source"]["kind"] == "mobi"
