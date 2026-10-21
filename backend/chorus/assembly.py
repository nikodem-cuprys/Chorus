"""Assembly: each part's line audio put together into one file (docs/spec/03-pipeline.md,
Assembly).

A **part** is what the Work page plays as one file: the front matter (where the Work title and
author are read, before chapter one), each chapter, the back matter. Parts are named as in the
API: "front", "back", or the chapter's index.

**When:** a part is assembled once every voiced line in it has its current take: the voicing
job queues each part as soon as it is voiced, and the whole Work when it ends; a Work whose
parts are all assembled is ready to listen. A part with no voiced lines has no audio.

**How:** each take's own leading and trailing silence is cut (`trim`: everything quieter than
`SILENCE_DB`, keeping `MARGIN` of it), each take is followed by its pause (`pauses_after`), and
ffmpeg cuts, pads and joins the takes in one run into a FLAC file on the data volume.

**Pauses** come from `pauses.json` (chorus.voicing.pauses), read on every run, and from the
Script's structure only: between lines of one paragraph, at a new paragraph, between lines of
verse, after the Work title, a chapter title or an epigraph's last line (its source line), and
at a Section break. Where several apply, the longest wins.

**Cached:** each part keeps the key of what it was made from (every take and the pause after
it). A part whose key has not changed is not assembled again, so changing a pause in the
settings file and assembling again re-assembles every part.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile
from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus.config import get_settings
from chorus.jobs import JobContext, JobFailed, job
from chorus.languages import get_packs
from chorus.models import Chapter, Line, Queue, Work, WorkState
from chorus.voicing import lines_dir, needs_voicing, pauses, plan_line

# Quieter than this, relative to full scale, is silence at either end of a take.
SILENCE_DB = -50.0
# How much of that silence is kept at each end, so a soft start or end is not clipped.
MARGIN = 0.04
# How far the file's length may be from the sum of its trimmed takes and pauses.
LENGTH_TOLERANCE = 0.01
LONG_PAUSE_AFTER = frozenset({"work_title", "chapter_title"})


def audio_dir(work_id: int) -> Path:
    return get_settings().data_dir / "works" / str(work_id) / "audio"


def discard(session: Session, work: Work) -> None:
    """Forgets every part's audio, for a new analysis that cuts the Script again."""
    shutil.rmtree(audio_dir(work.id), ignore_errors=True)
    for chapter in work.chapters:
        chapter.audio = None
    work.matter_audio = {}


# ---- Parts ----


@dataclass
class Part:
    key: str  # "front", "back" or the chapter's index
    chapter: Chapter | None
    # The part's blocks, which its lines' paragraph numbers index (chorus.script).
    blocks: list[dict]
    lines: list[Line] = field(default_factory=list)  # the voiced ones, in reading order

    def audio(self, work: Work) -> dict | None:
        return self.chapter.audio if self.chapter else (work.matter_audio or {}).get(self.key)

    def set_audio(self, work: Work, record: dict) -> None:
        if self.chapter:
            self.chapter.audio = record
        else:
            work.matter_audio = {**(work.matter_audio or {}), self.key: record}

    @property
    def file_name(self) -> str:
        return f"chapter-{self.chapter.id}.flac" if self.chapter else f"{self.key}.flac"


def parts_of(session: Session, work: Work) -> list[Part]:
    """The Work's parts that have voiced lines, in reading order."""
    parts = {"front": Part("front", None, work.front_matter)}
    by_id: dict[int, Part] = {}
    for c in work.chapters:
        by_id[c.id] = parts[str(c.index)] = Part(
            str(c.index), c, c.notes_before + c.blocks + c.notes_after
        )
    parts["back"] = Part("back", None, work.back_matter)
    lines = session.scalars(
        select(Line).where(Line.work_id == work.id, Line.voiced).order_by(Line.position)
    )
    for line in lines:
        (by_id[line.chapter_id] if line.part == "chapter" else parts[line.part]).lines.append(line)
    return [p for p in parts.values() if p.lines]


def is_voiced(work: Work, part: Part) -> bool:
    """Whether every voiced line in the part has its current take."""
    from chorus.works import pack_language

    pack = get_packs()[pack_language(work.language)]
    characters = {c.id: c for c in work.characters}
    return not any(
        needs_voicing(line, plan_line(line, work, part.chapter, characters, pack), work.id)
        for line in part.lines
    )


def pause_kinds(part: Part) -> list[list[str]]:
    """The kinds of pause (keys of the pause settings) that apply after each of the part's
    lines; none after the last line unless it asks for a long pause."""
    breaks = {n for n, b in enumerate(part.blocks) if b.get("type") == "section_break"}
    out = []
    for line, following in zip(part.lines, [*part.lines[1:], None], strict=True):
        long = line.passage in LONG_PAUSE_AFTER or (
            line.passage == "epigraph" and (following is None or following.passage != "epigraph")
        )
        kinds = ["after_title"] if long else []
        if following is not None:
            # A line Chorus made (a title) stands before the part's first block.
            end = line.last_paragraph if line.last_paragraph is not None else -1
            start = following.paragraph if following.paragraph is not None else end + 1
            if any(end < n < start for n in breaks):
                kinds.append("section_break")
            elif start == end:
                kinds.append("between_lines")
            elif start == end + 1 and line.passage == following.passage == "verse":
                kinds.append("verse_line_end")
            else:
                kinds.append("new_paragraph")
        out.append(kinds)
    return out


def pauses_after(part: Part, gaps: dict[str, float]) -> list[float]:
    """The pause after each of the part's lines: the longest that applies."""
    return [max((gaps[k] for k in kinds), default=0.0) for kinds in pause_kinds(part)]


# ---- Assembling one part ----


def trim(audio: np.ndarray, sample_rate: int) -> tuple[int, int]:
    """The first and last-plus-one samples of a take with its silent ends cut off; a take that
    is silence all through keeps one sample, so it still carries its pause."""
    loud = np.flatnonzero(np.abs(audio) > 10 ** (SILENCE_DB / 20))
    if loud.size == 0:
        return 0, min(1, len(audio))
    margin = int(round(MARGIN * sample_rate))
    return max(0, int(loud[0]) - margin), min(len(audio), int(loud[-1]) + 1 + margin)


def key_of(part: Part, gaps_after: list[float]) -> str:
    made_of = [
        [line.take[k] for k in ("file", "voice_id", "emotion", "intensity", "text", "seed")]
        + [line.take.get("seconds"), gap]
        for line, gap in zip(part.lines, gaps_after, strict=True)
    ]
    return hashlib.sha256(json.dumps(made_of).encode()).hexdigest()


def assemble(work: Work, part: Part, gaps_after: list[float]) -> dict:
    """Writes the part's file and returns its record: file and length in seconds."""
    folder = lines_dir(work.id)
    paths = [folder / line.take["file"] for line in part.lines]
    rate = soundfile.info(paths[0]).samplerate
    graph, inputs, total = [], [], 0
    for n, (path, gap) in enumerate(zip(paths, gaps_after, strict=True)):
        audio, file_rate = soundfile.read(path, dtype="float32", always_2d=True)
        if file_rate != rate:
            raise JobFailed("assembly.error.sample_rate", str(path))
        start, end = trim(audio[:, 0], rate)
        pad = int(round(gap * rate))
        inputs += ["-i", str(path)]
        graph.append(
            f"[{n}:a]atrim=start_sample={start}:end_sample={end},asetpts=N/SR/TB,"
            f"apad=pad_len={pad}[c{n}]"
        )
        total += end - start + pad
    graph.append("".join(f"[c{n}]" for n in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1")

    out_dir = audio_dir(work.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / part.file_name
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        script = Path(tmp) / "graph.txt"
        script.write_text(";\n".join(graph), encoding="utf-8")
        partial = Path(tmp) / part.file_name
        command = [
            get_settings().ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            *inputs, "-filter_complex_script", str(script),
            "-ac", "1", "-ar", str(rate), "-c:a", "flac", "-sample_fmt", "s16", str(partial),
        ]  # fmt: skip
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode != 0:
            raise JobFailed("assembly.error.ffmpeg", done.stderr[-2000:], part=part.key)
        os.replace(partial, target)
    frames = soundfile.info(target).frames
    if abs(frames - total) > LENGTH_TOLERANCE * rate:
        raise JobFailed("assembly.error.length", f"{frames} != {total}", part=part.key)
    return {"file": part.file_name, "seconds": round(frames / rate, 3)}


def assemble_part(session: Session, work: Work, part: Part) -> bool:
    """Assembles the part if all of it is voiced and its audio is missing or out of date.
    Returns whether it was assembled."""
    if not is_voiced(work, part):
        return False
    gaps_after = pauses_after(part, pauses())
    key = key_of(part, gaps_after)
    current = part.audio(work)
    if current and current.get("key") == key and (audio_dir(work.id) / current["file"]).is_file():
        return False
    part.set_audio(work, {**assemble(work, part, gaps_after), "key": key})
    session.commit()
    return True


def is_assembled(work: Work, part: Part) -> bool:
    current = part.audio(work)
    return bool(
        current
        and current.get("key") == key_of(part, pauses_after(part, pauses()))
        and (audio_dir(work.id) / current["file"]).is_file()
    )


def mark_ready(session: Session, work: Work) -> None:
    """A voiced Work whose parts are all assembled is ready to listen."""
    session.refresh(work)
    if work.state != WorkState.VOICED:
        return
    parts = parts_of(session, work)
    if all(is_voiced(work, p) and is_assembled(work, p) for p in parts):
        work.state = WorkState.READY
        session.commit()


# ---- The job ----


@job("assembly", Queue.OTHER)
def assembly_job(ctx: JobContext, part: str | None = None) -> None:
    """Assembles one part, or every part of the Work that needs it."""
    session = ctx.session
    work = session.get(Work, ctx.job.work_id)
    if work is None:
        return
    chosen = [p for p in parts_of(session, work) if part is None or p.key == part]
    assembled = []
    for n, p in enumerate(chosen):
        ctx.report(stage="assembly", part=p.key, done=n, total=len(chosen))
        if assemble_part(session, work, p):
            assembled.append(p.key)
    ctx.report(stage="assembly", done=len(chosen), total=len(chosen), assembled=assembled)
    mark_ready(session, work)


def start_assembly(session: Session, work: Work, part: str | None = None) -> None:
    from chorus.jobs import enqueue

    if part is None:
        enqueue(session, "assembly", work_id=work.id)
    else:
        enqueue(session, "assembly", work_id=work.id, part=part)
