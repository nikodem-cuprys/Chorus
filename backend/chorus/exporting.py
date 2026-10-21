"""MP3 and M4B export: a Work's Audio drama as ordinary files in the host's exports folder
(docs/spec/03-pipeline.md, MP3 and M4B export).

**Where:** one sub-folder per Work in the exports folder, named after the Work with its id
("Pride and Prejudice (12)"), so the files survive deleting the Work. The M4B is one file named
after the Work; the MP3s are one file per part, numbered, in an `MP3` folder inside it. A new
export of the same kind replaces the one before it.

**From what:** the assembled parts (chorus.assembly) in reading order: the front matter with the
Work title, each chapter, the back matter. An export of a Work that is not ready to listen is
refused.

| | M4B | MP3 |
|---|---|---|
| Audio | AAC, mono, 64 kbps | mono, 96 kbps |
| Chapters | one marker per part, from the assembled lengths | one file per part |
| Tags | title, author, cover | title, author, album, track number, cover |

**Cover:** the Source's cover as a JPEG, else a generated title card with the Work's title and
authors.

**Written aside:** the files are made in a hidden folder next to where they go and moved into
place when all of them are done, so a failed export leaves the previous one as it was.
"""

import os
import re
import subprocess
import tempfile
import textwrap
import zipfile
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus.assembly import Part, audio_dir, is_assembled, is_voiced, parts_of
from chorus.config import get_settings
from chorus.jobs import JobContext, JobFailed, Pace, job
from chorus.models import Export, Queue, Work, WorkState

KINDS = ("m4b", "mp3")
MP3_FOLDER = "MP3"
COVER_SIZE = 1400  # pixels, square; what audiobook players show well
# Part names written into the files, for listeners. English until Language packs carry them
# (export lines, milestone 8).
FRONT_LABEL, BACK_LABEL, CHAPTER_LABEL = "Front matter", "Back matter", "Chapter {index}"
TITLE_CARD_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
)

Report = Callable[..., None]


def exports_dir() -> Path:
    return get_settings().exports_dir


# ---- Names ----


def file_name(text: str, limit: int = 80) -> str:
    """Text made safe as a file or folder name on Linux, Windows and macOS hosts."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = " ".join(text.split())[:limit].rstrip(" .")
    return text or "Untitled"


def work_folder(work: Work) -> str:
    return f"{file_name(work.title or 'Untitled')} ({work.id})"


def part_label(work: Work, part: Part) -> str:
    """A chapter's title (from the table of contents, else its title line), else its number."""
    if part.chapter is None:
        return FRONT_LABEL if part.key == "front" else BACK_LABEL
    if part.chapter.title:
        return part.chapter.title
    heading = next((ln.text for ln in part.lines if ln.passage == "chapter_title"), None)
    return " ".join(heading.split()) if heading else CHAPTER_LABEL.format(index=part.chapter.index)


def authors_text(work: Work) -> str:
    return ", ".join(work.authors or [])


# ---- The cover ----


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in TITLE_CARD_FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def title_card(work: Work) -> Image.Image:
    """A plain square card with the Work's title and authors, for a Source with no cover."""
    image = Image.new("RGB", (COVER_SIZE, COVER_SIZE), (36, 40, 56))
    draw = ImageDraw.Draw(image)
    title_font, author_font = _font(96), _font(56)
    title = textwrap.wrap(work.title or "Untitled", width=20)[:6]
    y = COVER_SIZE * 0.3
    for row in title:
        draw.text((COVER_SIZE / 2, y), row, font=title_font, fill=(240, 236, 226), anchor="mt")
        y += 120
    if work.authors:
        y += 60
        for row in textwrap.wrap(authors_text(work), width=34)[:3]:
            draw.text((COVER_SIZE / 2, y), row, font=author_font, fill=(200, 192, 170), anchor="mt")
            y += 72
    return image


def write_cover(work: Work, target: Path) -> Path:
    """The Source's cover (as a JPEG no larger than COVER_SIZE), else a title card."""
    from chorus.works import work_dir

    image = None
    if work.cover_file:
        try:
            with Image.open(work_dir(work.id) / work.cover_file) as source:
                image = source.convert("RGB")
            image.thumbnail((COVER_SIZE, COVER_SIZE))
        except OSError:
            image = None  # an unreadable cover: the title card instead
    (image or title_card(work)).save(target, "JPEG", quality=90)
    return target


# ---- ffmpeg ----


def _metadata(value: str) -> str:
    """A value for an ffmetadata file."""
    return re.sub(r"([=;#\\\n])", r"\\\1", value)


def run_ffmpeg(arguments: list[str], seconds: float, progress: Callable[[float], None]) -> None:
    """Runs ffmpeg, telling `progress` the share of `seconds` written so far. Whatever
    `progress` raises (a pause, chorus.jobs) stops ffmpeg and is raised again."""
    command = [
        get_settings().ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-progress", "pipe:1", "-nostats", *arguments,
    ]  # fmt: skip
    with tempfile.TemporaryFile("w+", encoding="utf-8") as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True)
        try:
            for row in process.stdout:
                if row.startswith("out_time_us=") and seconds > 0:
                    try:
                        written = int(row.split("=", 1)[1]) / 1e6
                    except ValueError:
                        continue  # "N/A" before the first packet
                    progress(min(1.0, written / seconds))
        except BaseException:
            process.kill()
            process.wait()
            raise
        if process.wait() != 0:
            errors.seek(0)
            raise JobFailed("export.error.ffmpeg", errors.read()[-2000:])


def write_m4b(
    work: Work, parts: list[Part], target: Path, cover: Path, progress: Callable[[float], None]
) -> None:
    folder = target.parent
    sources = [audio_dir(work.id) / p.audio(work)["file"] for p in parts]
    listing = folder / "parts.txt"
    listing.write_text(
        "".join("file '{}'\n".format(str(s).replace("'", "'\\''")) for s in sources),
        encoding="utf-8",
    )
    meta = [
        ";FFMETADATA1",
        f"title={_metadata(work.title or '')}",
        f"album={_metadata(work.title or '')}",
        f"artist={_metadata(authors_text(work))}",
        f"album_artist={_metadata(authors_text(work))}",
        "genre=Audiobook",
    ]
    start = 0
    for part in parts:
        end = start + int(round(part.audio(work)["seconds"] * 1000))
        meta += [
            "[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={end}",
            f"title={_metadata(part_label(work, part))}",
        ]  # fmt: skip
        start = end
    metadata = folder / "metadata.txt"
    metadata.write_text("\n".join(meta) + "\n", encoding="utf-8")
    try:
        run_ffmpeg(
            [
                "-f", "concat", "-safe", "0", "-i", str(listing),
                "-i", str(metadata), "-i", str(cover),
                "-map", "0:a", "-map", "2:v", "-map_metadata", "1", "-map_chapters", "1",
                "-c:a", "aac", "-b:a", "64k", "-ac", "1",
                "-c:v", "copy", "-disposition:v:0", "attached_pic",
                "-movflags", "+faststart", "-f", "mp4", str(target),
            ],
            start / 1000,
            progress,
        )  # fmt: skip
    finally:
        listing.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)


def write_mp3s(
    work: Work, parts: list[Part], folder: Path, cover: Path, progress: Callable[[float], None]
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    total = sum(p.audio(work)["seconds"] for p in parts)
    width = max(2, len(str(len(parts))))
    written, done = [], 0.0
    for number, part in enumerate(parts, start=1):
        label = part_label(work, part)
        target = folder / f"{number:0{width}d} - {file_name(label)}.mp3"
        seconds = part.audio(work)["seconds"]
        run_ffmpeg(
            [
                "-i", str(audio_dir(work.id) / part.audio(work)["file"]), "-i", str(cover),
                "-map", "0:a", "-map", "1:v",
                "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "1",
                "-c:v", "copy", "-disposition:v:0", "attached_pic",
                "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)",
                "-id3v2_version", "3",
                "-metadata", f"title={label}",
                "-metadata", f"artist={authors_text(work)}",
                "-metadata", f"album_artist={authors_text(work)}",
                "-metadata", f"album={work.title or ''}",
                "-metadata", f"track={number}/{len(parts)}",
                str(target),
            ],
            seconds,
            lambda share, done=done, seconds=seconds: progress((done + share * seconds) / total),
        )  # fmt: skip
        done += seconds
        written.append(target)
    return written


# ---- Records ----


def remove_files(export: Export) -> None:
    """Deletes an export's files, and its folders once they are empty."""
    root = exports_dir()
    folders = set()
    for name in export.files:
        path = root / name
        path.unlink(missing_ok=True)
        folders.update(p for p in path.parents if root in p.parents)
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        try:
            folder.rmdir()
        except OSError:
            pass  # not empty: other files are in it


def delete_export(session: Session, export: Export) -> None:
    remove_files(export)
    session.delete(export)
    session.commit()


def ready_parts(session: Session, work: Work) -> list[Part]:
    """The parts to export, or JobFailed when the Work is not ready to listen."""
    parts = parts_of(session, work)
    if (
        work.state != WorkState.READY
        or not parts
        or not all(is_voiced(work, p) and is_assembled(work, p) for p in parts)
    ):
        raise JobFailed("export.error.not_ready")
    return parts


def export_work(
    session: Session,
    work: Work,
    kind: str,
    report: Report,
    check: Callable[[], None] | None = None,
) -> Export:
    """Writes the export's files and records it, replacing the Work's export of that kind.
    `check` is called as ffmpeg writes; a paused export starts over when resumed."""
    parts = ready_parts(session, work)
    folder = exports_dir() / work_folder(work)
    folder.mkdir(parents=True, exist_ok=True)
    pace = Pace()

    def progress(share: float) -> None:
        if check:
            check()
        report(
            stage="export",
            kind=kind,
            percent=round(100 * share),
            seconds_left=pace.seconds_left(share, 1.0),
        )

    progress(0)
    with tempfile.TemporaryDirectory(prefix=".export-", dir=folder) as tmp:
        staging = Path(tmp)
        cover = write_cover(work, staging / "cover.jpg")
        if kind == "m4b":
            written = [staging / f"{file_name(work.title or 'Untitled')}.m4b"]
            write_m4b(work, parts, written[0], cover, progress)
        else:
            written = write_mp3s(work, parts, staging / MP3_FOLDER, cover, progress)
        cover.unlink()

        for old in session.scalars(
            select(Export).where(Export.work_id == work.id, Export.kind == kind)
        ):
            remove_files(old)
            session.delete(old)
        files = []
        for path in written:
            final = folder / path.relative_to(staging)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, final)
            files.append(final.relative_to(exports_dir()).as_posix())
    row = Export(
        work_id=work.id,
        kind=kind,
        folder=work_folder(work),
        files=files,
        parts=[p.key for p in parts],
        seconds=round(sum(p.audio(work)["seconds"] for p in parts), 3),
    )
    session.add(row)
    session.commit()
    report(stage="export", kind=kind, percent=100, seconds_left=0)
    return row


# ---- The job ----


@job("export", Queue.OTHER)
def export_job(ctx: JobContext, export_kind: str) -> None:
    work = ctx.session.get(Work, ctx.job.work_id)
    if work is None:
        return
    export_work(ctx.session, work, export_kind, ctx.report, check=ctx.check)


def start_export(session: Session, work: Work, kind: str) -> None:
    """Queues an export; JobFailed when the Work is not ready to listen."""
    from chorus.jobs import enqueue

    ready_parts(session, work)
    enqueue(session, "export", work_id=work.id, export_kind=kind)


def download_name(export: Export) -> str:
    """What a download is called: the M4B's own name, or the MP3 folder's as a zip."""
    if export.kind == "m4b":
        return Path(export.files[0]).name
    return f"{export.folder}.zip"


def zip_mp3s(export: Export) -> Path:
    """The MP3 files in one uncompressed zip, in a temporary file the caller deletes."""
    handle, name = tempfile.mkstemp(suffix=".zip")
    os.close(handle)
    with zipfile.ZipFile(name, "w", zipfile.ZIP_STORED) as archive:
        for file in export.files:
            archive.write(exports_dir() / file, Path(file).name)
    return Path(name)
