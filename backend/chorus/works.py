"""Works: starting an import from an upload, the import job, and what the API sends.

Each Work has a folder on the data volume (`works/<id>/`) holding the stored copy of its
Source and its cover.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path, PurePath

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, object_session

from chorus.config import get_settings
from chorus.importing import ImportedWork, ImportRejected, base_language, language
from chorus.importing.calibre import convert_to_epub
from chorus.importing.epub import read_epub
from chorus.importing.pdf import read_pdf
from chorus.importing.txt import read_txt
from chorus.jobs import JobContext, enqueue, job
from chorus.languages import ChapterHeadings, get_packs
from chorus.models import Chapter, Line, Queue, Voice, Work, WorkState
from chorus.script import build_script

# Source kinds Chorus reads itself; any other is named by its extension ("mobi", "docx") and
# goes through Calibre.
SOURCE_KINDS = {".epub": "epub", ".txt": "txt", ".pdf": "pdf"}

# The pack whose rules are used when a Work's language has none.
FALLBACK_LANGUAGE = "en"


def work_dir(work_id: int) -> Path:
    return get_settings().data_dir / "works" / str(work_id)


def pack_language(code: str | None) -> str:
    """The Language pack a Work with this language uses."""
    return code if code in get_packs() else FALLBACK_LANGUAGE


def start_import(session: Session, filename: str, data: bytes) -> Work:
    """Stores the upload as the Work's Source and puts the import job on the queue."""
    name = PurePath(filename).name or "source"
    suffix = PurePath(name).suffix.lower()
    kind = SOURCE_KINDS.get(suffix) or suffix.lstrip(".")[:20] or "other"
    work = Work(
        title=PurePath(name).stem,
        source_kind=kind,
        source_name=name,
        source_hash=hashlib.sha256(data).hexdigest(),
        state=WorkState.IMPORTING,
    )
    session.add(work)
    session.commit()

    folder = work_dir(work.id)
    folder.mkdir(parents=True, exist_ok=True)
    work.source_file = f"source{PurePath(name).suffix.lower()}"
    (folder / work.source_file).write_bytes(data)
    session.commit()
    enqueue(session, "import", work_id=work.id)
    session.refresh(work)
    return work


@job("import", Queue.OTHER)
def import_work(ctx: JobContext) -> None:
    session = ctx.session
    work = session.get(Work, ctx.job.work_id)
    try:
        ctx.report(stage="reading")
        data = (work_dir(work.id) / work.source_file).read_bytes()

        # The heading patterns of the stated language's pack, else English's: the detector
        # can only run once the text is out.
        def headings_for(code: str | None) -> ChapterHeadings | None:
            return get_packs()[pack_language(code)].chapter_headings

        if work.source_kind == "epub":
            imported = read_epub(data, headings_for)
        elif work.source_kind == "txt":
            imported = read_txt(data, headings_for, work.source_name)
        elif work.source_kind == "pdf":
            imported = read_pdf(
                data,
                lambda code: get_packs()[pack_language(code)],
                work.source_name,
                lambda done, total: ctx.report(stage="reading", done=done, total=total),
            )
        else:
            ctx.report(stage="converting")
            epub = convert_to_epub(data, PurePath(work.source_name).suffix)
            imported = read_epub(epub, headings_for)
        ctx.report(stage="saving")
        _save(session, work, imported)
        if get_settings().analyse_after_import:
            start_analysis(session, work)
    except Exception as exc:
        session.rollback()
        work = session.get(Work, ctx.job.work_id)
        work.state = WorkState.FAILED
        if isinstance(exc, ImportRejected):
            work.error = exc.message()
        else:
            work.error = {"key": "import.error.unexpected", "params": {"detail": repr(exc)}}
        session.commit()
        raise


def _save(session: Session, work: Work, imported: ImportedWork) -> None:
    session.execute(delete(Line).where(Line.work_id == work.id))
    session.execute(delete(Chapter).where(Chapter.work_id == work.id))
    work.title = imported.title or work.title
    work.authors = imported.authors
    if imported.language:
        work.language, work.language_source = imported.language, "metadata"
    else:
        sample = "\n".join(c.text for c in imported.chapters)
        work.language = base_language(language.detect(sample))
        work.language_source = "detector" if work.language else None
    work.is_ao3 = imported.is_ao3
    work.meta = imported.metadata
    work.warnings = imported.warnings
    work.front_matter = [b.to_dict() for b in imported.front_matter]
    work.back_matter = [b.to_dict() for b in imported.back_matter]
    folder = work_dir(work.id)
    for old in folder.glob("cover.*"):
        old.unlink()
    work.cover_file = None
    if imported.cover:
        work.cover_file = f"cover.{imported.cover_type}"
        (folder / work.cover_file).write_bytes(imported.cover)
    for index, chapter in enumerate(imported.chapters, start=1):
        session.add(
            Chapter(
                work_id=work.id,
                index=index,
                title=chapter.title,
                content_hash=chapter.content_hash,
                notes_before=[b.to_dict() for b in chapter.notes_before],
                blocks=[b.to_dict() for b in chapter.blocks],
                notes_after=[b.to_dict() for b in chapter.notes_after],
            )
        )
    session.flush()
    session.refresh(work, ["chapters"])
    build_script(session, work, get_packs()[pack_language(work.language)])
    work.state = WorkState.IMPORTED
    work.error = None
    work.imported_at = datetime.now(UTC)
    session.commit()


def start_analysis(session: Session, work: Work) -> None:
    """Queues analysis on the GPU queue. An analysed Work is analysed again from the start, with
    its Script cut again; a stopped analysis continues where it stopped (chorus.analysis)."""
    enqueue(session, "analysis", work_id=work.id)


def set_language(session: Session, work: Work, code: str) -> None:
    """Chosen by the user. Nothing runs by itself, so the Script keeps the quotation marks of
    the language it was cut with until the next analysis, which cuts it again."""
    work.language = code
    work.language_source = "user"
    session.commit()


# ---- What the API sends ----


def _words(blocks: list[dict]) -> int:
    return sum(len("".join(s["text"] for s in b["spans"]).split()) for b in blocks)


def summary(work: Work) -> dict:
    return {
        "id": work.id,
        "title": work.title,
        "authors": work.authors,
        "state": work.state.value,
        "error": work.error,
        "language": work.language,
        "created_at": work.created_at.isoformat() if work.created_at else None,
    }


def detail(work: Work) -> dict:
    return {
        **summary(work),
        "language_source": work.language_source,
        # A Work in a language without a pack is handled with the English one.
        "has_language_pack": work.language in get_packs(),
        "source": {
            "kind": work.source_kind,
            "name": work.source_name,
            "hash": work.source_hash,
            "imported_at": work.imported_at.isoformat() if work.imported_at else None,
        },
        "is_ao3": work.is_ao3,
        "metadata": work.meta,
        "warnings": work.warnings,
        "cover_url": f"/api/works/{work.id}/cover" if work.cover_file else None,
        "front_matter_blocks": len(work.front_matter),
        "back_matter_blocks": len(work.back_matter),
        "chapters": [
            {
                "index": c.index,
                "title": c.title,
                "words": _words(c.blocks),
                "narrating_character_id": c.narrating_character_id,
            }
            for c in work.chapters
        ],
        "characters": _characters(work),
        "narrator_voice": _voice_names(object_session(work)).get(work.narrator_voice_id),
    }


def _voice_names(session: Session) -> dict[int, str]:
    return dict(session.execute(select(Voice.id, Voice.name)).all())


def _characters(work: Work) -> list[dict]:
    """The Character list with each Character's number of lines, most lines first."""
    session = object_session(work)
    counts = dict(
        session.execute(
            select(Line.character_id, func.count())
            .where(Line.work_id == work.id, Line.character_id.is_not(None))
            .group_by(Line.character_id)
        ).all()
    )
    names = _voice_names(session)
    rows = [
        {**c.to_dict(), "lines": counts.get(c.id, 0), "voice": names.get(c.voice_id)}
        for c in work.characters
    ]
    return sorted(rows, key=lambda row: -row["lines"])


def chapter_detail(chapter: Chapter, lines: list[Line]) -> dict:
    return {
        "index": chapter.index,
        "title": chapter.title,
        "notes_before": chapter.notes_before,
        "blocks": chapter.blocks,
        "notes_after": chapter.notes_after,
        "lines": [line.to_dict() for line in lines],
    }
