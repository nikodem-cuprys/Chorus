from itertools import combinations

from sqlalchemy import select

from chorus.casting import Casting, Role, cast_roles, cast_work, narration_voice, roles_of
from chorus.db import get_sessionmaker
from chorus.languages import get_packs
from chorus.models import Chapter, Character, Line, Voice, Work, WorkState
from chorus.voices import sync_built_in_voices

PACK = get_packs()["en"]


def character_voices() -> list[Casting]:
    """The English pack's 11 Character Voices: every built-in Voice but the Narrator's."""
    return [Casting(v.id, v.gender, v.age) for v in PACK.voices if v.id != PACK.default_narrator]


def genders(cast: dict[int, str]) -> dict[int, str]:
    by_id = {v.id: v.gender for v in PACK.voices}
    return {role: by_id[voice] for role, voice in cast.items()}


def test_twenty_characters_over_five_chapters_never_share_a_voice_in_a_chapter():
    # Four speakers a chapter, two women and two men; the busiest first.
    roles = [
        Role(
            id=n,
            gender="female" if n % 2 else "male",
            age="adult",
            lines=100 - n,
            chapters=frozenset({n // 4}),
        )
        for n in range(20)
    ]
    cast = cast_roles(roles, character_voices())

    assert PACK.default_narrator not in cast.values()
    assert genders(cast) == {r.id: r.gender for r in roles}
    # The 11 with the most lines that fit a free Voice of their gender get one of their own.
    assert len(set(cast[r.id] for r in roles[:10])) == 10
    for a, b in combinations(roles, 2):
        if cast[a.id] == cast[b.id]:
            assert not (a.chapters & b.chapters), (a.id, b.id, cast[a.id])


def test_where_sharing_in_a_chapter_cannot_be_avoided_the_fewest_chapters_are_shared():
    # Six women for five female Voices, all in chapter 1; the sixth, like the fifth, is also in
    # chapters 2 and 3, so sharing with the fifth would put them together in three chapters.
    roles = [Role(n, "female", "adult", 50 - n, frozenset({1})) for n in range(5)]
    roles[4] = Role(4, "female", "adult", 46, frozenset({1, 2, 3}))
    roles.append(Role(5, "female", "adult", 10, frozenset({1, 2, 3})))
    cast = cast_roles(roles, character_voices())

    shared = [r.id for r in roles[:5] if cast[r.id] == cast[5]]
    assert len(shared) == 1 and shared[0] != 4
    assert len(set(cast.values())) == 5


def test_unknown_gender_characters_spread_over_the_least_used_voices():
    known = [
        Role(n, v.gender, "adult", 100 - 5 * n, frozenset({1}))
        for n, v in enumerate(character_voices())
    ]
    minor = [Role(100 + n, "unknown", "unknown", 1, frozenset({9})) for n in range(3)]
    cast = cast_roles(known + minor, character_voices())

    least_used = [cast[r.id] for r in known[-3:]]
    assert sorted(cast[r.id] for r in minor) == sorted(least_used)


def test_children_and_the_elderly_get_an_adult_voice_of_their_gender():
    ages = {v.id: v.age for v in PACK.voices}
    cast = cast_roles(
        [
            Role(1, "male", "child", 30, frozenset({1})),
            Role(2, "male", "young_adult", 20, frozenset({1})),
            Role(3, "female", "elderly", 10, frozenset({1})),
        ],
        character_voices(),
    )
    assert ages[cast[1]] == "adult"
    assert cast[2] == "am_fenrir"  # the one young adult Voice
    assert ages[cast[3]] == "adult" and genders(cast)[3] == "female"


def test_a_narrating_character_is_cast_first_and_not_shared_lightly():
    # Seven men for six male Voices. The narrator has few quoted lines, but reads the narration
    # of two chapters, which counts as theirs (roles_of).
    roles = [Role(n, "male", "adult", 100 - n, frozenset({1})) for n in range(6)]
    roles.append(Role(9, "male", "adult", 400, frozenset({1, 2}), narrates=True))
    cast = cast_roles(roles, character_voices())
    assert cast[9] == "am_eric"  # first pick of the male adult Voices
    assert list(cast.values()).count(cast[9]) == 1


# ---- The Work ----


def test_a_work_is_cast_and_its_first_person_chapter_is_narrated_by_its_character():
    with get_sessionmaker()() as session:
        sync_built_in_voices(session, get_packs())
        work = Work(title="", source_kind="txt", source_name="t", state=WorkState.ANALYSED)
        session.add(work)
        session.flush()
        one = Chapter(work_id=work.id, index=1, content_hash="x", blocks=[])
        two = Chapter(work_id=work.id, index=2, content_hash="y", blocks=[])
        watson = Character(work_id=work.id, name="Watson", gender="male", age="unknown")
        holmes = Character(work_id=work.id, name="Holmes", gender="male", age="adult")
        irene = Character(work_id=work.id, name="Irene", gender="female", age="adult")
        session.add_all([one, two, watson, holmes, irene])
        session.flush()
        two.narrating_character_id = watson.id
        lines = [(holmes, one), (holmes, two), (irene, one), (watson, two)]
        for position, (who, chapter) in enumerate(lines):
            session.add(
                Line(
                    work_id=work.id, chapter_id=chapter.id, part="chapter", position=position,
                    spans=[], text="“…”", kind="speech", passage="narration", voiced=True,
                    speaker="character", character_id=who.id,
                )
            )  # fmt: skip
        for position, chapter in ((10, one), (11, two)):  # narration, read by Watson in two
            session.add(
                Line(
                    work_id=work.id, chapter_id=chapter.id, part="chapter", position=position,
                    spans=[], text="I went.", kind="narration", passage="narration", voiced=True,
                    speaker="narrator",
                )
            )  # fmt: skip
        # A Voice the user chose stays.
        lewis = session.scalar(select(Voice).where(Voice.name == "bm_lewis"))
        irene.voice_id, irene.voice_auto = lewis.id, False
        session.commit()
        session.refresh(work)

        roles = {r.id: r for r in roles_of(session, work)}
        assert (roles[watson.id].lines, roles[watson.id].narrates) == (2, True)
        assert roles[holmes.id].chapters == frozenset({one.id, two.id})

        cast_work(session, work)

        names = {v.id: v.name for v in session.scalars(select(Voice))}
        assert names[work.narrator_voice_id] == PACK.default_narrator
        assert names[irene.voice_id] == "bm_lewis" and not irene.voice_auto
        assert holmes.voice_auto and watson.voice_auto
        voiced = {names[c.voice_id] for c in (holmes, watson)}
        assert len(voiced) == 2 and PACK.default_narrator not in voiced
        characters = {c.id: c for c in work.characters}
        assert narration_voice(work, two, characters) == watson.voice_id
        assert narration_voice(work, one, characters) == work.narrator_voice_id
        assert narration_voice(work, None, characters) == work.narrator_voice_id
