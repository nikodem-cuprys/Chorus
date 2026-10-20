import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from chorus import firstrun
from chorus.app import create_app
from chorus.config import get_settings
from chorus.firstrun import Model, ModelFile

WEIGHTS = bytes(range(256)) * 400  # 100 KiB
TOKENIZER = b'{"model": "tiny"}'


def _file(path: str, content: bytes) -> ModelFile:
    return ModelFile("org/repo", "abc123", path, len(content), hashlib.sha256(content).hexdigest())


ANALYSIS = Model("qwen", "qwen", (_file("model.gguf", WEIGHTS),))
VOICE = Model(
    "chatterbox", "chatterbox", (_file("t3.safetensors", WEIGHTS), _file("tok.json", TOKENIZER))
)
MODELS = (ANALYSIS, VOICE)
CONTENT = {"model.gguf": WEIGHTS, "t3.safetensors": WEIGHTS, "tok.json": TOKENIZER}


class Hub:
    """A stand-in for Hugging Face's /resolve/ URLs that understands Range requests."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str | None]] = []
        # path -> how many more times to send damaged bytes
        self.corrupt: dict[str, int] = {}
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                name = self.path.rsplit("/", 1)[-1]
                assert self.path == f"/org/repo/resolve/abc123/{name}"
                rng = self.headers.get("Range")
                hub.requests.append((name, rng))
                body = CONTENT[name]
                if hub.corrupt.get(name):
                    hub.corrupt[name] -= 1
                    body = b"x" * len(body)
                start = int(rng.removeprefix("bytes=").rstrip("-")) if rng else 0
                self.send_response(206 if rng else 200)
                self.send_header("Content-Length", str(len(body) - start))
                self.end_headers()
                self.wfile.write(body[start:])

            def log_message(self, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"


@pytest.fixture
def hub(tmp_path, monkeypatch) -> Hub:
    server = Hub()
    monkeypatch.setattr(get_settings(), "models_dir", tmp_path / "models")
    monkeypatch.setattr(get_settings(), "models_url", server.url)
    monkeypatch.setattr(firstrun, "_store_activity", lambda: None)
    monkeypatch.setattr(firstrun, "_activity", {"verifying": None, "error": None})
    yield server
    server.server.shutdown()


def test_an_empty_models_volume_is_downloaded_and_checked(hub, published):
    assert not firstrun.is_ready(MODELS)
    firstrun.ensure_models(MODELS, retry_seconds=0)

    assert firstrun.is_ready(MODELS)
    models_dir = get_settings().models_dir
    assert (models_dir / "qwen" / "model.gguf").read_bytes() == WEIGHTS
    assert (models_dir / "chatterbox" / "tok.json").read_bytes() == TOKENIZER
    assert not list(models_dir.rglob("*.part"))

    last = [e for e in published if e["event"] == "models"][-1]
    assert last["ready"] is True
    assert [(m["id"], m["state"], m["done"] == m["size"]) for m in last["models"]] == [
        ("qwen", "done", True),
        ("chatterbox", "done", True),
    ]


def test_the_next_start_downloads_nothing(hub):
    firstrun.ensure_models(MODELS, retry_seconds=0)
    hub.requests.clear()
    firstrun.ensure_models(MODELS, retry_seconds=0)
    assert hub.requests == []


def test_an_interrupted_download_resumes_where_it_stopped(hub):
    part = get_settings().models_dir / "qwen" / "model.gguf.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(WEIGHTS[:40_000])  # what a killed container leaves behind

    firstrun.ensure_models(MODELS, retry_seconds=0)

    assert ("model.gguf", "bytes=40000-") in hub.requests
    assert (part.parent / "model.gguf").read_bytes() == WEIGHTS


def test_a_file_with_the_wrong_hash_is_downloaded_again(hub):
    hub.corrupt["tok.json"] = 1
    firstrun.ensure_models(MODELS, retry_seconds=0)

    assert [r for r in hub.requests if r[0] == "tok.json"] == [("tok.json", None)] * 2
    assert (get_settings().models_dir / "chatterbox" / "tok.json").read_bytes() == TOKENIZER


def test_a_hash_that_keeps_failing_is_shown_and_tried_again(hub, published, monkeypatch):
    hub.corrupt["tok.json"] = firstrun.HASH_ATTEMPTS  # one full round fails, the next works
    firstrun.ensure_models(MODELS, retry_seconds=0)

    errors = [e["error"] for e in published if e["event"] == "models" and e["error"]]
    assert errors[0] == {"key": "first_run.error.hash", "params": {}}
    assert firstrun.is_ready(MODELS)


def test_a_network_error_is_shown_and_tried_again(hub, published, monkeypatch):
    good_url = get_settings().models_url
    tries = []

    def sleep(_: float) -> None:
        tries.append(1)
        monkeypatch.setattr(get_settings(), "models_url", good_url)  # the network comes back

    monkeypatch.setattr(get_settings(), "models_url", "http://127.0.0.1:1")
    monkeypatch.setattr(firstrun.time, "sleep", sleep)
    firstrun.ensure_models(MODELS)

    assert tries == [1]
    errors = [e["error"] for e in published if e["event"] == "models" and e["error"]]
    assert errors[0]["key"] == "first_run.error.download"
    assert published[-1]["error"] is None and published[-1]["ready"] is True


def test_status_reads_progress_from_the_models_volume(hub):
    part = get_settings().models_dir / "qwen" / "model.gguf.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(WEIGHTS[:1000])

    result = firstrun.status({"verifying": None, "error": None}, MODELS)

    assert result["ready"] is False
    assert result["models"] == [
        {"id": "qwen", "size": len(WEIGHTS), "done": 1000, "state": "downloading"},
        {"id": "chatterbox", "size": len(WEIGHTS) + len(TOKENIZER), "done": 0, "state": "waiting"},
    ]
    verifying = firstrun.status({"verifying": "qwen", "error": None}, MODELS)
    assert verifying["models"][0]["state"] == "verifying"


def test_models_endpoint_serves_the_status(hub, monkeypatch):
    monkeypatch.setattr(firstrun, "MODELS", MODELS)
    monkeypatch.setattr(firstrun, "load_activity", lambda: {"verifying": None, "error": None})
    client = TestClient(create_app())

    body = client.get("/api/system/models").json()
    assert body["ready"] is False
    assert [m["state"] for m in body["models"]] == ["waiting", "waiting"]


def test_the_pinned_models_are_where_the_engines_look():
    assert firstrun.gguf_path().name == "Qwen3.5-4B-Q4_K_M.gguf"
    assert {f.path for f in firstrun.CHATTERBOX.files} == {
        "ve.safetensors",
        "t3_cfg.safetensors",
        "s3gen.safetensors",
        "tokenizer.json",
        "conds.pt",
    }
    for model in firstrun.MODELS:
        for f in model.files:
            assert len(f.revision) == 40 and len(f.sha256) == 64
