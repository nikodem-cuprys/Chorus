import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from chorus import analysis, exporting, jobs, voicing
from chorus.app import create_app
from chorus.assembly import assemble_part, parts_of
from chorus.db import get_sessionmaker
from chorus.jobs import (
    CANCEL,
    PAUSE,
    STOPPED_EXIT,
    JobContext,
    Pace,
    Stopped,
    enqueue,
    job,
    recover,
)  # fmt: skip
from chorus.models import Export, Job, JobState, Line, Queue, Work, WorkState
from chorus.voicing import voice_work
from tests import test_analysis
from tests.test_assembly import Model, make_work


@job("test.steps", Queue.OTHER)
def steps_job(ctx: JobContext, steps: int = 4, ask_at: int | None = None, ask: str = PAUSE):
    """Counts steps, saving each, from where it stopped; asks for `ask` itself at `ask_at`, as
    the user would from the browser."""
    for step in range(ctx.job.progress.get("done", 0), steps):
        ctx.check()
        ctx.report(done=step + 1, total=steps)
        if step + 1 == ask_at:
            with get_sessionmaker()() as other:
                other.get(Job, ctx.job.id).request = ask
                other.commit()


def fresh(session, row: Job) -> Job:
    session.expire_all()
    return session.get(Job, row.id)


# ---- Pause, resume, cancel ----


def test_a_running_job_pauses_after_its_current_step_and_resumes_from_there():
    with get_sessionmaker()() as session:
        row = enqueue(session, "test.steps", ask_at=2)
        row = fresh(session, row)
        assert (row.state, row.request, row.progress["done"]) == (JobState.PAUSED, None, 2)
        assert row.finished_at is None

        jobs.resume(session, row)  # runs at once in the tests
        row = fresh(session, row)
        assert (row.state, row.progress["done"]) == (JobState.DONE, 4)


def test_a_running_job_cancels_keeping_what_it_did():
    with get_sessionmaker()() as session:
        row = fresh(session, enqueue(session, "test.steps", ask_at=1, ask=CANCEL))
        assert (row.state, row.progress["done"]) == (JobState.CANCELLED, 1)
        assert row.finished_at is not None
        with pytest.raises(jobs.NotAllowed):
            jobs.resume(session, row)


def test_a_queued_job_pauses_or_cancels_at_once():
    with get_sessionmaker()() as session:
        row = Job(kind="test.steps", queue=Queue.OTHER, state=JobState.QUEUED, progress={})
        session.add(row)
        session.commit()
        assert jobs.pause(session, row).state == JobState.PAUSED
        # Its message, when it comes, finds it paused and does nothing.
        jobs._registry["test.steps"][1].apply(args=[row.id])
        assert fresh(session, row).progress == {}
        assert jobs.cancel(session, row).state == JobState.CANCELLED
        with pytest.raises(jobs.NotAllowed):
            jobs.pause(session, row)


def test_an_old_message_for_a_job_sent_again_is_ignored():
    with get_sessionmaker()() as session:
        row = Job(
            kind="test.steps", queue=Queue.OTHER, state=JobState.QUEUED, progress={},
            task_id="the-new-one",
        )  # fmt: skip
        session.add(row)
        session.commit()
        jobs._registry["test.steps"][1].apply(args=[row.id], task_id="an-old-one")
        assert fresh(session, row).state == JobState.QUEUED
        jobs._registry["test.steps"][1].apply(args=[row.id], task_id="the-new-one")
        assert fresh(session, row).state == JobState.DONE


def test_the_api_controls_jobs():
    client = TestClient(create_app())
    with get_sessionmaker()() as session:
        row = Job(kind="test.steps", queue=Queue.OTHER, state=JobState.QUEUED, progress={})
        session.add(row)
        session.commit()
        job_id = row.id
    assert client.post(f"/api/jobs/{job_id}/pause").json()["state"] == "paused"
    assert client.post(f"/api/jobs/{job_id}/resume").json()["state"] == "queued"
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "done"  # run at once here
    refused = client.post(f"/api/jobs/{job_id}/cancel")
    assert refused.status_code == 409
    assert refused.json()["detail"]["key"] == "job.error.cannot_cancel"
    assert client.post(f"/api/jobs/{job_id}/jump").status_code == 404


# ---- After a crash ----


def test_the_worker_sends_again_what_was_cut_off_and_leaves_paused_jobs_paused():
    with get_sessionmaker()() as session:

        def row(state, request=None, **progress):
            r = Job(
                kind="test.steps", queue=Queue.OTHER, state=state, request=request,
                progress=progress, kwargs={"steps": 3},
            )  # fmt: skip
            session.add(r)
            return r

        running = row(JobState.RUNNING, done=1)  # cut off after its first step
        queued = row(JobState.QUEUED)
        paused = row(JobState.PAUSED, done=2)
        pausing = row(JobState.RUNNING, request=PAUSE)  # asked to pause, then the crash
        finished = row(JobState.DONE, done=3)
        session.commit()

        assert [r.id for r in recover(session)] == [running.id, queued.id]
        assert fresh(session, running).state == JobState.DONE
        assert fresh(session, running).progress["done"] == 3
        assert fresh(session, queued).state == JobState.DONE
        assert fresh(session, paused).state == JobState.PAUSED
        assert fresh(session, pausing).state == JobState.PAUSED
        assert fresh(session, finished).state == JobState.DONE


# ---- Time left ----


def test_time_left_comes_from_the_speed_measured_in_this_run(monkeypatch):
    clock = iter([100.0, 110.0, 130.0])
    monkeypatch.setattr(jobs.time, "monotonic", lambda: next(clock))
    pace = Pace()
    assert pace.seconds_left(0.25, 1.0) is None  # the starting point: done before this run
    assert pace.seconds_left(0.30, 1.0) == 140  # 0.05 in 10 s, 0.70 to go
    assert pace.seconds_left(0.40, 1.0) == 120  # 0.15 in 30 s, 0.60 to go


# ---- Voicing ----


def stop_after(steps: int, request: str = PAUSE):
    count = 0

    def check():
        nonlocal count
        count += 1
        if count > steps:
            raise Stopped(request)

    return check


def test_paused_voicing_stops_within_a_sentence_and_resumes_at_the_next_line():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voiced = lambda: {ln.id for ln in session.scalars(select(Line)) if ln.take}  # noqa: E731
        # The front matter's one sentence (both halves), then chapter one's T3 and two S3Gen.
        with pytest.raises(Stopped):
            voice_work(session, work, Model(), lambda **p: None, check=stop_after(2 + 10 + 2))
        session.rollback()
        first = voiced()
        assert len(first) == 1 + 2  # the title, and chapter one's first two lines

        reports: list[dict] = []
        assert voice_work(session, work, Model(), lambda **p: reports.append(p)) == 12 - len(first)
        assert voiced() > first
        # Resumed in chapter one: still "part 2 of 3", counted over the whole Work.
        assert (reports[0]["part"], reports[0]["parts"], reports[0]["chapter"]) == (2, 3, "1")


def test_voicing_progress_moves_during_t3_and_estimates_the_time_left():
    with get_sessionmaker()() as session:
        work = make_work(session)
        reports: list[dict] = []
        voice_work(session, work, Model(), lambda **p: reports.append(p))
        chapter_one = [r for r in reports if r["chapter"] == "1"]
        # Before any line of the chapter is saved, its T3 half already moves the percentage.
        t3 = [r["percent"] for r in chapter_one if r["done"] == 1]
        assert len(set(t3)) > 1
        assert reports[-1]["percent"] == 100 and reports[-1]["done"] == reports[-1]["total"]
        # Never backwards, also when a line is saved between two sentences.
        percents = [r["percent"] for r in reports]
        assert percents == sorted(percents)
        assert all(r["seconds_left"] is None or r["seconds_left"] >= 0 for r in reports)
        assert any(r["seconds_left"] is not None for r in reports)
        assert {r["parts"] for r in reports} == {3}


def test_a_cancelled_voicing_job_leaves_the_work_analysed(monkeypatch):
    with get_sessionmaker()() as session:
        work = make_work(session)

        def child(job_id):
            with get_sessionmaker()() as other:
                other.get(Job, job_id).request = CANCEL
                other.commit()
            return STOPPED_EXIT

        monkeypatch.setattr(voicing, "run_child", child)
        row = enqueue(session, "voicing", work_id=work.id)
        assert fresh(session, row).state == JobState.CANCELLED
        assert session.get(Work, work.id).state == WorkState.ANALYSED
        # No assembly is queued for a voicing that did not finish.
        assert [j.kind for j in session.scalars(select(Job))] == ["voicing"]


def test_a_paused_voicing_job_keeps_the_work_voicing(monkeypatch):
    with get_sessionmaker()() as session:
        work = make_work(session)

        def child(job_id):
            with get_sessionmaker()() as other:
                other.get(Job, job_id).request = PAUSE
                other.commit()
            return STOPPED_EXIT

        monkeypatch.setattr(voicing, "run_child", child)
        row = enqueue(session, "voicing", work_id=work.id)
        assert fresh(session, row).state == JobState.PAUSED
        assert session.get(Work, work.id).state == WorkState.VOICING


def test_discarding_audio_throws_away_takes_seeds_and_chapters():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        for part in parts_of(session, work):
            assemble_part(session, work, part)
        work.state = WorkState.READY
        busy = Job(work_id=work.id, kind="voicing", queue=Queue.GPU, state=JobState.PAUSED)
        session.add(busy)
        session.commit()

        client = TestClient(create_app())
        refused = client.post(f"/api/works/{work.id}/discard-audio")
        assert refused.status_code == 409
        assert refused.json()["detail"]["key"] == "work.error.audio_busy"

        assert client.get(f"/api/works/{work.id}").json()["voiced_lines"] == 12
        busy.state = JobState.CANCELLED
        session.commit()
        assert client.post(f"/api/works/{work.id}/discard-audio").json()["state"] == "analysed"
        session.expire_all()
        assert all(ln.take is None and ln.seed is None for ln in session.scalars(select(Line)))
        assert client.get(f"/api/works/{work.id}").json()["voiced_lines"] == 0
        assert not voicing.lines_dir(work.id).exists()
        assert all(c.audio is None for c in work.chapters) and work.matter_audio == {}


# ---- Analysis ----


def test_paused_analysis_stops_after_the_current_chunk(monkeypatch):
    with get_sessionmaker()() as session:
        work = test_analysis.make_work(
            session, [test_analysis.CHAPTER_ONE, test_analysis.CHAPTER_TWO]
        )
        model = test_analysis.Model(test_analysis.CAST_ANSWERS, test_analysis.SPEAKERS)
        with pytest.raises(Stopped):
            analysis.analyse(session, work, model, lambda **p: None, check=stop_after(1))
        assert model.calls == ["cast"]
        assert work.analysis["done"] == 1

        again = test_analysis.Model(test_analysis.CAST_ANSWERS, test_analysis.SPEAKERS)
        analysis.analyse(session, work, again, lambda **p: None)
        assert again.calls == ["cast", "attribution", "attribution"]


def test_a_cancelled_analysis_leaves_the_work_imported(monkeypatch):
    with get_sessionmaker()() as session:
        work = test_analysis.make_work(session, [test_analysis.CHAPTER_ONE])

        def child(job_id):
            with get_sessionmaker()() as other:
                other.get(Job, job_id).request = CANCEL
                other.commit()
            return STOPPED_EXIT

        monkeypatch.setattr(analysis, "run_child", child)
        row = enqueue(session, "analysis", work_id=work.id)
        assert fresh(session, row).state == JobState.CANCELLED
        assert session.get(Work, work.id).state == WorkState.IMPORTED


# ---- Export ----


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_a_stopped_export_leaves_the_previous_one_as_it_was():
    with get_sessionmaker()() as session:
        work = make_work(session)
        voice_work(session, work, Model(), lambda **p: None)
        for part in parts_of(session, work):
            assemble_part(session, work, part)
        work.state = WorkState.READY
        session.commit()
        before = exporting.export_work(session, work, "mp3", lambda **p: None)

        with pytest.raises(Stopped):
            exporting.export_work(session, work, "mp3", lambda **p: None, check=stop_after(2))
        assert [e.id for e in session.scalars(select(Export))] == [before.id]
        assert all((exporting.exports_dir() / f).is_file() for f in before.files)
        assert not list(exporting.exports_dir().rglob(".export-*"))
