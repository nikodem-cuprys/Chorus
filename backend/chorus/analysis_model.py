"""The analysis model behind an interface (docs/spec/02-architecture.md, Engines), with its one
implementation: Qwen3.5-4B Q4_K_M through llama.cpp's server.

The server is started once for a whole analysis, with every layer on the card, 8k context and one
slot (`-np 1`; more slots divide the context), and stopped at the end. Requests go to its
`/completion` endpoint with a ChatML prompt whose think block is already closed, so Qwen answers
without thinking first, at temperature 0, with the output held to a JSON schema: the settings of
every scoring run (wayfinding tickets 08 and 24, M1 ticket 03).
"""

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from chorus.config import get_settings

CONTEXT = 8192
# Loading 2.7 GB onto the card takes about 15 s; a request about 100 s at most on the samples.
START_SECONDS = 600
REQUEST_SECONDS = 1800


@dataclass
class Completion:
    # The parsed output, or None when it was cut off or the prompt left no room.
    output: dict | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    # Why there is no output: "context full", "cut off".
    problem: str | None = None
    extra: dict = field(default_factory=dict)


class AnalysisModel(Protocol):
    def complete(self, system: str, user: str, schema: dict, max_tokens: int) -> Completion:
        """One request: the output held to `schema`, at most `max_tokens` long (less if the
        prompt leaves less room in the context)."""
        ...


class ModelUnavailable(Exception):
    """The model could not be started or stopped answering."""


def chatml(system: str, user: str) -> str:
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LlamaServer:
    """llama.cpp's server as a child process; use it as a context manager."""

    def __init__(self, model_path: Path, program: str | None = None):
        self.model_path = model_path
        self.program = program or get_settings().llama_server
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen | None = None

    def __enter__(self) -> "LlamaServer":
        if not self.model_path.is_file():
            raise ModelUnavailable(f"{self.model_path} is missing")
        # The server's output goes to the worker's log.
        self.process = subprocess.Popen(
            [
                self.program,
                "-m",
                str(self.model_path),
                "-ngl",
                "all",
                "-c",
                str(CONTEXT),
                "-np",
                "1",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]  # fmt: skip
        )
        deadline = time.monotonic() + START_SECONDS
        while True:
            if self.process.poll() is not None:
                raise ModelUnavailable(f"llama-server exited with code {self.process.returncode}")
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=5) as response:
                    if response.status == 200:
                        return self
            except (urllib.error.URLError, OSError):
                pass  # 503 while the model loads, refused before the port opens
            if time.monotonic() > deadline:
                self.__exit__()
                raise ModelUnavailable("llama-server did not start in time")
            time.sleep(1)

    def __exit__(self, *_: object) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def _post(self, path: str, body: dict) -> dict:
        request = urllib.request.Request(
            self.url + path, json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_SECONDS) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ModelUnavailable(f"llama-server: {exc!r}") from exc

    def complete(self, system: str, user: str, schema: dict, max_tokens: int) -> Completion:
        prompt = chatml(system, user)
        n_prompt = len(self._post("/tokenize", {"content": prompt})["tokens"])
        budget = min(max_tokens, CONTEXT - n_prompt - 8)
        if budget < 64:
            return Completion(None, n_prompt, problem="context full")
        started = time.monotonic()
        result = self._post(
            "/completion",
            {"prompt": prompt, "n_predict": budget, "temperature": 0, "json_schema": schema},
        )
        timings = result.get("timings", {})
        done = Completion(
            None,
            n_prompt,
            timings.get("predicted_n", 0),
            round(time.monotonic() - started, 1),
            extra={"stop": result.get("stop_type")},
        )
        try:
            done.output = json.loads(result["content"])
        except json.JSONDecodeError:
            done.problem = "cut off"
        return done
