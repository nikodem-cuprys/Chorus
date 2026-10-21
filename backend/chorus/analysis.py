"""Analysis: the Character list, then a Speaker, kind, Emotion and intensity for every quoted line
(docs/spec/03-pipeline.md, Analysis steps 3, 4 and 7). Approach B, with the Character list built
as a delta (M1 ticket 03).

**Chunks** are whole paragraphs of about `CHUNK_WORDS` words, never across a chapter (or the front
or back matter), made of the lines that will be voiced. Both passes go over the same chunks.

**Character pass:** chunk by chunk, the model sees the list so far and returns only new
Characters and new aliases; `merge` checks and merges them. For each chunk it also says whether
the narration is first or third person and who narrates; each chapter takes the majority answer
of its chunks as its Narrating Character, added to the list if missing.

**Attribution pass:** chunk by chunk, with the whole list (never trimmed) and the last
`TAIL_WORDS` words of the previous chunk, every quoted line gets a Speaker, a kind, an Emotion
and an intensity. Other voiced lines are the Narrator's. Afterwards Characters with no lines,
who narrate nothing, leave the list.

**Saved as it goes:** every finished chunk is committed together with `Work.analysis`, which says
how far the stage got, so a stopped analysis continues with the next chunk. A new analysis of an
analysed Work starts over: the Script is cut again (with the Work's current language) and the list
emptied.

**One child process per analysis:** the GPU job runs `python -m chorus.analysis <job id>`, which
starts llama.cpp's server, runs every request, stops it and exits, so the card is free afterwards.
"""

import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from chorus import firstrun
from chorus.analysis_model import AnalysisModel, LlamaServer, ModelUnavailable
from chorus.casting import cast_work
from chorus.config import get_settings
from chorus.db import get_sessionmaker
from chorus.jobs import CANCEL, PAUSE, STOPPED_EXIT, JobContext, JobFailed, Pace, Stopped, job
from chorus.languages import NameRules, get_packs
from chorus.models import Chapter, Character, Job, Line, Queue, Work, WorkState
from chorus.script import build_script

CHUNK_WORDS = 900
TAIL_WORDS = 150
CAST_MAX_TOKENS = 1500
ATTRIBUTION_MAX_TOKENS = 6000

GENDERS = ("female", "male", "unknown")
# As the model sees them; stored with an underscore ("young_adult"), like a Voice's.
AGES = ("child", "young adult", "adult", "elderly", "unknown")
KINDS = ("speech", "thought", "written")
EMOTIONS = (
    "neutral", "happy", "excited", "amused", "angry", "sad", "afraid", "anxious", "surprised",
)  # fmt: skip
INTENSITIES = ("normal", "strong")
NARRATOR, UNKNOWN = "Narrator", "Unknown"

# The attribution pass takes about three times as long per chunk as the Character pass.
ATTRIBUTION_WEIGHT = 3


# ---- Chunks ----


@dataclass
class Chunk:
    # "front", "back", or the chapter's id as text: the part whose Narrating Character it shares.
    part: str
    lines: list[Line]

    def render(self, numbered: bool = True) -> tuple[str, dict[int, Line]]:
        """The chunk's text, one paragraph per line of text. With `numbered`, each quotation is
        prefixed with its number in the chunk ("[12] “...”"); returns the quotations by number."""
        out: list[str] = []
        quotes: dict[int, Line] = {}
        previous: Line | None = None
        for n, line in enumerate(self.lines, start=1):
            if previous is not None and _new_paragraph(previous, line):
                out.append("\n\n")
            elif previous is not None:
                out.append(" ")
            if numbered and line.kind != "narration":
                out.append(f"[{n}] ")
                quotes[n] = line
            out.append(" ".join(line.text.split()))
            previous = line
        return "".join(out), quotes

    @property
    def text(self) -> str:
        return self.render(numbered=False)[0]


def _new_paragraph(previous: Line, line: Line) -> bool:
    return line.paragraph is None or line.paragraph != previous.last_paragraph


def _part_key(line: Line) -> str:
    return line.part if line.chapter_id is None else str(line.chapter_id)


def _words(text: str) -> int:
    return len(text.split())


def analysed(line: Line) -> bool:
    """Voiced lines are analysed, except the Work title line Chorus made, which is the
    Narrator's and would otherwise be a chunk (and a request) of its own."""
    return line.voiced and line.passage != "work_title"


def make_chunks(lines: list[Line]) -> list[Chunk]:
    """The analysed lines, in Script order, as chunks of whole paragraphs of about CHUNK_WORDS."""
    chunks: list[Chunk] = []
    current: list[Line] = []
    words = 0
    paragraph: list[Line] = []

    def end_paragraph() -> None:
        nonlocal current, words, paragraph
        n = sum(_words(line.text) for line in paragraph)
        if current and words + n > CHUNK_WORDS:
            chunks.append(Chunk(_part_key(current[0]), current))
            current, words = [], 0
        current += paragraph
        words += n
        paragraph = []

    for line in filter(analysed, lines):
        if paragraph and _part_key(line) != _part_key(paragraph[0]):
            end_paragraph()
            chunks.append(Chunk(_part_key(current[0]), current))
            current, words = [], 0
        elif paragraph and _new_paragraph(paragraph[-1], line):
            end_paragraph()
        paragraph.append(line)
    if paragraph:
        end_paragraph()
    if current:
        chunks.append(Chunk(_part_key(current[0]), current))
    return chunks


# ---- Character pass ----

CAST_SYSTEM = (
    "You maintain the list of Characters of a work of fiction. A Character is a person (or "
    "creature) who speaks or thinks at least one quoted line. You get the list so far (one "
    "Character per line: canonical name, gender, age, then the other ways the text refers to "
    "them) and the next part of the text. Return only what is new in this part: Characters who "
    "speak or think a quoted line here and are not on the list under any name, and new aliases "
    "for Characters already on the list. An alias is another name or title the text uses for that"
    " person, written exactly as in the text (a first name, a surname with a title, a nickname, "
    "such as 'Lizzy' or 'Miss Bennet'); never a pronoun, a description such as 'her sister', or a"
    " word that names a different person. If the list is empty, every speaking Character in this "
    "part is new. A Character the text never names is listed under a short description, such as "
    "'his mother' or 'the old man'. Return an empty list only when nothing is new. Never add a "
    "person who is already listed under another name: give the new name as an alias instead. For "
    "an alias, use the canonical name exactly as listed. For a new Character, give the gender and"
    " the age the text states or clearly implies: a title such as Mr., Mrs., Miss, Sir, Lady, Dr."
    " or Captain, a profession, a husband or wife, or grown children mean at least 'young adult' "
    "or 'adult'; a schoolchild, a little boy or girl, or a baby is a 'child'; a young lady, a "
    "youth, a student or a girl of marriageable age is a 'young adult'; old age, grey hair or "
    "grandchildren mean 'elderly'. Say 'unknown' only when the text gives no hint at all. Say "
    "whether the narration of this part is in the first or third person; if first person, "
    "'character' is the canonical name of the narrating Character (the name others call them, or "
    "a short description if they are never named; never 'I' or 'narrator'), else ''; for a "
    "first-person narrator also give their gender and age as for a new Character, and for third "
    "person 'unknown'."
)

_NARRATOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["person", "character", "gender", "age"],
    "properties": {
        "person": {"type": "string", "enum": ["first", "third"]},
        "character": {"type": "string"},
        # The narrator's, so one the Character pass never listed is not cast blind.
        "gender": {"type": "string", "enum": list(GENDERS)},
        "age": {"type": "string", "enum": list(AGES)},
    },
}
_ALIASES = {"type": "array", "maxItems": 8, "items": {"type": "string"}}
CAST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["narrator", "new_characters", "new_aliases"],
    "properties": {
        "narrator": _NARRATOR_SCHEMA,
        "new_characters": {
            "type": "array",
            "maxItems": 15,
            "items": {
                "type": "object",
                "additionalProperties": False,
                # Gender and age before the aliases, so they are decided from the text first.
                "required": ["name", "gender", "age", "aliases"],
                "properties": {
                    "name": {"type": "string"},
                    "gender": {"type": "string", "enum": list(GENDERS)},
                    "age": {"type": "string", "enum": list(AGES)},
                    "aliases": _ALIASES,
                },
            },
        },
        "new_aliases": {
            "type": "array",
            "maxItems": 15,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "aliases"],
                "properties": {"name": {"type": "string"}, "aliases": _ALIASES},
            },
        },
    },
}

PRONOUNS = frozenset(
    "he she him her his hers they them their you your i me my we us our it its this that "
    "himself herself myself yourself".split()
)
# Lower-case words allowed inside a name ("Sir Lewis de Bourgh", "the Duke of Wellington").
PARTICLES = frozenset("de du da di van von der den la le of the d'".split())


def _age_for_model(age: str) -> str:
    return age.replace("_", " ")


def roster(characters: list[Character]) -> str:
    return (
        "\n".join(
            f"- {c.name} ({c.gender}, {_age_for_model(c.age)}): {', '.join(c.aliases) or '-'}"
            for c in characters
        )
        or "(empty)"
    )


def is_name(alias: str) -> bool:
    """At most four words, each starting with a capital (particles aside); no pronoun or list."""
    words = alias.split()
    if not 1 <= len(words) <= 4 or len(alias) < 2:
        return False
    if any(mark in alias for mark in ",;&") or alias.lower() in PRONOUNS:
        return False
    if not words[0][0].isupper():
        return False
    return all(w[0].isupper() or w.lower() in PARTICLES for w in words)


def _in_text(name: str, text: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.IGNORECASE) is not None


class CastList:
    """The Character list being built, with every name and alias it knows. Names are compared
    with the Language pack's `names` rules ("the Hatter" is "Hatter"), else by lower case."""

    def __init__(self, characters: list[Character], names: NameRules | None = None):
        self.characters = characters
        self.names = names
        self.known = {self.key(n): c for c in characters for n in (c.name, *c.aliases)}

    def key(self, name: str) -> str:
        return self.names.key(name) if self.names else name.strip().lower()

    def find(self, name: str) -> Character | None:
        return self.known.get(self.key(name))

    def add(self, name: str, gender: str = "unknown", age: str = "unknown") -> Character:
        character = Character(
            name=name.strip(), aliases=[], gender=gender, age=age.replace(" ", "_")
        )
        self.characters.append(character)
        self.known[self.key(character.name)] = character
        return character

    def add_alias(self, character: Character, alias: str, text: str) -> bool:
        """Refused if it is not a name, is not in the chunk, or already names someone else."""
        alias = alias.strip()
        if not is_name(alias) or not _in_text(alias, text):
            return False
        if self.key(alias) in self.known:
            return False
        character.aliases = [*character.aliases, alias]
        self.known[self.key(alias)] = character
        return True


def merge(cast: CastList, output: dict, text: str) -> list[Character]:
    """Merges one chunk's answer into the list; returns the Characters added."""
    added = []
    for new in output.get("new_characters", []):
        name = new["name"].strip()
        if not name or name in (NARRATOR, UNKNOWN):
            continue
        character = cast.find(name)
        if character is None:
            character = cast.add(name, new["gender"], new["age"])
            added.append(character)
        else:
            # Listed again: merged, and what it knew now filled in.
            if character.gender == "unknown":
                character.gender = new["gender"]
            if character.age == "unknown":
                character.age = new["age"].replace(" ", "_")
        for alias in new["aliases"]:
            cast.add_alias(character, alias, text)
    for item in output.get("new_aliases", []):
        character = cast.find(item["name"])
        if character is None:
            continue
        for alias in item["aliases"]:
            cast.add_alias(character, alias, text)
    return added


def narrating_character(cast: CastList, answers: list[dict]) -> Character | None:
    """The majority answer of a part's chunks: None for third person, else the most named
    narrating Character, added to the list if missing. A tie goes to first person: a chunk of
    first-person narration with little narration in it is often answered "third" ("A Scandal in
    Bohemia" has two chunks, one answered each way), while a third-person text is almost never
    answered "first" (none of 167 chunks of Pride and Prejudice, M1 ticket 03)."""
    persons = Counter(a["person"] for a in answers)
    if persons["first"] < persons["third"] or not persons["first"]:
        return None
    # "I" or "the narrator" names nobody.
    names = Counter(
        name
        for a in answers
        if a["person"] == "first"
        and (name := a["character"].strip())
        and name.lower() not in PRONOUNS | {"narrator", "the narrator"}
    )
    if not names:
        return None
    # Count the answers by the Character they name, so "Watson" and "Dr. Watson" add up.
    by_character: Counter = Counter()
    unlisted: Counter = Counter()
    for name, count in names.items():
        character = cast.find(name)
        if character is not None:
            by_character[character.name] += count
        else:
            unlisted[name] += count
    if by_character and by_character.most_common(1)[0][1] >= max(unlisted.values(), default=0):
        character = cast.find(by_character.most_common(1)[0][0])
    else:
        character = cast.add(unlisted.most_common(1)[0][0])
    # Fill in what the list does not know from the answers that named them.
    theirs = [
        a for a in answers if a["person"] == "first" and cast.find(a["character"]) is character
    ]
    for trait in ("gender", "age"):
        said = Counter(v for a in theirs if (v := a.get(trait, "unknown")) != "unknown")
        if getattr(character, trait) == "unknown" and said:
            setattr(character, trait, said.most_common(1)[0][0].replace(" ", "_"))
    return character


# ---- Attribution pass ----

ATTRIBUTION_SYSTEM = (
    "You label the quoted lines of a work of fiction for an audio drama. Each quoted line is "
    "marked with its number in square brackets. For every numbered line give: the speaker "
    "(exactly one name from the allowed list; 'Narrator' if the quotation is not said or thought "
    "by a Character, such as a quoted word or title; 'Unknown' only if no listed Character fits),"
    " the kind (speech said aloud, thought, or written text being read or quoted), the emotion of"
    " the delivery, and its intensity ('strong' only when the delivery is clearly more intense "
    "than usual). In a back-and-forth with no speaker tags, speakers usually alternate. If the "
    "narration is first person, lines said or thought by the narrating Character get that "
    "Character's name, never 'Narrator'. Label every numbered line exactly once, in order."
)


def attribution_schema(names: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["lines"],
        "properties": {
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "speaker", "kind", "emotion", "intensity"],
                    "properties": {
                        "id": {"type": "integer"},
                        "speaker": {"type": "string", "enum": [*names, NARRATOR, UNKNOWN]},
                        "kind": {"type": "string", "enum": list(KINDS)},
                        "emotion": {"type": "string", "enum": list(EMOTIONS)},
                        "intensity": {"type": "string", "enum": list(INTENSITIES)},
                    },
                },
            }
        },
    }


def attribution_prompt(
    characters: list[Character], narrator: Character | None, tail: str, text: str, ids: list[int]
) -> str:
    listed = "\n".join(
        f"- {c.name} ({c.gender}, {_age_for_model(c.age)}); "
        f"also called: {', '.join(c.aliases) or '-'}"
        for c in characters
    )
    listed += (
        f"\nThe narration is first person; the narrator is {narrator.name}."
        if narrator
        else "\nThe narration is third person."
    )
    return (
        f"CHARACTERS (allowed speakers, plus Narrator and Unknown):\n{listed}\n\n"
        + (f"TEXT JUST BEFORE (for context, do not label):\n{tail}\n\n" if tail else "")
        + f"TEXT TO LABEL:\n{text}\n\n"
        + f"Label lines {ids[0]} to {ids[-1]} ({len(ids)} lines)."
    )


def label(line: Line, answer: dict | None, characters: dict[str, Character]) -> None:
    """Sets a quoted line's Speaker, kind, Emotion and intensity from the model's answer; a line
    the model left out is Unknown, said, neutral."""
    answer = answer or {"speaker": UNKNOWN, "kind": "speech", "emotion": "neutral"}
    line.kind = answer["kind"]
    speaker = answer["speaker"]
    if speaker == NARRATOR:
        line.speaker, line.character_id, line.emotion, line.intensity = "narrator", None, None, None
        return
    character = characters.get(speaker)
    line.speaker = "character" if character else "unknown"
    line.character_id = character.id if character else None
    line.emotion = answer["emotion"]
    # Thoughts are never strong.
    strong = answer.get("intensity") == "strong" and line.kind != "thought"
    line.intensity = "strong" if strong else "normal"


def _narrate(line: Line) -> None:
    line.speaker, line.character_id, line.emotion, line.intensity = "narrator", None, None, None


# ---- The stage ----

Report = Callable[..., None]


def _start_over(session: Session, work: Work) -> None:
    """Cut the Script again and empty the list, for a Work analysed before or never."""
    from chorus.works import pack_language

    session.execute(
        update(Chapter).where(Chapter.work_id == work.id).values(narrating_character_id=None)
    )
    build_script(session, work, get_packs()[pack_language(work.language)])
    from chorus.assembly import discard
    from chorus.voicing import discard_audio

    discard_audio(work.id)
    discard(session, work)
    work.characters.clear()  # deleted as orphans
    work.analysis = {"stage": "characters", "done": 0, "answers": [], "narrating": {}}
    session.commit()


def analyse(
    session: Session,
    work: Work,
    model: AnalysisModel,
    report: Report,
    check: Callable[[], None] | None = None,
) -> None:
    """Runs the stage over the Work from where it stopped, committing every finished chunk;
    `check` is called before each chunk, so a pause stops after the current one."""
    if not work.analysis or work.analysis.get("stage") == "done":
        _start_over(session, work)
    lines = list(
        session.scalars(select(Line).where(Line.work_id == work.id).order_by(Line.position))
    )
    chunks = make_chunks(lines)
    total = len(chunks)
    from chorus.works import pack_language

    names = get_packs()[pack_language(work.language)].names
    cast = CastList(list(work.characters), names)
    chapters = {str(c.id): c for c in work.chapters}

    pace = Pace()

    def progress(stage: str, done: int) -> None:
        cast_done = total if stage == "attribution" else done
        attribution_done = done if stage == "attribution" else 0
        weight = (1 + ATTRIBUTION_WEIGHT) * total or 1
        reached = cast_done + ATTRIBUTION_WEIGHT * attribution_done
        report(
            stage=stage,
            done=done,
            total=total,
            percent=round(100 * reached / weight),
            seconds_left=pace.seconds_left(reached, weight),
        )

    def step(stage: str, index: int) -> None:
        if check:
            check()
        progress(stage, index)

    def save(**state: object) -> None:
        work.analysis = {**work.analysis, **state}
        session.commit()

    # Character pass.
    if work.analysis["stage"] == "characters":
        answers = list(work.analysis["answers"])
        for index in range(work.analysis["done"], total):
            step("characters", index)
            text = chunks[index].text
            user = f"LIST SO FAR:\n{roster(cast.characters)}\n\nNEXT PART OF THE TEXT:\n{text}"
            done = model.complete(CAST_SYSTEM, user, CAST_SCHEMA, CAST_MAX_TOKENS)
            # A chunk whose answer was cut off adds nothing (4 of 167 on Pride and Prejudice).
            if done.output is not None:
                for character in merge(cast, done.output, text):
                    work.characters.append(character)
                answers.append(done.output["narrator"])
            else:
                answers.append(None)
            save(done=index + 1, answers=answers)

        narrating: dict[str, int | None] = {}
        for part in dict.fromkeys(chunk.part for chunk in chunks):
            given = [a for a, c in zip(answers, chunks, strict=True) if c.part == part and a]
            character = narrating_character(cast, given)
            if character is not None and character not in work.characters:
                work.characters.append(character)
            session.flush()
            narrating[part] = character.id if character else None
            if part in chapters:
                chapters[part].narrating_character_id = narrating[part]
        # A title in a name says the gender the model left unknown ("Mr. Bennet").
        for character in work.characters:
            said = names.gender([character.name, *character.aliases]) if names else None
            if character.gender == "unknown" and said:
                character.gender = said
        save(stage="attribution", done=0, narrating=narrating)

    # Attribution pass.
    if work.analysis["stage"] == "attribution":
        narrating = work.analysis["narrating"]
        by_id = {c.id: c for c in work.characters}
        by_name = {c.name: c for c in work.characters}
        schema = attribution_schema(list(by_name))
        for line in lines:
            if line.voiced and not analysed(line):
                _narrate(line)
        for index in range(work.analysis["done"], total):
            step("attribution", index)
            chunk = chunks[index]
            text, quotes = chunk.render()
            for line in chunk.lines:
                if line.kind == "narration":
                    _narrate(line)
            answers: dict[int, dict] = {}
            if quotes:
                tail = " ".join(chunks[index - 1].text.split()[-TAIL_WORDS:]) if index else ""
                narrator = by_id.get(narrating.get(chunk.part) or -1)
                ids = list(quotes)
                user = attribution_prompt(work.characters, narrator, tail, text, ids)
                done = model.complete(ATTRIBUTION_SYSTEM, user, schema, ATTRIBUTION_MAX_TOKENS)
                for answer in (done.output or {}).get("lines", []):
                    answers.setdefault(answer["id"], answer)
            for number, line in quotes.items():
                label(line, answers.get(number), by_name)
            save(done=index + 1)

        # Characters with no lines leave the list, unless they narrate a chapter.
        speaking = {line.character_id for line in lines if line.character_id is not None}
        keep = speaking | {i for i in narrating.values() if i is not None}
        for character in list(work.characters):
            if character.id not in keep:
                work.characters.remove(character)
        save(stage="done", done=total, finished_at=datetime.now(UTC).isoformat())
    progress("attribution", total)


# ---- The job and its child process ----


def analysed_since(work: Work, asked_at: datetime) -> bool:
    """Whether the Work's analysis finished after this job was asked for: a second click, or a
    job Celery hands out again after a crash while a newer one already finished."""
    finished = (work.analysis or {}).get("finished_at")
    if not finished or (work.analysis or {}).get("stage") != "done":
        return False
    asked = asked_at if asked_at.tzinfo else asked_at.replace(tzinfo=UTC)
    return datetime.fromisoformat(finished) > asked


@job("analysis", Queue.GPU)
def analysis_job(ctx: JobContext) -> None:
    session = ctx.session
    work = session.get(Work, ctx.job.work_id)
    if analysed_since(work, ctx.job.created_at):
        return
    work.state = WorkState.ANALYSING
    work.error = None
    session.commit()
    returncode = run_child(ctx.job.id)
    session.expire_all()
    if returncode == STOPPED_EXIT:
        request = ctx.requested() or PAUSE
        # Cancelled, the Work is back to imported: analysing it again continues from the
        # chunks already done. Paused, it stays analysing, and the job shows as paused.
        if request == CANCEL:
            work.state = WorkState.IMPORTED
        session.commit()
        raise Stopped(request)
    if returncode != 0:
        error = ctx.job.error or {
            "key": "analysis.error.unexpected",
            "params": {"detail": f"exit code {returncode}"},
        }
        work.state = WorkState.FAILED
        work.error = error
        session.commit()
        failed = JobFailed(error["key"])
        failed.params = error["params"]
        raise failed
    work.state = WorkState.ANALYSED
    session.commit()
    cast_work(session, work)
    if get_settings().voice_after_analysis:
        from chorus.voicing import start_voicing

        start_voicing(session, work)


def run_child(job_id: int) -> int:
    """The stage in its own process, so the card's memory is free when it ends."""
    return subprocess.run([sys.executable, "-m", "chorus.analysis", str(job_id)]).returncode


def main(job_id: int) -> int:
    with get_sessionmaker()() as session:
        row = session.get(Job, job_id)
        ctx = JobContext(session, row)
        work = session.get(Work, row.work_id)
        try:
            with LlamaServer(firstrun.gguf_path()) as model:
                analyse(session, work, model, ctx.report, check=ctx.check)
        except Stopped:
            session.rollback()
            return STOPPED_EXIT
        except ModelUnavailable as exc:
            print(f"analysis: {exc}", flush=True)
            session.rollback()
            row.error = {"key": "analysis.error.model", "params": {"detail": str(exc)}}
            session.commit()
            return 1
        except Exception as exc:
            session.rollback()
            row.error = {"key": "analysis.error.unexpected", "params": {"detail": repr(exc)}}
            session.commit()
            raise
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
