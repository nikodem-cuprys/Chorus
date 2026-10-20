import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chorus.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Queue(enum.StrEnum):
    GPU = "gpu"  # one slot: analysis and voicing, one model on the card at a time
    OTHER = "other"  # import, assembly, export, YouTube


class JobState(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"
    DONE = "done"


class Job(Base):
    __tablename__ = "job"

    id: Mapped[int] = mapped_column(primary_key=True)
    # A job without a Work is a system job.
    work_id: Mapped[int | None] = mapped_column(
        ForeignKey("work.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    queue: Mapped[Queue] = mapped_column(Enum(Queue, native_enum=False, length=10))
    state: Mapped[JobState] = mapped_column(
        Enum(JobState, native_enum=False, length=10), default=JobState.QUEUED
    )
    # Free-form progress for the interface: stage, done, total, percent, ...
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    # A message-catalogue key and its parameters, never display text.
    error: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "work_id": self.work_id,
            "kind": self.kind,
            "queue": self.queue.value,
            "state": self.state.value,
            "progress": self.progress or {},
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class Voice(Base):
    """A Voice a Speaker can be given. Built-in Voices are copies of their Language pack's
    `voices.json`, refreshed at every startup and never edited here (chorus.voices)."""

    __tablename__ = "voice"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The pack's id for a built-in Voice ("af_bella").
    name: Mapped[str] = mapped_column(String(60), unique=True)
    language: Mapped[str] = mapped_column(String(10), index=True)
    gender: Mapped[str] = mapped_column(String(10))  # female, male, neutral
    age: Mapped[str] = mapped_column(String(12))  # child, young_adult, adult, elderly
    accent: Mapped[str] = mapped_column(String(40))
    # Timbre words from the fixed list, as ids; the interface translates them.
    timbre: Mapped[list] = mapped_column(JSON)
    narrator_ok: Mapped[bool] = mapped_column(Boolean)
    built_in: Mapped[bool] = mapped_column(Boolean)
    # Emotion -> clip file name, in the pack's voices folder for a built-in Voice.
    clips: Mapped[dict] = mapped_column(JSON)
    # Where a built-in Voice comes from, for the credits; not translated.
    credit: Mapped[str | None] = mapped_column(String(200))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "gender": self.gender,
            "age": self.age,
            "accent": self.accent,
            "timbre": self.timbre,
            "narrator_ok": self.narrator_ok,
            "built_in": self.built_in,
            "credit": self.credit,
        }


class WorkState(enum.StrEnum):
    IMPORTING = "importing"
    # Imported, with its analysis queued.
    IMPORTED = "imported"
    ANALYSING = "analysing"
    # Analysed and cast, with voicing queued.
    ANALYSED = "analysed"
    VOICING = "voicing"
    # Until chapter assembly follows voicing (ticket 14), a Work rests here.
    VOICED = "voiced"
    FAILED = "failed"


class Work(Base):
    """A Source after import (docs/spec/05-data-model.md). Blocks are stored as JSON, as the
    importers produce them (chorus.importing)."""

    __tablename__ = "work"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    authors: Mapped[list] = mapped_column(JSON, default=list)
    # Base language code; where it came from: "metadata", "detector" or "user".
    language: Mapped[str | None] = mapped_column(String(10))
    language_source: Mapped[str | None] = mapped_column(String(10))
    source_kind: Mapped[str] = mapped_column(String(20))
    source_name: Mapped[str] = mapped_column(String(500))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    # Files on the data volume, relative to the Work's folder there.
    source_file: Mapped[str | None] = mapped_column(String(200))
    cover_file: Mapped[str | None] = mapped_column(String(200))
    is_ao3: Mapped[bool] = mapped_column(Boolean, default=False)
    # summary, tags, series, series_index, rating, warnings, publisher, published
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    # Message-catalogue keys with parameters.
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    front_matter: Mapped[list] = mapped_column(JSON, default=list)
    back_matter: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[WorkState] = mapped_column(
        Enum(WorkState, native_enum=False, length=20), default=WorkState.IMPORTING
    )
    error: Mapped[dict | None] = mapped_column(JSON)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Where the analysis is, saved with every finished chunk so it continues where it stopped
    # (chorus.analysis): stage, chunks done, each chunk's narration answer, the front and back
    # matter's Narrating Characters. None before the first analysis.
    analysis: Mapped[dict | None] = mapped_column(JSON)
    # The Narrator's Voice: the pack's default Narrator until the user swaps it (chorus.casting).
    narrator_voice_id: Mapped[int | None] = mapped_column(
        ForeignKey("voice.id", ondelete="SET NULL")
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="work",
        order_by="Chapter.index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    characters: Mapped[list["Character"]] = relationship(
        order_by="Character.id", cascade="all, delete-orphan", passive_deletes=True
    )


class Chapter(Base):
    __tablename__ = "chapter"
    __table_args__ = (UniqueConstraint("work_id", "index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("work.id", ondelete="CASCADE"), index=True)
    index: Mapped[int]
    title: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    notes_before: Mapped[list] = mapped_column(JSON, default=list)
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    notes_after: Mapped[list] = mapped_column(JSON, default=list)
    # The Character telling a first-person chapter; None for a chapter told in the third person.
    narrating_character_id: Mapped[int | None] = mapped_column(
        ForeignKey("character.id", ondelete="SET NULL")
    )

    work: Mapped[Work] = relationship(back_populates="chapters")


class Character(Base):
    """A person on a Work's Character list, found by analysis (chorus.analysis)."""

    __tablename__ = "character"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("work.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    # The other names and titles the text uses for this person.
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    gender: Mapped[str] = mapped_column(String(10))  # female, male, unknown
    age: Mapped[str] = mapped_column(String(12))  # child, young_adult, adult, elderly, unknown
    voice_id: Mapped[int | None] = mapped_column(ForeignKey("voice.id", ondelete="SET NULL"))
    # Whether the Voice was auto-cast (chorus.casting) rather than chosen by the user.
    voice_auto: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            "gender": self.gender,
            "age": self.age,
            "voice_id": self.voice_id,
            "voice_auto": self.voice_auto,
        }


class Line(Base):
    """One line of the Script (docs/spec/05-data-model.md, chorus.script). The Script is the
    Work's lines in `position` order: the front matter's, each chapter's, the back matter's."""

    __tablename__ = "line"
    __table_args__ = (UniqueConstraint("work_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("work.id", ondelete="CASCADE"), index=True)
    # None for a line of the front or back matter.
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapter.id", ondelete="CASCADE"), index=True
    )
    part: Mapped[str] = mapped_column(String(10))  # front, chapter, back
    position: Mapped[int]
    # The blocks the line comes from, as indexes into its part's blocks (for a chapter: notes
    # before, blocks, notes after, counted as one list). A quotation that runs on over several
    # paragraphs ends in a later one. None for a line Chorus made, such as the Work title.
    paragraph: Mapped[int | None]
    last_paragraph: Mapped[int | None]
    # The text with its marks, as spans; paragraphs inside one line are joined with "\n".
    spans: Mapped[list] = mapped_column(JSON)
    text: Mapped[str] = mapped_column(Text)
    # narration or quote; analysis makes a quote speech, thought or written.
    kind: Mapped[str] = mapped_column(String(12))
    # The kind of passage: chorus.script.PASSAGES.
    passage: Mapped[str] = mapped_column(String(16))
    voiced: Mapped[bool] = mapped_column(Boolean)
    # From analysis, for voiced lines: narrator, character (with `character_id`) or unknown.
    speaker: Mapped[str | None] = mapped_column(String(10))
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("character.id", ondelete="SET NULL"), index=True
    )
    # One of the nine Emotions and normal or strong; None for the Narrator.
    emotion: Mapped[str | None] = mapped_column(String(12))
    intensity: Mapped[str | None] = mapped_column(String(8))
    # Given when the line is first voiced and kept, so voicing it again gives the same take.
    seed: Mapped[int | None]
    # The current take (chorus.voicing): its file on the data volume, and the Voice, Emotion,
    # intensity, text and seed it was made with.
    take: Mapped[dict | None] = mapped_column(JSON)

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "paragraph": self.paragraph,
            "last_paragraph": self.last_paragraph,
            "spans": self.spans,
            "kind": self.kind,
            "passage": self.passage,
            "voiced": self.voiced,
            "speaker": self.speaker,
            "character_id": self.character_id,
            "emotion": self.emotion,
            "intensity": self.intensity,
            "seed": self.seed,
            "audio_seconds": (self.take or {}).get("seconds"),
        }
