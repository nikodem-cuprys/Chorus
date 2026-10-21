"""Entry point of the `worker` service: one Celery worker per queue, each with its own concurrency.

Running the queues as separate workers is what keeps the GPU queue at one task at a time while
the other queue runs several. If either worker exits, the other is stopped and the service exits,
so Docker restarts both.

Before the workers start, the startup check (chorus.healthcheck) runs in its own process and
stores its result for the interface. A failed check is reported, not fatal: the workers still
start, so jobs that do not need what failed can run.

Then the First run (chorus.firstrun) downloads any model that is not yet in the models volume, and
the workers start only when both are in place: no job runs without its model.

Before they start, every job that was queued or running when the worker last stopped is sent
again (chorus.jobs.recover), so a job cut off by a crash, a reboot or a restart of this container
resumes by itself; a paused job stays paused.
"""

import signal
import subprocess
import sys

from chorus import firstrun, tasks  # noqa: F401  (tasks: job kinds, for recover)
from chorus.db import get_sessionmaker
from chorus.jobs import CONCURRENCY, recover


def main() -> int:
    subprocess.run([sys.executable, "-m", "chorus.healthcheck", "--store"], check=False)
    firstrun.ensure_models()
    with get_sessionmaker()() as session:
        for row in recover(session):
            print(f"worker: job {row.id} ({row.kind}) sent again", flush=True)

    workers = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "chorus.tasks",
                "worker",
                "--queues",
                queue.value,
                "--concurrency",
                str(concurrency),
                "--hostname",
                f"{queue.value}@%h",
                "--loglevel",
                "INFO",
            ]
        )
        for queue, concurrency in CONCURRENCY.items()
    ]

    def stop(*_: object) -> None:
        for w in workers:
            if w.poll() is None:
                w.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    # Wait until one worker exits, then stop the rest.
    while all(w.poll() is None for w in workers):
        try:
            workers[0].wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
    stop()
    return max(w.wait() for w in workers)


if __name__ == "__main__":
    sys.exit(main())
