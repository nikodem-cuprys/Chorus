import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chorus import languages
from chorus.app import create_app
from chorus.db import get_sessionmaker
from chorus.languages import (
    EMOTIONS,
    INTENSITIES,
    REQUIRED_PARTS,
    PackError,
    get_pack,
    load_packs,
)
from chorus.models import Voice
from chorus.voices import sync_built_in_voices

PASSAGES = Path(__file__).resolve().parents[2] / ".scratch" / "chorus" / "samples" / "passages"

ENGLISH_VOICES = {
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_kore", "bf_emma",
    "am_eric", "am_fenrir", "am_michael", "bm_daniel", "bm_fable", "bm_lewis",
}  # fmt: skip


@pytest.fixture
def broken_pack(tmp_path, monkeypatch):
    """A copy of the English pack to break, used as the only pack."""
    folder = tmp_path / "en"
    shutil.copytree(languages.PACKS_DIR / "en", folder)
    monkeypatch.setattr(languages, "PACKS_DIR", tmp_path)
    languages.get_packs.cache_clear()
    yield folder
    languages.get_packs.cache_clear()


def _edit_pack_json(folder: Path, change) -> None:
    path = folder / "pack.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---- The English pack ----


def test_the_english_pack_is_complete():
    pack = get_pack("en")
    assert ("“", "”") in pack.quotation.pairs
    assert pack.quotation.dash_starts_dialogue is False
    assert {"Mr.", "Mrs.", "Dr.", "St."} <= pack.sentences.abbreviations
    assert pack.voice_model.id == "chatterbox-500m"
    assert set(pack.voice_model.emotions) == set(EMOTIONS)
    assert all(set(by) == set(INTENSITIES) for by in pack.voice_model.emotions.values())
    assert pack.voice_model.emotions["angry"]["strong"].exaggeration == 0.9
    assert pack.voice_model.emotions["sad"]["strong"].cfg_weight == 0.2
    assert {v.id for v in pack.voices} == ENGLISH_VOICES
    assert pack.default_narrator == "af_bella"
    assert pack.voice("af_bella").narrator_ok
    # The optional parts M1 and M3 use; the dictionary (M4) and export lines (M8) come later.
    assert pack.chapter_headings is not None
    assert "said" in pack.speech_verbs


def test_every_voice_clip_exists():
    for voice in get_pack("en").voices:
        clip = voice.clips["neutral"]
        assert clip.is_file(), clip
        assert clip.read_bytes()[:4] == b"RIFF"


@pytest.mark.parametrize(
    "heading",
    ["Chapter 12", "CHAPTER XII", "Part One", "12", "XII.", "Chapter Twenty-One",
     "Chapter 3. The Ball", "CHAPTER I: In Which", "Prologue"],
)  # fmt: skip
def test_chapter_headings(heading):
    assert get_pack("en").chapter_headings.is_heading(heading)


@pytest.mark.parametrize(
    "line",
    ["Mr. Bennet replied that he had not.", "Chapter of accidents", "Part of it", "1984 was"],
)
def test_lines_that_are_not_chapter_headings(line):
    assert not get_pack("en").chapter_headings.is_heading(line)


# ---- A broken pack stops Chorus ----


@pytest.mark.parametrize("part", REQUIRED_PARTS)
def test_a_missing_required_part_is_named(broken_pack, part):
    _edit_pack_json(broken_pack, lambda data: data.pop(part))
    with pytest.raises(PackError, match=f"'{part}' is missing"):
        load_packs()


def test_a_missing_optional_part_is_fine(broken_pack):
    _edit_pack_json(broken_pack, lambda data: data.pop("chapter_headings"))
    assert load_packs()["en"].chapter_headings is None


def test_a_missing_clip_is_named(broken_pack):
    (broken_pack / "voices" / "bm_lewis.wav").unlink()
    with pytest.raises(PackError, match="bm_lewis.wav is missing"):
        load_packs()


def test_a_missing_emotion_is_named(broken_pack):
    path = broken_pack / "emotions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["emotions"]["afraid"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PackError, match="'afraid' has no settings"):
        load_packs()


def test_startup_fails_on_a_broken_pack(broken_pack):
    _edit_pack_json(broken_pack, lambda data: data.pop("sentences"))
    with pytest.raises(PackError, match="'sentences' is missing"):
        with TestClient(create_app()):
            pass


# ---- Built-in Voices in the database ----


def test_startup_lists_the_built_in_voices():
    with TestClient(create_app()) as client:
        listed = client.get("/api/voices").json()
        assert {v["name"] for v in listed} == ENGLISH_VOICES
        fenrir = next(v for v in listed if v["name"] == "am_fenrir")
        assert fenrir | {"id": None, "clip_url": None} == {
            "id": None,
            "name": "am_fenrir",
            "language": "en",
            "gender": "male",
            "age": "young_adult",
            "accent": "american",
            "timbre": ["high"],
            "narrator_ok": True,
            "built_in": True,
            "default_narrator": False,
            "credit": "Kokoro-82M voice am_fenrir (Apache-2.0)",
            "clip_url": None,
        }
        assert [v["name"] for v in listed if v["default_narrator"]] == ["af_bella"]

        clip = client.get(fenrir["clip_url"])
        assert clip.headers["content-type"] == "audio/wav"
        assert clip.content[:4] == b"RIFF"


def test_the_sync_follows_the_pack():
    packs = load_packs()
    with get_sessionmaker()() as session:
        session.add(
            Voice(name="gone", language="en", gender="male", age="adult", accent="british",
                  timbre=["low"], narrator_ok=False, built_in=True, clips={}, credit=None)
        )  # fmt: skip
        session.commit()
        sync_built_in_voices(session, packs)
        sync_built_in_voices(session, packs)
        names = [v.name for v in session.query(Voice)]
    assert sorted(names) == sorted(ENGLISH_VOICES)


# ---- Sentences ----


def test_mr_bennet_stays_whole():
    split = get_pack("en").split_sentences
    assert split("Mr. Bennet replied that he had not.") == ["Mr. Bennet replied that he had not."]
    assert split("“My dear Mr. Bennet,” said his lady. “Have you heard?”") == [
        "“My dear Mr. Bennet,” said his lady.",
        "“Have you heard?”",
    ]


@pytest.mark.parametrize(
    ("text", "sentences"),
    [
        (
            "“But it is,” returned she; “for Mrs. Long has just been here, and she told me all "
            "about it.”",
            None,
        ),
        (
            "“How so? how can it affect them?”",
            None,
        ),
        (
            "To Sherlock Holmes she is always _the_ woman. I have seldom heard him mention her "
            "under any other name. In his eyes she eclipses and predominates the whole of her sex.",
            [
                "To Sherlock Holmes she is always _the_ woman.",
                "I have seldom heard him mention her under any other name.",
                "In his eyes she eclipses and predominates the whole of her sex.",
            ],
        ),
        (
            "He went out of the garret in which he lodged in S. Place and walked slowly.",
            None,
        ),
        (
            "“Oh! Mr. Bennet, you are wanted immediately; we are all in an uproar.”",
            ["“Oh!", "Mr. Bennet, you are wanted immediately; we are all in an uproar.”"],
        ),
        (
            "(Mrs. Reed, when there was no company, dined early.) Then it rained.",
            ["(Mrs. Reed, when there was no company, dined early.)", "Then it rained."],
        ),
    ],
)
def test_sentence_ends(text, sentences):
    assert get_pack("en").split_sentences(text) == (sentences or [text])


def _paragraphs(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [p for p in re.split(r"\n\s*\n", text) if p.strip() and not p.lstrip().startswith("#")]


@pytest.mark.parametrize("path", sorted(PASSAGES.glob("*.txt")), ids=lambda p: p.stem)
def test_the_sample_passages_split_at_their_sentence_ends(path):
    pack = get_pack("en")
    abbreviation = re.compile(
        "(?:^|[\\s“(])(?:" + "|".join(map(re.escape, pack.sentences.abbreviations)) + ")$"
    )
    total = 0
    for paragraph in _paragraphs(path):
        sentences = pack.split_sentences(paragraph)
        total += len(sentences)
        assert " ".join(sentences) == " ".join(paragraph.split())
        for sentence in sentences[:-1]:
            assert re.search(r"[.!?…][”\"’)\]]*$", sentence), sentence
            assert not abbreviation.search(sentence), sentence
            assert not re.search(r"(?:^|\s)[A-Z]\.$", sentence), sentence
        for later in sentences[1:]:
            assert not later[:1].islower(), later
    assert total > len(_paragraphs(path))
