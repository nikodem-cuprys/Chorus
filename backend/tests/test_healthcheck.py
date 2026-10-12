import sys

from fastapi.testclient import TestClient

from chorus import healthcheck
from chorus.app import create_app
from chorus.healthcheck import CheckResult, Health


def test_a_missing_program_fails_with_a_message_key():
    result = healthcheck._program("x", ["no-such-program-anywhere", "--version"])
    assert not result.ok
    assert result.message == {
        "key": "health.program.missing",
        "params": {"program": "no-such-program-anywhere"},
    }


def test_a_program_that_exits_with_an_error_fails():
    result = healthcheck._program("py", [sys.executable, "-c", "import sys; sys.exit('broken')"])
    assert not result.ok
    assert result.message["key"] == "health.program.failed"
    assert "broken" in result.detail


def test_a_working_program_passes_with_its_first_output_line():
    result = healthcheck._program("py", [sys.executable, "-c", "print('v1.2\\nmore')"])
    assert result.ok
    assert result.detail == "v1.2"


def test_torch_check_reports_a_missing_torch(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # makes `import torch` fail
    result = healthcheck.check_torch()
    assert not result.ok
    assert result.message["key"] == "health.torch.missing"


def test_health_is_ok_only_when_every_check_is():
    good = CheckResult("a", True, {"key": "k", "params": {}})
    bad = CheckResult("b", False, {"key": "k", "params": {}})
    assert Health("now", [good, good]).ok
    assert not Health("now", [good, bad]).to_dict()["ok"]


def test_health_endpoint_before_and_after_the_worker_checked(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr(healthcheck, "load", lambda: None)
    assert client.get("/api/system/health").json() == {"checked_at": None, "ok": None, "checks": []}

    failed = CheckResult("ffmpeg", False, {"key": "k", "params": {}})
    stored = Health("2026-10-12T00:00:00", [failed])
    monkeypatch.setattr(healthcheck, "load", lambda: stored.to_dict())
    body = client.get("/api/system/health").json()
    assert body["ok"] is False and body["checks"][0]["name"] == "ffmpeg"


def test_llama_server_without_a_cuda_device_fails(monkeypatch, tmp_path):
    fake = tmp_path / "fake_llama.py"
    fake.write_text("print('Available devices:')\nprint('  (none)')\n")
    monkeypatch.setattr(healthcheck, "_program", _fake_program(fake))
    result = healthcheck.check_llama_server()
    assert not result.ok
    assert result.message["key"] == "health.llama.no_gpu"


def test_llama_server_with_a_cuda_device_passes(monkeypatch, tmp_path):
    fake = tmp_path / "fake_llama.py"
    fake.write_text("print('Available devices:')\nprint('  CUDA0: NVIDIA GeForce GTX 1050 Ti')\n")
    monkeypatch.setattr(healthcheck, "_program", _fake_program(fake))
    result = healthcheck.check_llama_server()
    assert result.ok
    assert result.detail == "CUDA0: NVIDIA GeForce GTX 1050 Ti"


def _fake_program(script):
    real = healthcheck._program

    def run(name, command, first_line=True):
        return real(name, [sys.executable, str(script)], first_line)

    return run
