"""Formats Chorus has no reader for (MOBI, AZW3, DOCX, FB2, RTF, ODT…), converted to EPUB by
Calibre's `ebook-convert` and then read by the EPUB reader.

Calibre is GPL, so it only ever runs as a separate program (docs/spec/02-architecture.md). It
picks the input format from the file's extension, so the upload keeps its own. Its failures are
recognised and turned into messages: DRM, a format it cannot read, and a conversion that runs
past the time limit.
"""

import os
import re
import signal
import subprocess
import tempfile
from pathlib import Path

from chorus.config import get_settings
from chorus.importing import ImportRejected

# What Calibre says when a book is locked: its DRMError, or the MOBI reader's own words.
DRM = re.compile(r"DRMError|locked (?:by|with) DRM|is DRM.?protected|has DRM", re.I)
UNKNOWN_FORMAT = re.compile(r"No plugin to handle input format|Unknown input format", re.I)


def _command() -> list[str]:
    return [get_settings().ebook_convert]


def convert_to_epub(data: bytes, extension: str) -> bytes:
    """The Source converted to EPUB. `extension` is the upload's own, such as ".azw3"."""
    timeout = get_settings().calibre_timeout_seconds
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", extension):
        # Calibre needs the extension to know the format.
        raise ImportRejected("import.error.unsupported_format", format="")
    extension = extension.lower()
    with tempfile.TemporaryDirectory(prefix="chorus-calibre-") as folder:
        source = Path(folder) / f"source{extension}"
        target = Path(folder) / "converted.epub"
        source.write_bytes(data)
        output = _run([*_command(), str(source), str(target)], timeout)
        if DRM.search(output):
            raise ImportRejected("import.error.drm", output[-2000:])
        if UNKNOWN_FORMAT.search(output):
            raise ImportRejected(
                "import.error.unsupported_format", output[-2000:], format=extension.lstrip(".")
            )
        if not target.is_file() or target.stat().st_size == 0:
            raise ImportRejected("import.error.conversion_failed", output[-2000:])
        return target.read_bytes()


def _run(command: list[str], timeout: int) -> str:
    """Runs Calibre in its own process group, so a conversion past the time limit is stopped
    together with any worker processes it started. Returns everything it printed."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise ImportRejected("import.error.converter_missing", str(exc)) from exc
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _stop(process)
        raise ImportRejected(
            "import.error.conversion_timeout", f"after {timeout} s", minutes=max(1, timeout // 60)
        ) from exc
    return output or ""


def _stop(process: subprocess.Popen) -> None:
    try:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.communicate()
