"""Voices in the database. Built-in Voices are read-only: the Language packs are their source,
and `sync_built_in_voices` makes the table match the packs at every startup."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus.languages import LanguagePack
from chorus.models import Voice


def sync_built_in_voices(session: Session, packs: dict[str, LanguagePack]) -> None:
    """Adds and updates the packs' Voices and removes built-in Voices no pack has any more."""
    existing = {v.name: v for v in session.scalars(select(Voice).where(Voice.built_in))}
    for pack in packs.values():
        for voice in pack.voices:
            row = existing.pop(voice.id, None) or Voice(name=voice.id, built_in=True)
            row.language = pack.language
            row.gender = voice.gender
            row.age = voice.age
            row.accent = voice.accent
            row.timbre = list(voice.timbre)
            row.narrator_ok = voice.narrator_ok
            row.clips = {emotion: path.name for emotion, path in voice.clips.items()}
            row.credit = voice.credit
            session.add(row)
    for gone in existing.values():
        session.delete(gone)
    session.commit()


def to_dict(voice: Voice, packs: dict[str, LanguagePack]) -> dict:
    pack = packs.get(voice.language)
    default = voice.built_in and pack is not None and pack.default_narrator == voice.name
    return {
        **voice.to_dict(),
        "default_narrator": default,
        "clip_url": f"/api/voices/{voice.id}/clip",
    }


def clip_path(voice: Voice, packs: dict[str, LanguagePack], emotion: str = "neutral") -> Path:
    """The file of a built-in Voice's clip. (Cloned Voices, with clips on the data volume,
    arrive in milestone 6.)"""
    return packs[voice.language].voice(voice.name).clips[emotion]
