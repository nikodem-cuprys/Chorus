import json
import shutil

import numpy as np
import pytest
import soundfile
from fastapi.testclient import TestClient
from sqlalchemy import select

from chorus import assembly, voicing
from chorus.app import create_app
from chorus.assembly import MARGIN, assemble_part, audio_dir, parts_of, pauses_after, trim
from chorus.casting import cast_work
from chorus.db import get_sessionmaker
from chorus.importing import Block, Span
from chorus.jobs import enqueue
from chorus.languages import get_packs
from chorus.models import Chapter, Job, JobState, Line, Work, WorkState
from chorus.script import build_script
from chorus.voices import sync_built_in_voices
from chorus.voicing import pauses, voice_work

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")

PACK = get_packs()["en"]
RATE = 24_000
LEAD, TAIL = 0.2, 0.3  # the stand-in model's silence before and after what it says


class Model:
    """Says a tenth of a second of noise per word, with silence before and after it."""

    sample_rate = RATE

    def __init__(self, fail_after: int | None = None):
        self.fail_after = fail_after
        self.spoken = 0

    def speak(self, batch):
        for speech in batch:
            if self.fail_after is not None and self.spoken >= self.fail_after:
                raise RuntimeError("the worker was killed")
            self.spoken += 1
            rng = np.random.default_rng([speech.seed, len(speech.text)])
            said = rng.uniform(-0.5, 0.5, RATE * len(speech.text.split()) // 10)
            lead, tail = np.zeros(int(LEAD * RATE)), np.zeros(int(TAIL * RATE))
            yield speech, np.concatenate([lead, said, tail])


def block(text: str, type: str = "paragraph") -> dict:
    return Block(type, [Span(text)] if text else []).to_dict()


def make_work(session) -> Work:
    """A title, then two chapters: one with every kind of pause, and a short one."""
    sync_built_in_voices(session, get_packs())
    work = Work(
        title="Pauses", authors=["A. Writer"], source_kind="txt", source_name="t",
        state=WorkState.ANALYSED,
    )  # fmt: skip
    session.add(work)
    session.flush()
    one = [
        block("Chapter One", "heading"),
        block("Words of a sage.", "epigraph"),
        block("An Old Book", "epigraph"),
        block("“Come in,” she said."),
        block("He came in."),
        block("", "section_break"),
        block("Night fell."),
        block("Roses are red\nViolets are blue", "verse"),
        block("Sugar is sweet", "verse"),
    ]
    two = [block("Chapter Two", "heading"), block("The end.")]
    for index, blocks in enumerate((one, two), start=1):
        session.add(Chapter(work_id=work.id, index=index, content_hash=str(index), blocks=blocks))
    session.flush()
    session.refresh(work)
    build_script(session, work, PACK)
    for line in session.scalars(select(Line).where(Line.work_id == work.id)):
        line.speaker = "narrator"
    work.analysis = {"stage": "done"}
    session.commit()
    session.refresh(work)
    cast_work(session, work)
    return work


def words(text: str) -> int:
    return len(text.split())


def spoken(text: str) -> float:
    """A trimmed take's length: what the model said, and the margin kept at each end."""
    return words(text) / 10 + 2 * MARGIN


# ---- Pauses ----


def test_each_line_is_followed_by_the_pause_its_place_in_the_script_asks_for():
    with get_sessionmaker()() as session:
        work = make_work(session)
        parts = {p.key: p for p in parts_of(session, work)}
        assert list(parts) == ["front", "1", "2"]
        p = pauses()
        one = parts["1"]
        assert [
            (ln.text, gap) for ln, gap in zip(one.lines, pauses_after(one, p), strict=True)
        ] == [
            ("Chapter One", p["after_title"]),
            ("Words of a sage.", p["new_paragraph"]),
            ("An Old Book", p["after_title"]),  # the epigraph's source line
            ("“Come in,”", p["between_lines"]),
            ("she said.", p["new_paragraph"]),
            ("He came in.", p["section_break"]),
            ("Night fell.", p["new_paragraph"]),
            ("Roses are red\nViolets are blue", p["verse_line_end"]),
            ("Sugar is sweet", 0.0),  # nothing after the chapter's last line
        ]
        # The Work title and author, then a long pause, before chapter one.
        front = parts["front"]
        assert [ln.passage for ln in front.lines] == ["work_title"]
        assert pauses_after(front, p) == [p["after_title"]]


def test_verse_is_voiced_with_the_pause_at_each_line_end(monkeypatch, tmp_path):
    settings = {**json.loads(voicing.PAUSES_FILE.read_text()), "verse_line_end": 0.6}
    (tmp_path / "pauses.json").write_text(json.dumps(settings))
    monkeypatch.setattr(voicing, "PAUSES_FILE", tmp_path / "pauses.json")
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        line = session.scalar(select(Line).where(Line.text.startswith("Roses")))
        # Two verse lines of three words, each with the model's silence, and 0.6 s between.
        each = LEAD + 0.3 + TAIL
        assert line.take["seconds"] == pytest.approx(2 * each + 0.6, abs=1e-3)


# ---- Assembling ----


def test_trimming_cuts_the_silence_at_both_ends_and_keeps_a_margin():
    audio = np.concatenate([np.zeros(4800), np.full(2400, 0.1), np.zeros(7200)])
    margin = int(MARGIN * RATE)
    assert trim(audio, RATE) == (4800 - margin, 4800 + 2400 + margin)
    assert trim(np.zeros(100), RATE) == (0, 1)  # silence all through keeps one sample


def test_a_chapter_is_its_trimmed_takes_and_pauses():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        parts = {p.key: p for p in parts_of(session, work)}
        assert assemble_part(session, work, parts["1"])

        p = pauses()
        expected = (
            sum(spoken(ln.text) for ln in parts["1"].lines)
            + 2 * p["after_title"]  # after the chapter title and the epigraph's source line
            + p["between_lines"]
            + 3 * p["new_paragraph"]
            + p["section_break"]
            + p["verse_line_end"]
            # inside the verse line: its two lines' silence and the pause between them
            + TAIL
            + LEAD
            + p["verse_line_end"]
        )
        path = audio_dir(work.id) / work.chapters[0].audio["file"]
        info = soundfile.info(path)
        assert info.format == "FLAC" and info.samplerate == RATE
        assert info.frames / RATE == pytest.approx(expected, abs=0.005)
        assert work.chapters[0].audio["seconds"] == pytest.approx(expected, abs=0.005)


def test_an_assembled_chapter_is_cached_until_a_pause_changes(monkeypatch, tmp_path):
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        two = next(p for p in parts_of(session, work) if p.key == "2")
        assert assemble_part(session, work, two)
        before = work.chapters[1].audio["seconds"]
        assert not assemble_part(session, work, two)

        settings = {**json.loads(voicing.PAUSES_FILE.read_text()), "after_title": 3.0}
        (tmp_path / "pauses.json").write_text(json.dumps(settings))
        monkeypatch.setattr(voicing, "PAUSES_FILE", tmp_path / "pauses.json")
        assert assemble_part(session, work, two)
        assert work.chapters[1].audio["seconds"] == pytest.approx(before + 1.5, abs=0.005)


def test_a_part_is_not_assembled_until_all_its_lines_are_voiced():
    with get_sessionmaker()() as session:
        work = make_work(session)
        one = next(p for p in parts_of(session, work) if p.key == "1")
        assert not assemble_part(session, work, one)
        assert work.chapters[0].audio is None


# ---- When ----


def test_a_chapter_is_assembled_as_soon_as_it_is_voiced(monkeypatch):
    with get_sessionmaker()() as session:
        work = make_work(session)
        queued: list[str] = []

        def part_voiced(part: str) -> None:
            queued.append(part)
            assembly.start_assembly(session, work, part)

        # Killed in chapter two: the front matter and chapter one are voiced and assembled.
        with pytest.raises(RuntimeError):
            voice_work(session, work, Model(fail_after=12), lambda **p: None, part_voiced)
        session.rollback()
        assert queued == ["front", "1"]
        session.expire_all()
        assert work.matter_audio["front"]["seconds"] > 0
        assert work.chapters[0].audio["seconds"] > 0
        assert work.chapters[1].audio is None
        assert work.state != WorkState.READY

        client = TestClient(create_app())
        detail = client.get(f"/api/works/{work.id}").json()
        assert [c["audio_seconds"] is not None for c in detail["chapters"]] == [True, False]
        assert detail["front_matter_audio_seconds"] > 0
        response = client.get(f"/api/works/{work.id}/audio/1")
        assert response.status_code == 200 and response.headers["content-type"] == "audio/flac"
        assert client.get(f"/api/works/{work.id}/audio/2").status_code == 404


def test_voicing_ends_with_the_work_ready_to_listen(monkeypatch):
    with get_sessionmaker()() as session:
        work = make_work(session)

        def child(job_id):
            voice_work(session, work, Model(), lambda **p: None)
            return 0

        monkeypatch.setattr(voicing, "run_child", child)
        enqueue(session, "voicing", work_id=work.id)
        session.expire_all()
        jobs = session.scalars(select(Job).order_by(Job.id)).all()
        assert [(j.kind, j.state) for j in jobs] == [
            ("voicing", JobState.DONE), ("assembly", JobState.DONE),
        ]  # fmt: skip
        assert jobs[1].progress["assembled"] == ["front", "1", "2"]
        assert session.get(Work, work.id).state == WorkState.READY

        # Assembling again finds nothing to do.
        client = TestClient(create_app())
        assert client.post(f"/api/works/{work.id}/assembly").status_code == 202
        last = session.scalars(select(Job).order_by(Job.id.desc())).first()
        session.refresh(last)
        assert last.kind == "assembly" and last.progress["assembled"] == []


def test_a_new_analysis_discards_the_assembled_audio():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        for part in parts_of(session, work):
            assemble_part(session, work, part)
        assembly.discard(session, work)
        session.commit()
        assert not audio_dir(work.id).exists()
        assert work.matter_audio == {} and all(c.audio is None for c in work.chapters)
