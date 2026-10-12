"""Dummy jobs, one per queue, to exercise the job machinery until real stages exist."""

import time
from datetime import UTC, datetime

from chorus.jobs import JobContext, job
from chorus.models import Queue


def _count(ctx: JobContext, steps: int, step_seconds: float) -> None:
    for done in range(1, steps + 1):
        time.sleep(step_seconds)
        ctx.report(done=done, total=steps, percent=round(100 * done / steps))
    # Recorded so a test can check that GPU jobs never overlap.
    ctx.report(finished=datetime.now(UTC).isoformat())


@job("dev.gpu", Queue.GPU)
def dev_gpu(ctx: JobContext, steps: int = 5, step_seconds: float = 0.5) -> None:
    _count(ctx, steps, step_seconds)


@job("dev.other", Queue.OTHER)
def dev_other(ctx: JobContext, steps: int = 5, step_seconds: float = 0.5) -> None:
    _count(ctx, steps, step_seconds)
