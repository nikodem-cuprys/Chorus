"""Background jobs: Celery on Redis, with a one-slot GPU queue and a queue for everything else.

A job is a row in the `job` table plus a Celery task that carries the row's id. Tasks report
progress through `JobContext.report`, which saves it and publishes it for the browser.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from celery import Celery, Task
from sqlalchemy.orm import Session

from chorus import events
from chorus.config import get_settings
from chorus.db import get_sessionmaker
from chorus.models import Job, JobState, Queue

celery_app = Celery("chorus", broker=get_settings().redis_url)
celery_app.conf.update(
    task_default_queue=Queue.OTHER.value,
    # A worker takes one task at a time and acknowledges it only when done, so a task
    # interrupted by a crash goes back on the queue instead of being lost.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# How many tasks each queue runs at once. The GPU queue must stay at 1: only one model
# fits on the card at a time.
CONCURRENCY = {Queue.GPU: 1, Queue.OTHER: 4}


def _now() -> datetime:
    return datetime.now(UTC)


class JobContext:
    """What a running task uses to talk about its job."""

    def __init__(self, session: Session, job: Job):
        self.session = session
        self.job = job

    def report(self, **progress: Any) -> None:
        self.job.progress = {**(self.job.progress or {}), **progress}
        self._save()

    def _set_state(self, state: JobState, **fields: Any) -> None:
        self.job.state = state
        for name, value in fields.items():
            setattr(self.job, name, value)
        self._save()

    def _save(self) -> None:
        self.session.commit()
        events.publish("job", self.job.to_dict())


class JobFailed(Exception):
    """A job that cannot finish, with a message-catalogue key and parameters saying why."""

    def __init__(self, key: str, detail: str = "", **params: object):
        super().__init__(detail or key)
        self.key = key
        self.params = params
        self.detail = detail

    def message(self) -> dict:
        return {"key": self.key, "params": self.params}


JobFunction = Callable[..., None]
_registry: dict[str, tuple[Queue, Task]] = {}


def job(kind: str, queue: Queue) -> Callable[[JobFunction], JobFunction]:
    """Register `fn(ctx, **kwargs)` as the task that runs jobs of this kind on this queue."""

    def register(fn: JobFunction) -> JobFunction:
        @celery_app.task(name=f"chorus.{kind}")
        def run(job_id: int, **kwargs: Any) -> None:
            with get_sessionmaker()() as session:
                row = session.get(Job, job_id)
                if row is None or row.state in (JobState.CANCELLED, JobState.DONE):
                    return
                ctx = JobContext(session, row)
                ctx._set_state(JobState.RUNNING, started_at=row.started_at or _now())
                try:
                    fn(ctx, **kwargs)
                except JobFailed as exc:
                    # An expected failure: the reason is for the user, not a crash to trace.
                    session.rollback()
                    ctx._set_state(JobState.FAILED, finished_at=_now(), error=exc.message())
                    return
                except Exception as exc:
                    session.rollback()
                    ctx._set_state(
                        JobState.FAILED,
                        finished_at=_now(),
                        error={"key": "job.error.unexpected", "params": {"detail": repr(exc)}},
                    )
                    raise
                ctx._set_state(JobState.DONE, finished_at=_now())

        _registry[kind] = (queue, run)
        return fn

    return register


def enqueue(session: Session, kind: str, work_id: int | None = None, **kwargs: Any) -> Job:
    """Create the job row and put its task on the kind's queue."""
    queue, task = _registry[kind]
    row = Job(work_id=work_id, kind=kind, queue=queue, state=JobState.QUEUED, progress={})
    session.add(row)
    session.commit()
    events.publish("job", row.to_dict())
    task.apply_async(args=[row.id], kwargs=kwargs, queue=queue.value)
    return row
