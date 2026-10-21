"""Background jobs: Celery on Redis, with a one-slot GPU queue and a queue for everything else.

A job is a row in the `job` table plus a Celery task that carries the row's id. Tasks report
progress through `JobContext.report`, which saves it and publishes it for the browser.

**Control** (docs/spec/02-architecture.md, Jobs): pausing or cancelling a running job saves the
request on its row; the job looks at it between steps (`JobContext.check`, after a line, a
chunk, a part) and stops by raising `Stopped`, keeping all it finished. A queued or paused job is
paused or cancelled at once. Resuming sends the job again, and it continues where it stopped,
since every stage saves as it goes. A job run in a child process stops by exiting with
`STOPPED_EXIT`.

**Sent again:** each job keeps its arguments and the id of the Celery message that may run it;
any other message for it (a copy Celery hands out again after a crash) is ignored. When the
worker starts (`recover`), every job that was queued or running is sent again, so a job cut off
by a crash or restart resumes by itself; a paused job stays paused.
"""

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from celery import Celery, Task
from sqlalchemy import select
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


# How a job run in a child process says it stopped at a pause or cancel request.
STOPPED_EXIT = 3
# Requests a running job can be sent.
PAUSE, CANCEL = "pause", "cancel"


class Stopped(Exception):
    """Raised by a job that stops at a request: paused or cancelled, keeping what it finished."""

    def __init__(self, request: str):
        super().__init__(request)
        self.request = request


class JobContext:
    """What a running task uses to talk about its job."""

    def __init__(self, session: Session, job: Job):
        self.session = session
        self.job = job

    def report(self, **progress: Any) -> None:
        self.job.progress = {**(self.job.progress or {}), **progress}
        self._save()

    def requested(self) -> str | None:
        """Pause or cancel, if the user asked for either since the job started."""
        self.session.refresh(self.job, ["request"])
        return self.job.request

    def check(self) -> None:
        """Called between steps: raises Stopped when the user asked to pause or cancel."""
        request = self.requested()
        if request:
            raise Stopped(request)

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
        @celery_app.task(name=f"chorus.{kind}", bind=True)
        def run(task: Task, job_id: int, **kwargs: Any) -> None:
            with get_sessionmaker()() as session:
                row = session.get(Job, job_id)
                if row is None or row.state not in (JobState.QUEUED, JobState.RUNNING):
                    return  # paused, cancelled or finished since it was sent
                if row.task_id and task.request.id and task.request.id != row.task_id:
                    return  # an old message: the job was sent again since
                ctx = JobContext(session, row)
                ctx._set_state(JobState.RUNNING, started_at=row.started_at or _now())
                try:
                    fn(ctx, **kwargs)
                except Stopped as exc:
                    session.rollback()
                    if exc.request == CANCEL:
                        ctx._set_state(JobState.CANCELLED, finished_at=_now(), request=None)
                    else:
                        ctx._set_state(JobState.PAUSED, request=None)
                    return
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
    queue, _ = _registry[kind]
    row = Job(
        work_id=work_id, kind=kind, queue=queue, state=JobState.QUEUED, progress={}, kwargs=kwargs
    )
    session.add(row)
    session.commit()
    send(session, row)
    return row


def send(session: Session, row: Job) -> None:
    """Puts the job on its queue as a new message; any earlier one is ignored from now on."""
    _, task = _registry[row.kind]
    row.state = JobState.QUEUED
    row.request = None
    row.task_id = uuid.uuid4().hex
    session.commit()
    events.publish("job", row.to_dict())
    task.apply_async(
        args=[row.id], kwargs=row.kwargs or {}, queue=row.queue.value, task_id=row.task_id
    )


# ---- Control ----


class NotAllowed(Exception):
    """The job is not in a state that allows what was asked."""


def _publish(session: Session, row: Job) -> Job:
    session.commit()
    events.publish("job", row.to_dict())
    return row


def pause(session: Session, row: Job) -> Job:
    if row.state == JobState.QUEUED:
        row.state = JobState.PAUSED
    elif row.state == JobState.RUNNING:
        row.request = PAUSE
    else:
        raise NotAllowed
    return _publish(session, row)


def resume(session: Session, row: Job) -> Job:
    if row.state != JobState.PAUSED:
        raise NotAllowed
    send(session, row)
    return row


def cancel(session: Session, row: Job) -> Job:
    if row.state in (JobState.QUEUED, JobState.PAUSED):
        row.state, row.finished_at, row.request = JobState.CANCELLED, _now(), None
    elif row.state == JobState.RUNNING:
        row.request = CANCEL
    else:
        raise NotAllowed
    return _publish(session, row)


def recover(session: Session) -> list[Job]:
    """Sends again every job that was queued or running when the worker stopped; one asked to
    pause or cancel while it ran is paused or cancelled instead. Run before the workers start."""
    resent = []
    rows = session.scalars(
        select(Job).where(Job.state.in_([JobState.QUEUED, JobState.RUNNING])).order_by(Job.id)
    )
    for row in list(rows):
        if row.kind not in _registry:
            continue
        if row.request == CANCEL:
            row.state, row.finished_at, row.request = JobState.CANCELLED, _now(), None
            _publish(session, row)
        elif row.request == PAUSE:
            row.state, row.request = JobState.PAUSED, None
            _publish(session, row)
        else:
            send(session, row)
            resent.append(row)
    return resent


# ---- Time left ----


class Pace:
    """A time-left estimate from the speed measured since the first call in this run."""

    def __init__(self) -> None:
        self._start: tuple[float, float] | None = None

    def seconds_left(self, done: float, total: float) -> int | None:
        now = time.monotonic()
        if self._start is None:
            self._start = (now, done)
            return None
        started, done_then = self._start
        if done <= done_then or now <= started:
            return None
        rate = (done - done_then) / (now - started)
        return round(max(0.0, total - done) / rate)
