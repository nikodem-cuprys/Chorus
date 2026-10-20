import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from chorus import analysis
from chorus.analysis import (
    CAST_SYSTEM,
    CastList,
    Chunk,
    analyse,
    is_name,
    make_chunks,
    merge,
    narrating_character,
)
from chorus.analysis_model import Completion
from chorus.app import create_app
from chorus.db import get_sessionmaker
from chorus.importing import Block, Span
from chorus.jobs import _registry, enqueue
from chorus.languages import get_packs
from chorus.models import Chapter, Character, Job, JobState, Line, Work, WorkState
from chorus.voices import sync_built_in_voices


def para(text: str, **kw) -> dict:
    return Block("paragraph", [Span(text)], **kw).to_dict()


def line(text: str, paragraph: int, kind: str = "narration", chapter_id: int | None = 1) -> Line:
    return Line(
        text=text,
        paragraph=paragraph,
        last_paragraph=paragraph,
        kind=kind,
        part="chapter" if chapter_id else "front",
        chapter_id=chapter_id,
        voiced=True,
    )


# ---- The Character list ----


@pytest.mark.parametrize(
    "alias, ok",
    [
        ("Lizzy", True),
        ("Miss Bennet", True),
        ("Sir Lewis de Bourgh", True),
        ("Lady Catherine herself", False),  # a lower-case word that is no particle
        ("Jane could not have been wearied", False),  # copied text, more than four words
        ("she", False),
        ("Jane, Lizzy", False),  # a list
        ("her sister", False),
    ],
)
def test_an_alias_must_be_a_name(alias, ok):
    assert is_name(alias) is ok


def test_aliases_are_refused_when_absent_from_the_chunk_or_someone_elses():
    cast = CastList([])
    elizabeth = cast.add("Elizabeth", "female", "young adult")
    jane = cast.add("Jane", "female", "young adult")
    text = "“Lizzy,” said Jane. Miss Bennet smiled."
    assert cast.add_alias(elizabeth, "Lizzy", text)
    assert not cast.add_alias(elizabeth, "Eliza", text)  # not in the chunk
    assert not cast.add_alias(elizabeth, "Jane", text)  # another Character's name
    assert cast.add_alias(jane, "Miss Bennet", text)
    assert not cast.add_alias(elizabeth, "miss bennet", text)
    assert elizabeth.aliases == ["Lizzy"] and elizabeth.age == "young_adult"


def test_names_are_compared_without_their_article():
    cast = CastList([], get_packs()["en"].names)
    hatter = cast.add("the Hatter", "male", "adult")
    merge(
        cast,
        {
            "new_characters": [{"name": "Hatter", "gender": "male", "age": "adult", "aliases": []}],
            "new_aliases": [{"name": "The Hatter", "aliases": ["Mad Hatter"]}],
        },
        "“No room!” said the Hatter. The Mad Hatter frowned.",
    )
    assert cast.characters == [hatter] and hatter.aliases == ["Mad Hatter"]


def test_a_relisted_character_is_merged_and_fills_in_what_was_unknown():
    cast = CastList([])
    bennet = cast.add("Mr. Bennet")
    text = "“My dear Mr. Bennet,” said his lady. Mr. Bennet replied."
    added = merge(
        cast,
        {
            "new_characters": [
                {"name": "Mrs. Bennet", "gender": "female", "age": "adult", "aliases": []},
                {"name": "mr. bennet", "gender": "male", "age": "adult", "aliases": ["he"]},
            ],
            "new_aliases": [{"name": "Nobody", "aliases": ["Bennet"]}],
        },
        text,
    )
    assert [c.name for c in added] == ["Mrs. Bennet"]
    assert [c.name for c in cast.characters] == ["Mr. Bennet", "Mrs. Bennet"]
    assert (bennet.gender, bennet.age, bennet.aliases) == ("male", "adult", [])


def test_a_chapter_takes_the_majority_narration_answer():
    cast = CastList([])
    watson = cast.add("Watson", "male", "adult")
    cast.add_alias(watson, "Dr. Watson", "Dr. Watson")
    first = [
        {"person": "first", "character": "Dr. Watson"},
        {"person": "first", "character": "Watson"},
        {"person": "third", "character": ""},
    ]
    assert narrating_character(cast, first) is watson
    third = [
        {"person": "third", "character": ""},
        {"person": "third", "character": ""},
        {"person": "first", "character": "Holmes"},
    ]
    assert narrating_character(cast, third) is None


def test_a_tie_goes_to_first_person_and_i_names_nobody():
    cast = CastList([])
    answers = [
        {"person": "third", "character": ""},
        {"person": "first", "character": "I"},
        {"person": "first", "character": "Jane"},
        {"person": "first", "character": "I"},
        {"person": "third", "character": ""},
        {"person": "third", "character": ""},
    ]
    jane = narrating_character(cast, answers)
    assert jane is not None and jane.name == "Jane"
    assert narrating_character(CastList([]), answers[1:2] + answers[4:5]) is None  # only "I"


def test_a_narrating_character_missing_from_the_list_is_added_with_their_traits():
    cast = CastList([])
    answers = [
        {"person": "first", "character": "Jane", "gender": "female", "age": "child"},
        {"person": "first", "character": "Jane", "gender": "unknown", "age": "unknown"},
    ]
    jane = narrating_character(cast, answers)
    assert jane is not None and jane.name == "Jane" and cast.characters == [jane]
    assert (jane.gender, jane.age) == ("female", "child")


# ---- Chunks ----


def test_chunks_are_whole_paragraphs_never_across_a_chapter():
    words = " ".join(["word"] * 400)
    lines = [
        line(words, 0),
        line("“Hi,”", 1, "quote"),
        line(words, 1),
        line(words, 2),  # would pass 900 words: starts a new chunk
        line("Not voiced.", 3),
        line("Next chapter.", 0, chapter_id=2),
    ]
    lines[4].voiced = False
    title = line("A Story, by Somebody", None, chapter_id=None)
    title.passage = "work_title"  # the Narrator's, and no chunk of its own
    lines.insert(0, title)
    chunks = make_chunks(lines)
    assert [[ln.text[:5] for ln in c.lines] for c in chunks] == [
        ["word ", "“Hi,”", "word "],
        ["word "],
        ["Next "],
    ]
    assert [c.part for c in chunks] == ["1", "1", "2"]


def test_a_chunk_numbers_its_quotations_and_keeps_paragraphs():
    text, quotes = Chunk(
        "1", [line("“Hi,”", 0, "quote"), line("she said.", 0), line("He nodded.", 1)]
    ).render()
    assert text == "[1] “Hi,” she said.\n\nHe nodded."
    assert list(quotes) == [1]


# ---- The stage, with a stand-in for the model ----


class Model:
    """Answers the Character pass from `cast` (per chunk, in order) and attribution from the
    quotations' text."""

    def __init__(self, cast: list[dict], speakers: dict[str, dict], fail_after: int | None = None):
        self.cast = list(cast)
        self.speakers = speakers
        self.fail_after = fail_after
        self.calls: list[str] = []

    def complete(self, system: str, user: str, schema: dict, max_tokens: int) -> Completion:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise RuntimeError("the worker was killed")
        if system == CAST_SYSTEM:
            self.calls.append("cast")
            return Completion(self.cast.pop(0))
        self.calls.append("attribution")
        names = schema["properties"]["lines"]["items"]["properties"]["speaker"]["enum"]
        assert names[-2:] == ["Narrator", "Unknown"]
        out = []
        for number, quote in re.findall(r"\[(\d+)\] (“[^”]*”)", user.split("TEXT TO LABEL:")[1]):
            answer = self.speakers.get(quote)
            if answer:
                out.append({"id": int(number), **answer})
        return Completion({"lines": out})


def make_work(session, chapters: list[list[dict]]) -> Work:
    sync_built_in_voices(session, get_packs())  # what the app does at startup
    work = Work(title="Tales", source_kind="txt", source_name="t.txt", state=WorkState.IMPORTED)
    session.add(work)
    session.flush()
    for index, blocks in enumerate(chapters, start=1):
        session.add(Chapter(work_id=work.id, index=index, content_hash="x", blocks=blocks))
    session.commit()
    session.refresh(work)
    return work


CHAPTER_ONE = [
    para("“Have you heard?” asked Mrs. Bennet. Mr. Morris had let Netherfield."),
    para("“I have not,” said Mr. Bennet. “I think,” he thought."),
    para("“Who?” said a voice. The word “Netherfield” was all she said."),
]
CHAPTER_TWO = [para("I was tired. “Good night,” I said to Holmes. “Night, Watson.”")]

CAST_ANSWERS = [
    {
        "narrator": {"person": "third", "character": ""},
        "new_characters": [
            {"name": "Mrs. Bennet", "gender": "female", "age": "adult", "aliases": []},
            {"name": "Mr. Bennet", "gender": "unknown", "age": "adult", "aliases": []},
            {"name": "Mr. Morris", "gender": "male", "age": "adult", "aliases": []},
        ],
        "new_aliases": [],
    },
    {
        "narrator": {"person": "first", "character": "Watson"},
        "new_characters": [
            {"name": "Holmes", "gender": "male", "age": "adult", "aliases": []},
        ],
        "new_aliases": [],
    },
]
SPEAKERS = {
    "“Have you heard?”": {
        "speaker": "Mrs. Bennet", "kind": "speech", "emotion": "excited", "intensity": "strong",
    },
    "“I have not,”": {
        "speaker": "Mr. Bennet", "kind": "speech", "emotion": "amused", "intensity": "normal",
    },
    "“I think,”": {
        "speaker": "Mr. Bennet", "kind": "thought", "emotion": "anxious", "intensity": "strong",
    },
    "“Netherfield”": {
        "speaker": "Narrator", "kind": "speech", "emotion": "neutral", "intensity": "normal",
    },
    "“Good night,”": {
        "speaker": "Watson", "kind": "speech", "emotion": "sad", "intensity": "normal",
    },
    "“Night, Watson.”": {
        "speaker": "Holmes", "kind": "speech", "emotion": "neutral", "intensity": "normal",
    },
}  # fmt: skip


def _labels(session, work: Work) -> dict[str, tuple]:
    names = {c.id: c.name for c in work.characters}
    lines = session.scalars(select(Line).where(Line.work_id == work.id).order_by(Line.position))
    return {
        ln.text: (ln.kind, ln.speaker, names.get(ln.character_id), ln.emotion, ln.intensity)
        for ln in lines
    }


def test_the_stage_lists_characters_and_labels_every_quoted_line():
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE, CHAPTER_TWO])
        model = Model(CAST_ANSWERS, SPEAKERS)
        reports: list[dict] = []
        analyse(session, work, model, lambda **p: reports.append(p))

        assert model.calls == ["cast", "cast", "attribution", "attribution"]
        labels = _labels(session, work)
        excited = ("speech", "character", "Mrs. Bennet", "excited", "strong")
        assert labels["“Have you heard?”"] == excited
        # Thoughts are never strong; the Narrator has no Emotion.
        assert labels["“I think,”"] == ("thought", "character", "Mr. Bennet", "anxious", "normal")
        assert labels["“Netherfield”"] == ("speech", "narrator", None, None, None)
        # A line the model left out is Unknown.
        assert labels["“Who?”"] == ("speech", "unknown", None, "neutral", "normal")
        assert labels["asked Mrs. Bennet. Mr. Morris had let Netherfield."][1] == "narrator"
        assert labels["Tales"][1] == "narrator"  # the Work title line, never in a chunk
        # In the first-person chapter, the narrator's own line has their name.
        assert labels["“Good night,”"][2] == "Watson"

        # Watson was added as chapter 2's Narrating Character; Mr. Morris never speaks.
        assert sorted(c.name for c in work.characters) == [
            "Holmes", "Mr. Bennet", "Mrs. Bennet", "Watson",
        ]  # fmt: skip
        bennet = next(c for c in work.characters if c.name == "Mr. Bennet")
        assert bennet.gender == "male"  # from his title; the model said "unknown"
        narrating = {c.index: c.narrating_character_id for c in work.chapters}
        watson = next(c for c in work.characters if c.name == "Watson")
        assert narrating == {1: None, 2: watson.id}
        assert work.analysis["stage"] == "done"
        assert reports[-1] == {"stage": "attribution", "done": 2, "total": 2, "percent": 100}


def test_a_stopped_analysis_continues_with_the_next_chunk():
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE, CHAPTER_TWO])
        killed = Model(CAST_ANSWERS, SPEAKERS, fail_after=3)
        with pytest.raises(RuntimeError):
            analyse(session, work, killed, lambda **p: None)
        session.rollback()
        assert work.analysis == {**work.analysis, "stage": "attribution", "done": 1}

        again = Model([], SPEAKERS)
        analyse(session, work, again, lambda **p: None)
        assert again.calls == ["attribution"]
        assert _labels(session, work)["“Night, Watson.”"][2] == "Holmes"
        assert _labels(session, work)["“Have you heard?”"][2] == "Mrs. Bennet"


def test_a_new_analysis_starts_over():
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE, CHAPTER_TWO])
        analyse(session, work, Model(CAST_ANSWERS, SPEAKERS), lambda **p: None)
        again = Model(CAST_ANSWERS, SPEAKERS)
        analyse(session, work, again, lambda **p: None)
        assert again.calls == ["cast", "cast", "attribution", "attribution"]
        assert len(work.characters) == 4


# ---- The job ----


def test_the_job_runs_the_stage_in_a_child_and_marks_the_work(monkeypatch):
    monkeypatch.setattr(analysis, "run_child", lambda job_id: 0)
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE])
        row = enqueue(session, "analysis", work_id=work.id)
        session.expire_all()
        assert session.get(Job, row.id).state == JobState.DONE
        assert session.get(Work, work.id).state == WorkState.ANALYSED


def test_a_failed_child_fails_the_job_and_the_work_with_its_reason(monkeypatch):
    def child(job_id: int) -> int:
        with get_sessionmaker()() as other:
            other.get(Job, job_id).error = {
                "key": "analysis.error.model", "params": {"detail": "out of memory"},
            }  # fmt: skip
            other.commit()
        return 1

    monkeypatch.setattr(analysis, "run_child", child)
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE])
        row = enqueue(session, "analysis", work_id=work.id)
        session.expire_all()
        failed = session.get(Job, row.id)
        assert failed.state == JobState.FAILED
        assert failed.error["params"] == {"detail": "out of memory"}
        assert session.get(Work, work.id).error == failed.error


def test_a_job_asked_for_before_the_last_analysis_finished_does_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(analysis, "run_child", lambda job_id: calls.append(job_id) or 0)
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE])
        stale = Job(work_id=work.id, kind="analysis", queue="gpu", state=JobState.RUNNING)
        session.add(stale)
        session.commit()
        enqueue(session, "analysis", work_id=work.id)
        work.analysis = {"stage": "done", "finished_at": "2999-01-01T00:00:00+00:00"}
        session.commit()
        # Celery hands the killed job out again after the newer one finished.
        _registry["analysis"][1].apply(args=[stale.id])
        assert len(calls) == 1


def test_a_stopped_analysis_can_be_started_again_but_not_queued_twice(monkeypatch):
    monkeypatch.setattr(analysis, "run_child", lambda job_id: 0)
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE])
        work.state = WorkState.ANALYSING  # its worker was killed
        session.add(Job(work_id=work.id, kind="analysis", queue="gpu", state=JobState.QUEUED))
        session.commit()
        work_id = work.id
    client = TestClient(create_app())
    assert client.post(f"/api/works/{work_id}/analysis").status_code == 409
    with get_sessionmaker()() as session:
        session.query(Job).update({"state": JobState.RUNNING})
        session.commit()
    assert client.post(f"/api/works/{work_id}/analysis").status_code == 202


def test_the_api_starts_an_analysis_and_lists_the_characters(monkeypatch):
    monkeypatch.setattr(analysis, "run_child", lambda job_id: 0)
    with get_sessionmaker()() as session:
        work = make_work(session, [CHAPTER_ONE])
        session.add(Character(work_id=work.id, name="Mrs. Bennet", gender="female", age="adult"))
        session.commit()
        work_id = work.id
    client = TestClient(create_app())
    assert client.post(f"/api/works/{work_id}/analysis").status_code == 202
    body = client.get(f"/api/works/{work_id}").json()
    assert body["state"] == "analysed"
    assert [(c["name"], c["lines"]) for c in body["characters"]] == [("Mrs. Bennet", 0)]
    assert client.post("/api/works/999/analysis").status_code == 404
