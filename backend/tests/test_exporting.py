import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from chorus import exporting
from chorus.app import create_app
from chorus.assembly import assemble_part, parts_of
from chorus.db import get_sessionmaker
from chorus.jobs import JobFailed, enqueue
from chorus.models import Export, Job, JobState, Work, WorkState
from chorus.voicing import voice_work
from chorus.works import work_dir
from tests.test_assembly import Model, make_work

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="needs ffmpeg"
)


@pytest.fixture(autouse=True)
def empty_exports():
    """The exports folder outlives each test's database; start each test with it empty."""
    shutil.rmtree(exporting.exports_dir(), ignore_errors=True)


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
         "-show_chapters", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return json.loads(out.stdout)


def ready_work(session) -> Work:
    """The assembly tests' Work, voiced and assembled: the front matter and two chapters."""
    work = make_work(session)
    voice_work(session, work, Model(), lambda **p: None)
    for part in parts_of(session, work):
        assemble_part(session, work, part)
    work.state = WorkState.READY
    session.commit()
    return work


def test_names_are_safe_on_every_host():
    assert exporting.file_name('What? A "Book": Part 1/2.') == "What A Book Part 1 2"
    assert exporting.file_name("...") == "Untitled"
    assert len(exporting.file_name("x" * 300)) == 80


def test_the_m4b_has_the_audio_chapters_tags_and_cover():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        row = exporting.export_work(session, work, "m4b", lambda **p: None)
        assert row.files == [f"Pauses ({work.id})/Pauses.m4b"]
        info = probe(exporting.exports_dir() / row.files[0])

        audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
        assert (audio["codec_name"], audio["channels"]) == ("aac", 1)
        cover = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert cover["disposition"]["attached_pic"] == 1
        assert (cover["width"], cover["height"]) == (1400, 1400)  # the title card
        tags = info["format"]["tags"]
        assert (tags["title"], tags["artist"]) == ("Pauses", "A. Writer")

        chapters = info["chapters"]
        assert [c["tags"]["title"] for c in chapters] == [
            "Front matter",
            "Chapter One",
            "Chapter Two",
        ]
        lengths = [float(c["end_time"]) - float(c["start_time"]) for c in chapters]
        expected = [work.matter_audio["front"]["seconds"]] + [
            c.audio["seconds"] for c in work.chapters
        ]
        assert lengths == pytest.approx(expected, abs=0.002)
        assert float(info["format"]["duration"]) == pytest.approx(sum(expected), abs=0.1)


def test_the_mp3s_are_numbered_and_tagged():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        row = exporting.export_work(session, work, "mp3", lambda **p: None)
        folder = f"Pauses ({work.id})/MP3"
        assert row.files == [
            f"{folder}/01 - Front matter.mp3",
            f"{folder}/02 - Chapter One.mp3",
            f"{folder}/03 - Chapter Two.mp3",
        ]
        for number, name in enumerate(row.files, start=1):
            info = probe(exporting.exports_dir() / name)
            audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
            assert (audio["codec_name"], audio["channels"], audio["bit_rate"]) == (
                "mp3", 1, "96000",
            )  # fmt: skip
            assert any(s["codec_type"] == "video" for s in info["streams"])  # the cover
            tags = info["format"]["tags"]
            assert tags["track"] == f"{number}/3"
            assert (tags["artist"], tags["album"]) == ("A. Writer", "Pauses")
        assert probe(exporting.exports_dir() / row.files[1])["format"]["tags"]["title"] == (
            "Chapter One"
        )


def test_the_sources_cover_is_used():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        work_dir(work.id).mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 900), (200, 30, 30)).save(work_dir(work.id) / "cover.png")
        work.cover_file = "cover.png"
        session.commit()
        row = exporting.export_work(session, work, "m4b", lambda **p: None)
        info = probe(exporting.exports_dir() / row.files[0])
        cover = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (cover["width"], cover["height"]) == (600, 900)


def test_a_new_export_replaces_the_one_of_its_kind():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        first = exporting.export_work(session, work, "m4b", lambda **p: None)
        mp3 = exporting.export_work(session, work, "mp3", lambda **p: None)
        work.title = "Renamed"
        session.commit()
        second = exporting.export_work(session, work, "m4b", lambda **p: None)
        rows = session.scalars(select(Export).order_by(Export.id)).all()
        assert [r.id for r in rows] == [mp3.id, second.id]
        assert not (exporting.exports_dir() / first.files[0]).exists()
        assert (exporting.exports_dir() / second.files[0]).is_file()
        # No staging folders are left behind.
        assert not list(exporting.exports_dir().rglob(".export-*"))


def test_a_work_that_is_not_ready_is_refused():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        work.state = WorkState.VOICING
        session.commit()
        with pytest.raises(JobFailed) as refused:
            exporting.export_work(session, work, "mp3", lambda **p: None)
        assert refused.value.key == "export.error.not_ready"
        response = TestClient(create_app()).post(
            f"/api/works/{work.id}/exports", json={"kind": "m4b"}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["key"] == "export.error.not_ready"


def test_the_job_and_the_api():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        client = TestClient(create_app())
        assert client.post(f"/api/works/{work.id}/exports", json={"kind": "mp3"}).status_code == 202
        assert client.post(f"/api/works/{work.id}/exports", json={"kind": "wav"}).status_code == 422
        job = session.scalars(select(Job).where(Job.kind == "export")).one()
        assert job.state == JobState.DONE and job.progress["percent"] == 100

        exports = client.get(f"/api/works/{work.id}").json()["exports"]
        assert [(e["kind"], e["folder"], len(e["files"])) for e in exports] == [
            ("mp3", f"Pauses ({work.id})", 3),
        ]  # fmt: skip
        download = client.get(exports[0]["download_url"])
        assert download.status_code == 200
        # A name with spaces and brackets is sent percent-encoded.
        assert f"Pauses%20%28{work.id}%29.zip" in download.headers["content-disposition"]
        names = zipfile.ZipFile(io.BytesIO(download.content)).namelist()
        assert names == ["01 - Front matter.mp3", "02 - Chapter One.mp3", "03 - Chapter Two.mp3"]

        assert client.delete(f"/api/exports/{exports[0]['id']}").status_code == 204
        assert client.get(f"/api/works/{work.id}").json()["exports"] == []
        assert not (exporting.exports_dir() / f"Pauses ({work.id})").exists()
        assert client.delete(f"/api/exports/{exports[0]['id']}").status_code == 404


def test_the_m4b_downloads_as_itself():
    with get_sessionmaker()() as session:
        work = ready_work(session)
        enqueue(session, "export", work_id=work.id, export_kind="m4b")
        row = session.scalars(select(Export)).one()
        download = TestClient(create_app()).get(f"/api/exports/{row.id}/download")
        assert download.status_code == 200
        assert download.headers["content-type"] == "audio/mp4"
        assert 'filename="Pauses.m4b"' in download.headers["content-disposition"]
