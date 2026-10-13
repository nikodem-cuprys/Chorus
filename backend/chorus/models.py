import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
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
    # Until analysis follows import by itself (ticket 11), a Work rests here.
    IMPORTED = "imported"
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

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="work",
        order_by="Chapter.index",
        cascade="all, delete-orphan",
        passive_deletes=True,
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

    work: Mapped[Work] = relationship(back_populates="chapters")
