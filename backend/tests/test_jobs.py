from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.db import get_sessionmaker
from chorus.jobs import CONCURRENCY, enqueue, job
from chorus.models import Job, JobState, Queue


@job("test.fails", Queue.OTHER)
def failing_job(ctx) -> None:
    ctx.report(done=1)
    raise RuntimeError("boom")


def test_a_job_runs_and_reports_progress(published):
    client = TestClient(create_app())
    created = client.post("/api/dev/jobs", json={"queue": "other", "steps": 3, "step_seconds": 0})
    assert created.status_code == 201

    finished = client.get(f"/api/jobs/{created.json()['id']}").json()
    assert finished["state"] == "done"
    assert finished["progress"]["percent"] == 100
    assert finished["started_at"] and finished["finished_at"]

    states = [e["state"] for e in published]
    assert states[0] == "queued" and states[1] == "running" and states[-1] == "done"
    assert [e["progress"].get("done") for e in published if e["state"] == "running"][-1] == 3


def test_jobs_go_to_their_own_queue():
    with get_sessionmaker()() as session:
        gpu = enqueue(session, "dev.gpu", steps=1, step_seconds=0)
        other = enqueue(session, "dev.other", steps=1, step_seconds=0)
    assert (gpu.queue, other.queue) == (Queue.GPU, Queue.OTHER)


def test_a_failing_job_is_marked_failed_with_a_message_key(published):
    with get_sessionmaker()() as session:
        row = enqueue(session, "test.fails")
        session.refresh(row)
        assert row.state == JobState.FAILED
        assert row.error["key"] == "job.error.unexpected"
        assert row.finished_at is not None
    assert published[-1]["state"] == "failed"


def test_a_cancelled_job_is_not_run():
    with get_sessionmaker()() as session:
        row = Job(kind="dev.other", queue=Queue.OTHER, state=JobState.CANCELLED, progress={})
        session.add(row)
        session.commit()
        from chorus.dev_jobs import dev_other  # noqa: F401
        from chorus.jobs import _registry

        _registry["dev.other"][1].apply(args=[row.id])
        session.refresh(row)
        assert row.state == JobState.CANCELLED


def test_the_gpu_queue_has_one_slot():
    assert CONCURRENCY[Queue.GPU] == 1


def test_unknown_job_is_404_with_a_message_key():
    response = TestClient(create_app()).get("/api/jobs/999")
    assert response.status_code == 404
    assert response.json()["detail"]["key"] == "job.error.not_found"
