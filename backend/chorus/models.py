import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

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
    # Set once Works exist (ticket 05); a job without a Work is a system job.
    work_id: Mapped[int | None] = mapped_column(index=True)
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
