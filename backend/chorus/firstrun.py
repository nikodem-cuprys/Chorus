"""First run: the model weights, downloaded in pinned versions into the models volume.

The worker runs `ensure_models` before its Celery workers start, so no job runs until both models
are in place; the interface shows the First run screen until then (`/api/system/models` and the
`models` server-sent event).

Each file is pinned by repository, revision and SHA-256. It is downloaded to `<name>.part`,
resumed with an HTTP Range request when the `.part` is already there (a killed container), hashed,
and renamed into place only when the hash matches; a file with the wrong hash is downloaded again.
A file at its final name is therefore always a checked one, and a later start skips it.

The GPU code never downloads anything: Chatterbox is loaded with `ChatterboxTTS.from_local` from
`chatterbox_dir()` and llama-server is given `gguf_path()`, and the image sets Hugging Face's
offline mode (`HF_HUB_OFFLINE=1`).

Run by hand with `python -m chorus.firstrun`.
"""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from chorus import events
from chorus.config import get_settings

REDIS_KEY = "chorus:models"
CHUNK = 1024 * 1024
# How often progress goes to the browser while a file downloads.
REPORT_SECONDS = 0.5
# A file whose hash keeps failing is given up after this many downloads.
HASH_ATTEMPTS = 3
# Waiting time before trying again after a network error.
RETRY_SECONDS = 30


@dataclass(frozen=True)
class ModelFile:
    repo: str
    revision: str
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Model:
    id: str
    # The folder in the models volume.
    folder: str
    files: tuple[ModelFile, ...]

    @property
    def size(self) -> int:
        return sum(f.size for f in self.files)


# Qwen3.5-4B Q4_K_M: the exact file scored in tickets 08, 24 and M1 ticket 03.
QWEN = Model(
    id="qwen",
    folder="qwen3.5-4b",
    files=(
        ModelFile(
            "unsloth/Qwen3.5-4B-GGUF",
            "e87f176479d0855a907a41277aca2f8ee7a09523",
            "Qwen3.5-4B-Q4_K_M.gguf",
            2_740_937_888,
            "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4",
        ),
    ),
)

# Chatterbox 500M: the files `ChatterboxTTS.from_pretrained` of chatterbox-tts 0.1.7 fetches, at
# the revision every listening test so far used.
_CHATTERBOX_REV = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
CHATTERBOX = Model(
    id="chatterbox",
    folder="chatterbox",
    files=tuple(
        ModelFile("ResembleAI/chatterbox", _CHATTERBOX_REV, path, size, sha256)
        for path, size, sha256 in (
            (
                "ve.safetensors",
                5_695_784,
                "f0921cab452fa278bc25cd23ffd59d36f816d7dc5181dd1bef9751a7fb61f63c",
            ),
            (
                "t3_cfg.safetensors",
                2_129_653_744,
                "914cb1696f47527fe8852ca8f1fe1fa63cb34f76f9c715e84e067b744dd0da81",
            ),
            (
                "s3gen.safetensors",
                1_056_484_620,
                "2b78103c654207393955e4900aac14a12de8ef25f4b09424f1ef91941f161d4e",
            ),
            (
                "tokenizer.json",
                25_470,
                "d71e3a44eabb1784df9a68e9f95b251ecbf1a7af6a9f50835856b2ca9d8c14a5",
            ),
            (
                "conds.pt",
                107_374,
                "6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e",
            ),
        )
    ),
)

MODELS: tuple[Model, ...] = (QWEN, CHATTERBOX)


def model_dir(model: Model) -> Path:
    return get_settings().models_dir / model.folder


def gguf_path() -> Path:
    """The analysis model's file, for llama-server's `-m`."""
    return model_dir(QWEN) / QWEN.files[0].path


def chatterbox_dir() -> Path:
    """The voice model's folder, for `ChatterboxTTS.from_local`."""
    return model_dir(CHATTERBOX)


def _final(model: Model, file: ModelFile) -> Path:
    return model_dir(model) / file.path


def _part(model: Model, file: ModelFile) -> Path:
    return model_dir(model) / f"{file.path}.part"


def _url(file: ModelFile) -> str:
    base = get_settings().models_url.rstrip("/")
    return f"{base}/{file.repo}/resolve/{file.revision}/{file.path}"


def is_ready(models: tuple[Model, ...] | None = None) -> bool:
    """Every file is at its final name with its size; only checked files get there."""
    return all(
        _final(m, f).is_file() and _final(m, f).stat().st_size == f.size
        for m in models or MODELS
        for f in m.files
    )


# ---- Status, for the First run screen ----

# What the downloader is doing, beyond what the files on disk say: the model it is checking,
# and the last error. Kept in Redis so the web service can serve it.
_activity: dict = {"verifying": None, "error": None}


def _store_activity() -> None:
    import redis

    redis.Redis.from_url(get_settings().redis_url).set(REDIS_KEY, json.dumps(_activity))


def load_activity() -> dict:
    import redis

    raw = redis.Redis.from_url(get_settings().redis_url).get(REDIS_KEY)
    return json.loads(raw) if raw else {"verifying": None, "error": None}


def _done_bytes(model: Model, file: ModelFile) -> int:
    final = _final(model, file)
    if final.is_file():
        return final.stat().st_size
    part = _part(model, file)
    return min(part.stat().st_size, file.size) if part.is_file() else 0


def status(activity: dict | None = None, models: tuple[Model, ...] | None = None) -> dict:
    """Each model with its size and how much of it is on disk, read from the models volume."""
    activity = activity or {"verifying": None, "error": None}
    models = models or MODELS
    out = []
    for m in models:
        done = sum(_done_bytes(m, f) for f in m.files)
        ready = is_ready((m,))
        if ready:
            state = "done"
        elif activity.get("verifying") == m.id:
            state = "verifying"
        elif done:
            state = "downloading"
        else:
            state = "waiting"
        out.append({"id": m.id, "size": m.size, "done": done, "state": state})
    return {"ready": is_ready(models), "models": out, "error": activity.get("error")}


def _publish(models: tuple[Model, ...]) -> None:
    _store_activity()
    events.publish("models", status(_activity, models))


# ---- Downloading ----


class HashMismatch(Exception):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def _fetch(file: ModelFile, part: Path, on_progress: Callable[[], None]) -> None:
    """Download into `part`, continuing from its current length."""
    have = part.stat().st_size if part.is_file() else 0
    if have > file.size:
        part.unlink()
        have = 0
    if have == file.size:
        return
    request = urllib.request.Request(_url(file), headers={"User-Agent": "chorus"})
    if have:
        request.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(request, timeout=60) as response:
        # A server that ignores the Range sends the whole file again: start over.
        mode = "ab" if have and response.status == 206 else "wb"
        last = time.monotonic()
        with part.open(mode) as out:
            while block := response.read(CHUNK):
                out.write(block)
                if time.monotonic() - last >= REPORT_SECONDS:
                    out.flush()
                    on_progress()
                    last = time.monotonic()


def _download(model: Model, file: ModelFile, on_progress: Callable[[], None]) -> None:
    final, part = _final(model, file), _part(model, file)
    if final.is_file() and final.stat().st_size == file.size:
        return
    final.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(HASH_ATTEMPTS):
        _fetch(file, part, on_progress)
        _activity["verifying"] = model.id
        on_progress()
        try:
            if part.stat().st_size == file.size and _sha256(part) == file.sha256:
                part.replace(final)
                return
            part.unlink()
        finally:
            _activity["verifying"] = None
            on_progress()
    raise HashMismatch(f"{file.repo}/{file.path}: wrong SHA-256 after {HASH_ATTEMPTS} downloads")


def download_all(models: tuple[Model, ...] = MODELS) -> None:
    """Download every missing file once; raises on a network error or a hash that keeps failing."""

    def progress() -> None:
        _publish(models)

    for m in models:
        for f in m.files:
            _download(m, f, progress)


def ensure_models(models: tuple[Model, ...] = MODELS, retry_seconds: float = RETRY_SECONDS) -> None:
    """Block until every model is in place, trying again after errors (a cut network, a full
    disk) with the error shown on the First run screen."""
    _activity.update(verifying=None, error=None)
    _publish(models)
    while not is_ready(models):
        try:
            download_all(models)
            _activity["error"] = None
        except HashMismatch as exc:
            print(f"first run: {exc}", flush=True)
            _activity["error"] = {"key": "first_run.error.hash", "params": {}}
        except (urllib.error.URLError, OSError) as exc:
            print(f"first run: {exc!r}", flush=True)
            _activity["error"] = {
                "key": "first_run.error.download",
                "params": {"detail": str(getattr(exc, "reason", exc))},
            }
        _publish(models)
        if not is_ready(models):
            time.sleep(retry_seconds)


def main() -> int:
    ensure_models()
    print("first run: models in place", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
