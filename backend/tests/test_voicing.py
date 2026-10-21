import numpy as np
import pytest
import soundfile
from sqlalchemy import select

from chorus import voicing
from chorus.casting import cast_work
from chorus.config import get_settings
from chorus.db import get_sessionmaker
from chorus.importing import Block, Span
from chorus.jobs import enqueue
from chorus.languages import get_packs
from chorus.models import Chapter, Character, Job, JobState, Line, Voice, Work, WorkState
from chorus.script import build_script
from chorus.voice_model import Speech
from chorus.voices import sync_built_in_voices
from chorus.voicing import lines_dir, plan_line, voice_work

PACK = get_packs()["en"]
RATE = 24_000


class Model:
    """Speaks a tenth of a second per word, with samples that depend only on text and seed."""

    sample_rate = RATE

    def __init__(self, fail_after: int | None = None):
        self.batches: list[list[Speech]] = []
        self.fail_after = fail_after
        self.spoken = 0

    def speak(self, batch, step=None):
        # T3 over the whole batch, then S3Gen piece by piece, as Chatterbox.speak.
        for index in range(len(batch)):
            if step:
                step("t3", index)
        yield from self._s3gen(batch, step)

    def _s3gen(self, batch, step):
        self.batches.append(batch)
        for index, speech in enumerate(batch):
            if step:
                step("s3gen", index)
            if self.fail_after is not None and self.spoken >= self.fail_after:
                raise RuntimeError("the worker was killed")
            self.spoken += 1
            rng = np.random.default_rng([speech.seed, len(speech.text)])
            yield speech, rng.uniform(-0.5, 0.5, RATE * len(speech.text.split()) // 10)


def para(text: str, type: str = "paragraph") -> dict:
    return Block(type, [Span(text)]).to_dict()


def make_work(session) -> Work:
    """Two chapters: the first in the third person, the second told by Watson."""
    sync_built_in_voices(session, get_packs())
    work = Work(title="", source_kind="txt", source_name="t", state=WorkState.ANALYSED)
    session.add(work)
    session.flush()
    one = [
        para("“Have you heard? Netherfield is let at last!” cried Mrs. Bennet. He had not."),
        para("Dear Sir, I write in haste.", type="letter"),
        para("* * *"),
    ]
    two = [para("I sat down. “Holmes, I think,” I thought aloud.")]
    for index, blocks in enumerate((one, two), start=1):
        session.add(Chapter(work_id=work.id, index=index, content_hash=str(index), blocks=blocks))
    session.flush()
    session.refresh(work)
    build_script(session, work, PACK)
    bennet = Character(work_id=work.id, name="Mrs. Bennet", gender="female", age="adult")
    watson = Character(work_id=work.id, name="Watson", gender="male", age="adult")
    session.add_all([bennet, watson])
    session.flush()
    work.chapters[1].narrating_character_id = watson.id
    for line in session.scalars(select(Line).where(Line.work_id == work.id)):
        line.speaker = "narrator"
        if line.text.startswith("“Have"):
            line.kind, line.speaker, line.character_id = "speech", "character", bennet.id
            line.emotion, line.intensity = "excited", "strong"
        elif line.text.startswith("“Holmes"):
            line.kind, line.speaker, line.character_id = "thought", "character", watson.id
            line.emotion, line.intensity = "anxious", "strong"
    work.analysis = {"stage": "done"}
    session.commit()
    session.refresh(work)
    cast_work(session, work)
    return work


def lines_of(session, work) -> dict[str, Line]:
    return {ln.text: ln for ln in session.scalars(select(Line).where(Line.work_id == work.id))}


def voice_names(session) -> dict[int, str]:
    return {v.id: v.name for v in session.scalars(select(Voice))}


# ---- What each line is voiced with ----


def test_each_line_gets_its_voice_and_settings():
    with get_sessionmaker()() as session:
        work = make_work(session)
        lines = lines_of(session, work)
        characters = {c.id: c for c in work.characters}
        chapters = {c.id: c for c in work.chapters}
        names = voice_names(session)

        def plan(text):
            line = lines[text]
            return plan_line(line, work, chapters.get(line.chapter_id), characters, PACK)

        bennet = next(c for c in work.characters if c.name == "Mrs. Bennet")
        watson = next(c for c in work.characters if c.name == "Watson")
        excited = plan("“Have you heard? Netherfield is let at last!”")
        assert (excited.voice_id, excited.emotion, excited.intensity) == (
            bennet.voice_id, "excited", "strong",
        )  # fmt: skip
        assert (excited.exaggeration, excited.cfg_weight) == (0.9, 0.35)
        # The Narrator is always neutral, in the Narrator's Voice in a third-person chapter.
        narration = plan("cried Mrs. Bennet. He had not.")
        assert names[narration.voice_id] == "af_bella"
        assert (narration.emotion, narration.exaggeration, narration.cfg_weight) == (
            "neutral", 0.5, 0.5,
        )  # fmt: skip
        assert plan("Dear Sir, I write in haste.").emotion == "neutral"  # letters
        # In Watson's chapter his narration is read in his Voice; thoughts are never strong.
        assert plan("I sat down.").voice_id == watson.voice_id
        thought = plan("“Holmes, I think,”")
        assert (thought.emotion, thought.intensity) == ("anxious", "normal")


# ---- The stage ----


def test_every_voiced_line_gets_a_flac_file_chapter_by_chapter():
    with get_sessionmaker()() as session:
        work = make_work(session)
        model = Model()
        reports: list[dict] = []
        voiced = voice_work(session, work, model, lambda **p: reports.append(p))

        lines = lines_of(session, work)
        assert voiced == len(lines) == 7
        # Two chapters, two batches; the silent line needs no model.
        assert len(model.batches) == 2
        assert [s.text for s in model.batches[1]] == [
            "I sat down.",
            "“Holmes, I think,”",
            "I thought aloud.",
        ]
        for line in lines.values():
            path = lines_dir(work.id) / line.take["file"]
            audio, rate = soundfile.read(path)
            assert rate == RATE and soundfile.info(path).format == "FLAC"
            assert line.take["seed"] == line.seed is not None
            assert line.take["seconds"] == pytest.approx(len(audio) / RATE, abs=1e-3)
        assert lines["* * *"].take["seconds"] == 0.25
        assert reports[-1]["done"] == reports[-1]["total"] == 7


def test_a_long_line_is_its_sentences_joined_with_the_pause():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        line = lines_of(session, work)["“Have you heard? Netherfield is let at last!”"]
        # Two sentences: 3 and 5 words, a tenth of a second each, and 0.3 s between them.
        assert line.take["seconds"] == pytest.approx(0.3 + 0.3 + 0.5, abs=1e-3)


def test_voicing_a_line_again_with_its_seed_gives_the_same_take():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        line = lines_of(session, work)["“Holmes, I think,”"]
        path = lines_dir(work.id) / line.take["file"]
        first, seed = path.read_bytes(), line.seed

        line.take = None
        session.commit()
        model = Model()
        assert voice_work(session, work, model, lambda **p: None) == 1
        assert line.seed == seed and path.read_bytes() == first


def test_a_stopped_voicing_voices_only_the_missing_lines():
    with get_sessionmaker()() as session:
        work = make_work(session)
        with pytest.raises(RuntimeError):
            voice_work(session, work, Model(fail_after=4), lambda **p: None)
        session.rollback()
        done = {t for t, ln in lines_of(session, work).items() if ln.take}
        # Killed after four sentences: the speech (two) and the narration (two) are saved, and
        # the silent line, which needs no model; the letter was next.
        assert done == {
            "“Have you heard? Netherfield is let at last!”",
            "cried Mrs. Bennet. He had not.",
            "* * *",
        }
        again = Model()
        assert voice_work(session, work, again, lambda **p: None) == 4
        assert [s.text for s in again.batches[0]] == ["Dear Sir, I write in haste."]


def test_a_line_whose_values_changed_is_voiced_again():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        line = lines_of(session, work)["“Have you heard? Netherfield is let at last!”"]
        line.emotion = "angry"
        session.commit()
        model = Model()
        assert voice_work(session, work, model, lambda **p: None) == 1
        assert line.take["emotion"] == "angry"


def test_a_new_analysis_discards_the_line_audio():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        assert any(lines_dir(work.id).iterdir())
        voicing.discard_audio(work.id)
        assert not lines_dir(work.id).exists()


# ---- The job ----


def test_the_job_runs_in_a_child_and_marks_the_work_voiced(monkeypatch):
    monkeypatch.setattr(voicing, "run_child", lambda job_id: 0)
    with get_sessionmaker()() as session:
        work = make_work(session)
        row = enqueue(session, "voicing", work_id=work.id)
        session.expire_all()
        assert session.get(Job, row.id).state == JobState.DONE
        assert session.get(Work, work.id).state == WorkState.VOICED


def test_analysis_queues_voicing_and_voicing_queues_assembly(monkeypatch):
    from chorus import analysis

    monkeypatch.setattr(analysis, "run_child", lambda job_id: 0)
    monkeypatch.setattr(voicing, "run_child", lambda job_id: 0)
    monkeypatch.setattr(get_settings(), "voice_after_analysis", True)
    with get_sessionmaker()() as session:
        work = make_work(session)
        enqueue(session, "analysis", work_id=work.id)
        kinds = [j.kind for j in session.scalars(select(Job).order_by(Job.id))]
        assert kinds == ["analysis", "voicing", "assembly"]
        session.expire_all()
        assert session.get(Work, work.id).state == WorkState.VOICED
