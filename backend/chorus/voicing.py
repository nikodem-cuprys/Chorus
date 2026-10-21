"""Voicing: one FLAC file per voiced line, with Chatterbox 500M (docs/spec/03-pipeline.md, Voicing).

**What each line is voiced with** (`plan_line`):
- **Voice:** a Character's line, the Character's Voice; the Narrator's lines, the chapter's
  narration Voice (the Narrating Character's in a first-person chapter, chorus.casting); a line
  whose Speaker is Unknown, the Narrator's Voice. Each Voice speaks from its neutral clip.
- **Settings:** a Character's (or Unknown) line takes its Emotion and intensity from the voice
  model's Emotion settings in the Language pack; the Narrator and letters are always neutral;
  thoughts are never strong; `exaggeration` never goes above 0.9.
- **Seed:** given the first time a line is voiced and kept, so the same line voices the same way.
- **Long lines** are split into sentences with the pack's sentence rules; each is voiced with the
  line's Voice, settings and seed, and they are joined with the `between_sentences` pause. Verse
  is split at its line ends too, which take the `verse_line_end` pause.

**Order and batches:** reading order, a chapter (or the front or back matter) at a time; the
voice model takes each chapter as one batch, its two halves on the card in turn.

**Saved as it goes:** a line's file is written and its take committed as soon as its audio is
done. A line needs voicing while it has no take, or its take was made with another Voice,
Emotion, intensity or text; so a stopped job, started again, voices only what is missing.

**One child process per job:** `python -m chorus.voicing <job id>` loads Chatterbox with
`from_local` from the models volume, voices every line that needs it, and exits. Each part is
queued for assembly (chorus.assembly) as soon as its lines are voiced, and the whole Work once
the job ends.
"""

import json
import random
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

import numpy as np
import soundfile
from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus import firstrun
from chorus.casting import narration_voice
from chorus.config import get_settings
from chorus.db import get_sessionmaker
from chorus.jobs import CANCEL, PAUSE, STOPPED_EXIT, JobContext, JobFailed, Pace, Stopped, job
from chorus.languages import MAX_EXAGGERATION, LanguagePack, get_packs
from chorus.models import Chapter, Character, Job, Line, Queue, Voice, Work, WorkState
from chorus.voice_model import Chatterbox, Speech, VoiceModel

PAUSES_FILE = Path(__file__).resolve().parent / "pauses.json"
NEUTRAL = ("neutral", "normal")
# A line with no letters or digits in it ("* * *", a lone dash) is this much silence: the voice
# model, given no words, says a sentence of its own.
SILENT_LINE_SECONDS = 0.25
# The share of a sentence's voicing time spent in T3 (the rest in S3Gen), for progress and the
# time left: 500 s of 771 s voicing Metamorphosis' chapter on the GTX 1050 Ti (M1 ticket 15).
T3_SHARE = 0.65


def pauses() -> dict[str, float]:
    """The pause settings, read each time so a change applies to the next run."""
    data = json.loads(PAUSES_FILE.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in data.items() if k != "note"}


def lines_dir(work_id: int) -> Path:
    return get_settings().data_dir / "works" / str(work_id) / "lines"


def discard_audio(work_id: int) -> None:
    """Removes a Work's line audio, for a new analysis that cuts the Script again."""
    shutil.rmtree(lines_dir(work_id), ignore_errors=True)


def forget_audio(session: Session, work: Work) -> None:
    """Throws away the Work's audio at the user's request: every line's take and seed, and the
    assembled parts. Voicing it again starts from nothing, with new seeds."""
    from chorus.assembly import discard

    discard_audio(work.id)
    discard(session, work)
    for line in session.scalars(select(Line).where(Line.work_id == work.id)):
        line.take, line.seed = None, None
    if work.state in (WorkState.VOICING, WorkState.VOICED, WorkState.READY):
        work.state = WorkState.ANALYSED
    session.commit()


# ---- What a line is voiced with ----


@dataclass(frozen=True)
class LinePlan:
    voice_id: int
    # The Emotion and intensity the take uses (neutral, normal for the Narrator and letters).
    emotion: str
    intensity: str
    exaggeration: float
    cfg_weight: float
    text: str

    def matches(self, take: dict | None) -> bool:
        return take is not None and all(
            take.get(k) == v
            for k, v in (
                ("voice_id", self.voice_id),
                ("emotion", self.emotion),
                ("intensity", self.intensity),
                ("text", self.text),
            )
        )


def plan_line(
    line: Line,
    work: Work,
    chapter: Chapter | None,
    characters: dict[int, Character],
    pack: LanguagePack,
) -> LinePlan:
    character = characters.get(line.character_id) if line.character_id is not None else None
    if line.speaker == "character" and character is not None and character.voice_id is not None:
        voice_id = character.voice_id
    elif line.speaker in ("character", "unknown"):
        voice_id = work.narrator_voice_id
    else:
        voice_id = narration_voice(work, chapter, characters)

    neutral = line.speaker not in ("character", "unknown") or line.passage == "letter"
    emotion, intensity = NEUTRAL if neutral else (line.emotion or "neutral", line.intensity)
    if intensity != "strong" or line.kind == "thought":
        intensity = "normal"
    setting = pack.voice_model.emotions[emotion][intensity]
    return LinePlan(
        voice_id=voice_id,
        emotion=emotion,
        intensity=intensity,
        exaggeration=min(setting.exaggeration, MAX_EXAGGERATION),
        cfg_weight=setting.cfg_weight,
        text=" ".join(line.text.split()),
    )


def needs_voicing(line: Line, plan: LinePlan, work_id: int) -> bool:
    if not plan.matches(line.take):
        return True
    return not (lines_dir(work_id) / line.take["file"]).is_file()


def sentences(text: str, pack: LanguagePack) -> list[str]:
    """The sentences that have something to say."""
    return [s for s in pack.split_sentences(text) if any(c.isalnum() for c in s)]


def pieces(line: Line, pack: LanguagePack, gaps: dict[str, float]) -> list[tuple[str, float]]:
    """What the line says, a sentence at a time, each with the pause before the next one:
    `between_sentences`, or `verse_line_end` where a line of verse ends."""
    if line.passage == "verse":
        rows = [r for r in line.text.split("\n") if r.strip()]
    else:
        rows = [line.text]
    out: list[tuple[str, float]] = []
    for row in rows:
        said = sentences(row, pack)
        out += [(s, gaps["between_sentences"]) for s in said[:-1]]
        out += [(s, gaps["verse_line_end"]) for s in said[-1:]]
    return out


def join(parts: list[np.ndarray], gaps: list[float], sample_rate: int) -> np.ndarray:
    """The parts with each one's pause after it, except the last's."""
    out: list[np.ndarray] = []
    for n, part in enumerate(parts):
        if n:
            out.append(np.zeros(int(round(gaps[n - 1] * sample_rate)), dtype=np.float32))
        out.append(part.astype(np.float32))
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


# ---- The stage ----

Report = Callable[..., None]


def _words(text: str) -> int:
    return len(text.split())


def part_key(line: Line, chapters: dict[int, Chapter]) -> str:
    """The part a line is in, as chorus.assembly names it: front, back or the chapter's index."""
    return str(chapters[line.chapter_id].index) if line.part == "chapter" else line.part


def voice_work(
    session: Session,
    work: Work,
    model: VoiceModel,
    report: Report,
    part_voiced: Callable[[str], None] | None = None,
    check: Callable[[], None] | None = None,
) -> int:
    """Voices every line of the Work that needs it, chapter by chapter in reading order,
    committing each line as soon as its file is written; `part_voiced` is told each part
    (chorus.assembly) whose lines were voiced, and `check` is called before each sentence in
    each half of the model, so a pause stops within a sentence. Returns the number of lines
    voiced.

    Progress is counted in words, each sentence's words split between T3 and S3Gen by the time
    each half takes (`T3_SHARE`): lines voiced before this run count as done, and the time
    left comes from this run's speed."""
    from chorus.works import pack_language

    pack = get_packs()[pack_language(work.language)]
    gaps = pauses()
    voices = {v.id: v for v in session.scalars(select(Voice))}
    characters = {c.id: c for c in work.characters}
    chapters = {c.id: c for c in work.chapters}
    folder = lines_dir(work.id)
    folder.mkdir(parents=True, exist_ok=True)

    lines = [
        line
        for line in session.scalars(
            select(Line).where(Line.work_id == work.id).order_by(Line.position)
        )
        if line.voiced
    ]
    plans = {
        line.id: plan_line(line, work, chapters.get(line.chapter_id), characters, pack)
        for line in lines
    }
    todo = [line for line in lines if needs_voicing(line, plans[line.id], work.id)]
    parts = [list(group) for _, group in groupby(todo, key=lambda ln: (ln.part, ln.chapter_id))]
    # Every part of the Work, so progress says "part 3 of 12" also when only 3 to 12 are left.
    every_part = list(dict.fromkeys(part_key(line, chapters) for line in lines))
    done = len(lines) - len(todo)
    words_total = sum(_words(line.text) for line in lines) or 1
    words_done = float(words_total - sum(_words(line.text) for line in todo))
    pace = Pace()
    reached = words_done  # where the last report was, in words

    def progress(part: int, words: float | None = None) -> None:
        nonlocal reached
        if words is not None:
            reached = words
        share = reached / words_total
        key = part_key(parts[part - 1][0], chapters) if parts else None
        report(
            stage="voicing",
            part=every_part.index(key) + 1 if key else len(every_part),
            parts=len(every_part),
            chapter=key,
            done=done,
            total=len(lines),
            percent=min(100, round(100 * share)),
            seconds_left=pace.seconds_left(share, 1.0),
        )

    def save(line: Line, plan: LinePlan, audio: np.ndarray) -> None:
        nonlocal done
        name = f"{line.id}.flac"
        soundfile.write(folder / name, audio, model.sample_rate, subtype="PCM_16")
        line.take = {
            "file": name,
            "voice_id": plan.voice_id,
            "emotion": plan.emotion,
            "intensity": plan.intensity,
            "text": plan.text,
            "seed": line.seed,
            "seconds": round(len(audio) / model.sample_rate, 3),
        }
        session.commit()
        done += 1

    for number, part in enumerate(parts, start=1):
        progress(number)
        batch: list[Speech] = []
        owners: list[Line] = []
        line_gaps: dict[int, list[float]] = {}
        for line in part:
            if line.seed is None:
                line.seed = random.randrange(2**31)
            plan = plans[line.id]
            reference = voices[plan.voice_id]
            clip = pack.voice(reference.name).clips["neutral"]
            said = pieces(line, pack, gaps)
            if not said:
                save(line, plan, np.zeros(int(SILENT_LINE_SECONDS * model.sample_rate)))
                continue
            line_gaps[line.id] = [gap for _, gap in said]
            for text, _ in said:
                batch.append(Speech(text, clip, plan.exaggeration, plan.cfg_weight, line.seed))
                owners.append(line)
        session.commit()  # the seeds, before any audio exists
        if not batch:
            words_done += sum(_words(line.text) for line in part)
            progress(number, words_done)
            if part_voiced:
                part_voiced(part_key(part[0], chapters))
            continue

        # Words before each piece of the batch, for progress inside a half.
        before = [0]
        for speech in batch:
            before.append(before[-1] + _words(speech.text))

        def step(half: str, index: int, before=before, number=number, base=words_done) -> None:
            if check:
                check()
            if half == "t3":
                inside = T3_SHARE * before[index]
            else:
                inside = T3_SHARE * before[-1] + (1 - T3_SHARE) * before[index]
            progress(number, base + inside)

        started = time.monotonic()
        heard: dict[int, list[np.ndarray]] = {}
        seconds = 0.0
        for (_, audio), line in zip(model.speak(batch, step), owners, strict=True):
            heard.setdefault(line.id, []).append(audio)
            if len(heard[line.id]) == len(line_gaps[line.id]):
                joined = join(heard.pop(line.id), line_gaps[line.id], model.sample_rate)
                seconds += len(joined) / model.sample_rate
                save(line, plans[line.id], joined)
                progress(number)
        took = time.monotonic() - started
        print(
            f"voicing: work {work.id} part {number}/{len(parts)}: {len(part)} lines, "
            f"{seconds:.1f} s of audio in {took:.1f} s ({took / max(seconds, 0.001):.2f}x)",
            flush=True,
        )
        words_done += sum(_words(line.text) for line in part)
        progress(number, words_done)
        if part_voiced:
            part_voiced(part_key(part[0], chapters))
    progress(len(parts))
    return len(todo)


# ---- The job and its child process ----


@job("voicing", Queue.GPU)
def voicing_job(ctx: JobContext) -> None:
    session = ctx.session
    work = session.get(Work, ctx.job.work_id)
    work.state = WorkState.VOICING
    work.error = None
    session.commit()
    returncode = run_child(ctx.job.id)
    session.expire_all()
    if returncode == STOPPED_EXIT:
        request = ctx.requested() or PAUSE
        # Cancelled, the Work is back to analysed: starting voicing again voices what is
        # missing. Paused, it stays voicing, and the job shows as paused.
        if request == CANCEL:
            work.state = WorkState.ANALYSED
        session.commit()
        raise Stopped(request)
    if returncode != 0:
        error = ctx.job.error or {
            "key": "voicing.error.unexpected",
            "params": {"detail": f"exit code {returncode}"},
        }
        work.state = WorkState.FAILED
        work.error = error
        session.commit()
        failed = JobFailed(error["key"])
        failed.params = error["params"]
        raise failed
    work.state = WorkState.VOICED
    session.commit()
    from chorus.assembly import start_assembly

    start_assembly(session, work)


def start_voicing(session: Session, work: Work) -> None:
    from chorus.jobs import enqueue

    enqueue(session, "voicing", work_id=work.id)


def run_child(job_id: int) -> int:
    """The stage in its own process, so the card's memory is free when it ends."""
    return subprocess.run([sys.executable, "-m", "chorus.voicing", str(job_id)]).returncode


def main(job_id: int) -> int:
    from chorus.assembly import start_assembly

    with get_sessionmaker()() as session:
        row = session.get(Job, job_id)
        ctx = JobContext(session, row)
        work = session.get(Work, row.work_id)
        try:
            with Chatterbox(firstrun.chatterbox_dir()) as model:
                voice_work(
                    session,
                    work,
                    model,
                    ctx.report,
                    part_voiced=lambda part: start_assembly(session, work, part),
                    check=ctx.check,
                )
        except Stopped:
            session.rollback()
            return STOPPED_EXIT
        except Exception as exc:
            session.rollback()
            row.error = {"key": "voicing.error.unexpected", "params": {"detail": repr(exc)}}
            session.commit()
            raise
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
