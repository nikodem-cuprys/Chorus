"""Tests against the running Compose stack, skipped unless CHORUS_STACK_URL is set.

CHORUS_DEV=true docker compose up -d --build
CHORUS_STACK_URL=http://localhost:8000 pytest tests/integration
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx2 as httpx
import pytest

URL = os.environ.get("CHORUS_STACK_URL")
REPO = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.skipif(not URL, reason="CHORUS_STACK_URL is not set")

# On an empty models volume the First run downloads 5.9 GB before the worker takes jobs.
FIRST_RUN_SECONDS = float(os.environ.get("CHORUS_FIRST_RUN_SECONDS", 4 * 3600))


@pytest.fixture(scope="module", autouse=True)
def models_in_place():
    if not URL:
        return
    with httpx.Client(base_url=URL, timeout=10) as client:
        deadline = time.monotonic() + FIRST_RUN_SECONDS
        while not client.get("/api/system/models").json()["ready"]:
            if time.monotonic() > deadline:
                pytest.fail("the First run did not finish")
            time.sleep(10)


def _start(client: httpx.Client, queue: str, steps: int, step_seconds: float) -> int:
    response = client.post(
        "/api/dev/jobs", json={"queue": queue, "steps": steps, "step_seconds": step_seconds}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _listen(events: list[dict], stop: threading.Event) -> None:
    with httpx.Client(base_url=URL, timeout=None) as client:
        with client.stream("GET", "/api/events") as stream:
            name = None
            for line in stream.iter_lines():
                if stop.is_set():
                    return
                if line.startswith("event: "):
                    name = line[len("event: ") :]
                elif line.startswith("data: ") and name == "job":
                    events.append(json.loads(line[len("data: ") :]))


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def test_first_run_has_put_both_pinned_models_in_place():
    with httpx.Client(base_url=URL, timeout=10) as client:
        body = client.get("/api/system/models").json()
    assert body["error"] is None
    assert [(m["id"], m["state"], m["done"] == m["size"]) for m in body["models"]] == [
        ("qwen", "done", True),
        ("chatterbox", "done", True),
    ]
    assert [m["size"] for m in body["models"]] == [2_740_937_888, 3_191_966_992]


def test_jobs_run_on_their_queues_and_report_over_sse():
    events: list[dict] = []
    stop = threading.Event()
    listener = threading.Thread(target=_listen, args=(events, stop), daemon=True)
    listener.start()
    time.sleep(1)  # let the stream connect before the jobs start

    with httpx.Client(base_url=URL, timeout=10) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        gpu_a = _start(client, "gpu", steps=4, step_seconds=0.5)
        gpu_b = _start(client, "gpu", steps=4, step_seconds=0.5)
        other = _start(client, "other", steps=4, step_seconds=0.5)
        ids = {gpu_a, gpu_b, other}

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            jobs = {i: client.get(f"/api/jobs/{i}").json() for i in ids}
            if all(j["state"] == "done" for j in jobs.values()):
                break
            time.sleep(0.5)
        else:
            pytest.fail(f"jobs did not finish: {jobs}")
    stop.set()

    # Progress reached the browser's stream for every job.
    for i in ids:
        progress = [e["progress"].get("percent") for e in events if e["id"] == i]
        assert 100 in progress, f"no progress events for job {i}"

    # The two GPU jobs never overlapped.
    first, second = sorted((jobs[gpu_a], jobs[gpu_b]), key=lambda j: j["started_at"])
    assert _when(first["finished_at"]) <= _when(second["started_at"])

    # The other queue ran alongside the GPU queue.
    o = jobs[other]
    assert _when(o["started_at"]) < _when(first["finished_at"])


def test_the_port_is_published_on_localhost_only():
    config = json.loads(
        subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    for name, service in config["services"].items():
        for port in service.get("ports", []):
            assert port.get("host_ip") == "127.0.0.1", f"{name} publishes {port}"


def test_the_startup_check_passes_on_this_machine():
    """Needs the GPU host: torch on the card, llama-server, Calibre and ffmpeg all work."""
    with httpx.Client(base_url=URL, timeout=10) as client:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            health = client.get("/api/system/health").json()
            if health["ok"] is not None:
                break
            time.sleep(2)
        else:
            pytest.fail("the worker never stored a startup check")
    failed = [(c["name"], c["detail"]) for c in health["checks"] if not c["ok"]]
    assert failed == []
    names = {c["name"] for c in health["checks"]}
    assert names == {"torch", "llama-server", "ebook-convert", "ffmpeg"}
