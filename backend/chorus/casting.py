"""Auto-casting: every Speaker gets a built-in Voice of the Work's Language pack, straight after
analysis (docs/spec/03-pipeline.md, Casting).

- **Narrator:** the pack's default Narrator Voice, never given to a Character.
- **Narrating Character:** cast like any Character, by their own traits. In a first-person chapter
  the narration is read in that Character's Voice (`narration_voice`); the Narrator's Voice is not
  used there. This is the one Voice the Narrator shares.
- **Characters**, Narrating Characters first and then by lines, most first, take an unused Voice of
  their gender while one is left. The rest share: each takes the Voice of their gender whose
  Characters share the fewest chapters with them, then the closest age, then the fewest lines so
  far. A Character of unknown gender is matched across all the Character Voices the same way, so
  minor unnamed speakers spread over the least-used Voices.
- **Age:** no built-in Voice is a child or elderly, so those Characters are matched as adults.
- **Cloned Voices** are never auto-cast. A Voice the user chose is kept (from milestone 3).

Run by hand with `python -m chorus.casting <work id>`.
"""

import sys
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from chorus.db import get_sessionmaker
from chorus.languages import get_packs
from chorus.models import Chapter, Character, Line, Voice, Work


@dataclass
class Role:
    """A Character as casting sees them."""

    id: int
    gender: str  # female, male, unknown
    age: str  # child, young_adult, adult, elderly, unknown
    lines: int
    # The parts they are heard in: chapters where they speak, or which they narrate.
    chapters: frozenset = frozenset()
    narrates: bool = False


@dataclass
class Casting:
    voice: str  # a Voice's id in the pack ("am_michael")
    gender: str
    age: str
    roles: list[Role] = field(default_factory=list)

    @property
    def lines(self) -> int:
        return sum(r.lines for r in self.roles)

    def shared_chapters(self, role: Role) -> int:
        return sum(len(role.chapters & other.chapters) for other in self.roles)


def _age_miss(role: Role, voice: Casting) -> int:
    if role.age == "unknown":
        return 0
    wanted = "young_adult" if role.age == "young_adult" else "adult"
    return 0 if voice.age == wanted else 1


def _fits(role: Role, voice: Casting) -> bool:
    return role.gender == "unknown" or role.gender == voice.gender


def cast_roles(roles: list[Role], voices: list[Casting]) -> dict[int, str]:
    """Each role's Voice. `voices` are the Character Voices: the pack's, without the Narrator's."""
    order = sorted(roles, key=lambda r: (not r.narrates, -r.lines, r.id))
    chosen: dict[int, Casting] = {}
    for role in order:
        unused = [v for v in voices if not v.roles and _fits(role, v)]
        if unused:
            chosen[role.id] = min(unused, key=lambda v: _age_miss(role, v))
        else:
            # No Voice of their gender is left: share. (A gender with no Voice at all would take
            # any Voice.)
            fitting = [v for v in voices if _fits(role, v)] or voices
            chosen[role.id] = min(
                fitting,
                key=lambda v: (v.shared_chapters(role), _age_miss(role, v), v.lines),
            )
        chosen[role.id].roles.append(role)
    return {role_id: voice.voice for role_id, voice in chosen.items()}


# ---- The Work ----


def roles_of(session: Session, work: Work) -> list[Role]:
    """The Work's Characters with their lines and the parts they are heard in. A Narrating
    Character's lines include the narration they read, so nobody else shares their Voice lightly."""
    narrated: dict[int, set] = {}
    narrator_of: dict[object, int] = {}
    for chapter in work.chapters:
        if chapter.narrating_character_id is not None:
            narrated.setdefault(chapter.narrating_character_id, set()).add(chapter.id)
            narrator_of[chapter.id] = chapter.narrating_character_id
    for part, character_id in (work.analysis or {}).get("narrating", {}).items():
        if part in ("front", "back") and character_id is not None:
            narrated.setdefault(character_id, set()).add(part)
            narrator_of[part] = character_id
    rows = session.execute(
        select(Line.character_id, Line.chapter_id, Line.part, Line.speaker).where(
            Line.work_id == work.id, Line.speaker.in_(("character", "narrator"))
        )
    ).all()
    lines: dict[int, int] = {}
    heard: dict[int, set] = {}
    for character_id, chapter_id, part, speaker in rows:
        where = chapter_id or part
        if speaker == "narrator":
            character_id = narrator_of.get(where)
            if character_id is None:
                continue
        lines[character_id] = lines.get(character_id, 0) + 1
        heard.setdefault(character_id, set()).add(where)
    return [
        Role(
            id=c.id,
            gender=c.gender,
            age=c.age,
            lines=lines.get(c.id, 0),
            chapters=frozenset(heard.get(c.id, set()) | narrated.get(c.id, set())),
            narrates=c.id in narrated,
        )
        for c in work.characters
    ]


def cast_work(session: Session, work: Work) -> None:
    """Sets the Narrator's Voice and auto-casts every Character whose Voice the user did not
    choose."""
    from chorus.works import pack_language

    pack = get_packs()[pack_language(work.language)]
    built_in = {
        v.name: v
        for v in session.scalars(
            select(Voice).where(Voice.built_in, Voice.language == pack.language)
        )
    }
    work.narrator_voice_id = built_in[pack.default_narrator].id
    voices = [
        Casting(name, v.gender, v.age)
        for name, v in built_in.items()
        if name != pack.default_narrator
    ]
    by_name = {c.voice: c for c in voices}
    chosen_by_user = {c.id for c in work.characters if c.voice_id and not c.voice_auto}
    roles = roles_of(session, work)
    # Voices the user chose count as taken, so auto-casting shares around them.
    names = {v.id: v.name for v in built_in.values()}
    for role in roles:
        if role.id in chosen_by_user:
            character = session.get(Character, role.id)
            if names.get(character.voice_id) in by_name:
                by_name[names[character.voice_id]].roles.append(role)
    cast = cast_roles([r for r in roles if r.id not in chosen_by_user], voices)
    for character in work.characters:
        if character.id in cast:
            character.voice_id = built_in[cast[character.id]].id
            character.voice_auto = True
    session.commit()


def narration_voice(work: Work, chapter: Chapter | None, characters: dict[int, Character]) -> int:
    """The Voice reading a chapter's narration: its Narrating Character's in a first-person
    chapter, else the Narrator's. `chapter` is None for the front and back matter."""
    narrating = chapter.narrating_character_id if chapter is not None else None
    character = characters.get(narrating) if narrating is not None else None
    if character is not None and character.voice_id is not None:
        return character.voice_id
    return work.narrator_voice_id


def main(work_id: int) -> int:
    with get_sessionmaker()() as session:
        work = session.get(Work, work_id)
        cast_work(session, work)
        voices = {v.id: v.name for v in session.scalars(select(Voice))}
        print(f"Narrator: {voices[work.narrator_voice_id]}")
        for c in work.characters:
            print(f"{c.name}: {voices.get(c.voice_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
