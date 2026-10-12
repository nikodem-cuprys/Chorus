"""The startup check of the GPU stack and the external programs.

The worker runs it when it starts (it is the only service with the GPU) and stores the result in
Redis; the web service serves it at /api/system/health, and the interface shows a clear message
instead of the app when a check failed. Run by hand with `python -m chorus.healthcheck`.

It runs as its own process (`--store` saves the result) so the CUDA context the torch check
creates is gone when it exits: the card's memory belongs to the models.
"""

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from chorus.config import get_settings

REDIS_KEY = "chorus:health"


@dataclass
class CheckResult:
    name: str
    ok: bool
    # A message-catalogue key and its parameters.
    message: dict
    # Technical detail for the logs and the "details" fold-out, never translated.
    detail: str = ""


@dataclass
class Health:
    checked_at: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def to_dict(self) -> dict:
        return {
            "checked_at": self.checked_at,
            "ok": self.ok,
            "checks": [asdict(c) for c in self.checks],
        }


def _msg(key: str, **params: object) -> dict:
    return {"key": key, "params": params}


def check_torch() -> CheckResult:
    """A matrix multiply on the card. A wheel without Pascal kernels fails right here."""
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        return CheckResult("torch", False, _msg("health.torch.missing"), repr(exc))

    cuda = torch.version.cuda or ""
    if not cuda.startswith("12."):
        return CheckResult(
            "torch",
            False,
            _msg("health.torch.wrong_build", version=torch.__version__, cuda=cuda or "none"),
            f"torch {torch.__version__} is built for CUDA {cuda or 'none'}, not CUDA 12",
        )
    if not torch.cuda.is_available():
        return CheckResult(
            "torch", False, _msg("health.torch.no_gpu"), "torch.cuda.is_available() is False"
        )
    try:
        name = torch.cuda.get_device_name(0)
        x = torch.randn(1024, 1024, device="cuda")
        total = float((x @ x).sum().item())
        torch.cuda.synchronize()
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        if "no kernel image" in text:
            return CheckResult(
                "torch",
                False,
                _msg("health.torch.no_kernel", version=torch.__version__),
                text,
            )
        return CheckResult("torch", False, _msg("health.torch.failed"), text)
    if total != total:  # NaN
        return CheckResult("torch", False, _msg("health.torch.failed"), "matrix multiply gave NaN")
    major, minor = torch.cuda.get_device_capability(0)
    return CheckResult(
        "torch",
        True,
        _msg("health.torch.ok", device=name),
        f"torch {torch.__version__}, CUDA {cuda}, {name}, sm_{major}{minor}",
    )


def _program(name: str, command: list[str], first_line: bool = True) -> CheckResult:
    if shutil.which(command[0]) is None:
        return CheckResult(name, False, _msg("health.program.missing", program=command[0]), "")
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name, False, _msg("health.program.failed", program=command[0]), repr(exc)
        )
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0:
        return CheckResult(
            name, False, _msg("health.program.failed", program=command[0]), output[-2000:]
        )
    return CheckResult(
        name,
        True,
        _msg("health.program.ok", program=command[0]),
        (output.splitlines()[0] if output else "") if first_line else output[-2000:],
    )


def check_llama_server() -> CheckResult:
    """llama.cpp loads its CUDA backend at run time; if a library is missing it quietly runs on
    the CPU instead. So the check asks for its devices and needs a CUDA one."""
    program = get_settings().llama_server
    result = _program("llama-server", [program, "--list-devices"], first_line=False)
    if not result.ok:
        return result
    devices = [
        line.strip() for line in result.detail.splitlines() if line.strip().startswith("CUDA")
    ]
    if not devices:
        return CheckResult("llama-server", False, _msg("health.llama.no_gpu"), result.detail)
    return CheckResult("llama-server", True, _msg("health.program.ok", program=program), devices[0])


def check_ebook_convert() -> CheckResult:
    return _program("ebook-convert", ["ebook-convert", "--version"])


def check_ffmpeg() -> CheckResult:
    return _program("ffmpeg", ["ffmpeg", "-hide_banner", "-version"])


CHECKS: list[Callable[[], CheckResult]] = [
    check_torch,
    check_llama_server,
    check_ebook_convert,
    check_ffmpeg,
]


def run_checks() -> Health:
    return Health(datetime.now(UTC).isoformat(), [check() for check in CHECKS])


def store(health: Health) -> None:
    import redis

    redis.Redis.from_url(get_settings().redis_url).set(REDIS_KEY, json.dumps(health.to_dict()))


def load() -> dict | None:
    import redis

    raw = redis.Redis.from_url(get_settings().redis_url).get(REDIS_KEY)
    return json.loads(raw) if raw else None


def main(argv: list[str]) -> int:
    health = run_checks()
    for c in health.checks:
        print(f"health {'ok  ' if c.ok else 'FAIL'} {c.name}: {c.detail}", flush=True)
    if "--store" in argv:
        store(health)
    return 0 if health.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
