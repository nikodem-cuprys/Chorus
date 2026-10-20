"""Language packs: everything that differs by language, one folder per language beside this file.

A pack is `pack.json` plus the files it names (the voice model's Emotion settings, the built-in
Voices' `voices.json` and clips). `load_packs` reads and checks every pack once, at startup, and
fails loudly on a missing or broken required part. See docs/spec/02-architecture.md.

| Part               | Required | Used from                                   |
|--------------------|----------|---------------------------------------------|
| quotation          | yes      | the line splitter (ticket 09)               |
| sentences          | yes      | `LanguagePack.split_sentences`              |
| voice_model        | yes      | voicing (ticket 13)                         |
| voices             | yes      | the Voice table, auto-casting (ticket 12)   |
| chapter_headings   | no       | TXT and PDF import                          |
| speech_verbs       | no       | the review queue (milestone 3)              |
| dictionary         | no       | Respelling candidates (milestone 4)         |
| export_lines       | no       | YouTube export (milestone 8)                |
| work_title         | no       | the Script's Work title line (ticket 09)    |
| names              | no       | the Character list (tickets 11 and 12)      |
"""

import json
import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path

PACKS_DIR = Path(__file__).resolve().parent

REQUIRED_PARTS = ("quotation", "sentences", "voice_model", "voices")

# Chorus-wide labels; packs only choose among them (docs/spec/04 and 05).
EMOTIONS = (
    "neutral", "happy", "excited", "amused", "angry", "sad", "afraid", "anxious", "surprised",
)  # fmt: skip
INTENSITIES = ("normal", "strong")
MAX_EXAGGERATION = 0.9
GENDERS = ("female", "male", "neutral")
AGES = ("child", "young_adult", "adult", "elderly")
TIMBRE_WORDS = (
    "low", "high", "bright", "dark", "brisk", "measured", "warm", "soft", "gruff", "crisp",
)  # fmt: skip


class PackError(Exception):
    """A Language pack that cannot be used. The message names the pack and the part."""


@dataclass(frozen=True)
class QuotationRules:
    pairs: tuple[tuple[str, str], ...]  # (opening mark, closing mark)
    dash_starts_dialogue: bool
    # Used instead of `pairs` for a Work whose text opens more quotations with these, such as
    # British books that quote speech with ‘ ’. A closing mark followed by a letter is never a
    # closing mark, which keeps ’ the apostrophe ("don’t") inside such a quotation.
    alternative_pairs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NameRules:
    """How Character names are read: articles left out when names are compared ("the Hatter" is
    "Hatter"), and titles that say a gender ("Mr. Bennet" is male)."""

    articles: frozenset[str]
    # A title, lower case and without its full stop -> female or male.
    titles: dict[str, str]

    def key(self, name: str) -> str:
        """A name as compared: lower case, without a leading article."""
        words = name.strip().lower().split()
        if len(words) > 1 and words[0] in self.articles:
            words = words[1:]
        return " ".join(words)

    def gender(self, names: list[str]) -> str | None:
        """The gender the first title of any of these names says, if one does."""
        for name in names:
            words = name.split()
            if words and (gender := self.titles.get(words[0].lower().rstrip("."))):
                return gender
        return None


@dataclass(frozen=True)
class WorkTitle:
    """How the Work title and author line is said: `format` with {title} and {authors}, the
    authors joined with commas and `and` before the last."""

    format: str
    and_: str

    def say(self, title: str, authors: list[str]) -> str:
        if not authors:
            return title
        joined = (
            authors[0]
            if len(authors) == 1
            else (f"{', '.join(authors[:-1])} {self.and_} {authors[-1]}")
        )
        return self.format.format(title=title, authors=joined)


@dataclass(frozen=True)
class SentenceRules:
    end: tuple[str, ...]
    abbreviations: frozenset[str]


@dataclass(frozen=True)
class EmotionSetting:
    exaggeration: float
    cfg_weight: float


@dataclass(frozen=True)
class VoiceModel:
    id: str
    # emotions[emotion][intensity]
    emotions: dict[str, dict[str, EmotionSetting]]


@dataclass(frozen=True)
class BuiltInVoice:
    id: str
    gender: str
    age: str
    accent: str
    timbre: tuple[str, ...]
    narrator_ok: bool
    clips: dict[str, Path]  # Emotion -> file; only "neutral" for now
    credit: str


@dataclass(frozen=True)
class ChapterHeadings:
    words: tuple[str, ...]
    numbering: tuple[str, ...]  # any of "arabic", "roman", "words"
    units: tuple[str, ...]
    tens: tuple[str, ...]
    joiner: str
    standalone: tuple[str, ...]
    lone_number: bool
    # A number, a full stop and a title in capitals: "I. A SCANDAL IN BOHEMIA".
    numbered_titles: bool = False

    @cached_property
    def _number(self) -> str:
        numbers = []
        if "arabic" in self.numbering:
            numbers.append(r"\d{1,4}")
        if "roman" in self.numbering:
            numbers.append(
                r"(?=[MDCLXVI])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
            )
        if "words" in self.numbering and (self.units or self.tens):
            units = "|".join(map(re.escape, self.units))
            tens = "|".join(map(re.escape, self.tens))
            words = [f"(?:{tens})(?:{re.escape(self.joiner)}(?:{units}))?"] if tens else []
            words += [f"(?:{units})"] if units else []
            numbers.append("|".join(words))
        return "|".join(f"(?:{n})" for n in numbers)

    @cached_property
    def _styles(self) -> list[tuple[str, re.Pattern[str]]]:
        """One whole-line pattern per style of heading, each with an optional title after a
        separator ("Chapter 3. The Ball", "CHAPTER XII")."""
        number = self._number
        title = r"(?:\s*[.:—–-](?:\s*\S.*)?|\s+\S.*)?"
        styles = []
        if self.words and number:
            words = "|".join(map(re.escape, self.words))
            styles.append(("word", f"(?:{words})\\s+(?:{number}){title}", re.IGNORECASE))
        if self.standalone:
            words = "|".join(map(re.escape, self.standalone))
            styles.append(("standalone", f"(?:{words}){title}", re.IGNORECASE))
        if self.lone_number and number:
            styles.append(("lone_number", f"(?:{number})\\.?", re.IGNORECASE))
        if self.numbered_titles and number:
            # Case matters here: the title must have capitals and no lowercase letters.
            styles.append(("numbered_title", f"(?:{number})\\.\\s+(?=.*[A-Z])[^a-z]+", 0))
        return [(name, re.compile(f"\\s*(?:{p})\\s*", flags)) for name, p, flags in styles]

    def style(self, line: str) -> str | None:
        """Which style of heading the line is ("word", "standalone", "lone_number",
        "numbered_title"), or None if it is not a heading."""
        for name, pattern in self._styles:
            if pattern.fullmatch(line):
                return name
        return None

    def is_heading(self, line: str) -> bool:
        return self.style(line) is not None


@dataclass(frozen=True)
class LanguagePack:
    language: str
    path: Path
    quotation: QuotationRules
    sentences: SentenceRules
    voice_model: VoiceModel
    voices: tuple[BuiltInVoice, ...]
    default_narrator: str
    clip_text: str
    chapter_headings: ChapterHeadings | None
    speech_verbs: frozenset[str] | None
    dictionary: frozenset[str] | None
    export_lines: dict[str, str] | None
    work_title: WorkTitle | None = None
    names: NameRules | None = None

    def voice(self, voice_id: str) -> BuiltInVoice:
        return next(v for v in self.voices if v.id == voice_id)

    @cached_property
    def _sentence_end(self) -> re.Pattern[str]:
        ends = "".join(map(re.escape, self.sentences.end))
        closers = "".join(re.escape(close) for _, close in self.quotation.pairs) + re.escape(")]’'")
        return re.compile(f"([{ends}]+)[{closers}]*" + r"(?=\s|$)")

    @cached_property
    def _openers(self) -> str:
        return "".join(open_ for open_, _ in self.quotation.pairs) + "([‘'"

    def split_sentences(self, text: str) -> list[str]:
        """Splits a line into sentences for voicing (long lines are voiced one sentence at a
        time). Not a sentence end: a full stop after an abbreviation from the pack ("Mr.") or
        after a single capital letter (an initial, as in "S. Place"), and any end mark followed
        by a lowercase letter ("How so? how can it affect them?"). Joining the result with
        single spaces gives back the text with its whitespace collapsed."""
        text = " ".join(text.split())
        sentences, start = [], 0
        for match in self._sentence_end.finditer(text):
            following = text[match.end() :].lstrip()
            if following[:1].islower():
                continue
            if match.group(1) == ".":
                word = text[start : match.start()].rsplit(" ", 1)[-1].lstrip(self._openers) + "."
                if word in self.sentences.abbreviations or re.fullmatch(r"[A-Z]\.", word):
                    continue
            sentences.append(text[start : match.end()].strip())
            start = match.end()
        if text[start:].strip():
            sentences.append(text[start:].strip())
        return sentences


def _part(data: dict, name: str, where: str) -> object:
    if data.get(name) in (None, "", [], {}):
        raise PackError(f"{where}: the required part '{name}' is missing")
    return data[name]


def _read_json(path: Path, where: str) -> dict:
    if not path.is_file():
        raise PackError(f"{where}: {path.name} is missing ({path})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackError(f"{where}: {path.name} is not valid JSON ({exc})") from exc


def _strings(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise PackError(f"{where}: expected a list of words")
    return tuple(value)


def _pairs(pairs: object, name: str, where: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(pairs, list) or not all(
        isinstance(p, list) and len(p) == 2 and all(isinstance(m, str) and len(m) == 1 for m in p)
        for p in pairs
    ):
        raise PackError(f"{where}: '{name}' must be a list of [opening, closing] marks")
    return tuple((o, c) for o, c in pairs)


def _load_quotation(raw: dict, where: str) -> QuotationRules:
    pairs = _pairs(_part(raw, "pairs", where), "pairs", where)
    dash = raw.get("dash_starts_dialogue")
    if not isinstance(dash, bool):
        raise PackError(f"{where}: the required part 'dash_starts_dialogue' is missing")
    alternative = _pairs(raw.get("alternative_pairs", []), "alternative_pairs", where)
    return QuotationRules(pairs, dash, alternative)


def _load_work_title(raw: dict, where: str) -> WorkTitle:
    text, and_ = raw.get("format"), raw.get("and")
    if not (isinstance(text, str) and "{title}" in text and "{authors}" in text):
        raise PackError(f"{where}: 'format' must hold {{title}} and {{authors}}")
    if not (isinstance(and_, str) and and_):
        raise PackError(f"{where}: the required part 'and' is missing")
    return WorkTitle(text, and_)


def _load_names(raw: dict, where: str) -> NameRules:
    articles = _strings(raw["articles"], f"{where}.articles") if raw.get("articles") else ()
    titles: dict[str, str] = {}
    for gender, words in (raw.get("titles") or {}).items():
        if gender not in ("female", "male"):
            raise PackError(f"{where}.titles: '{gender}' is not female or male")
        for word in _strings(words, f"{where}.titles.{gender}"):
            titles[word.lower().rstrip(".")] = gender
    return NameRules(frozenset(a.lower() for a in articles), titles)


def _load_sentences(raw: dict, where: str) -> SentenceRules:
    end = _strings(_part(raw, "end", where), f"{where}.end")
    abbreviations = _strings(_part(raw, "abbreviations", where), f"{where}.abbreviations")
    return SentenceRules(end, frozenset(abbreviations))


def _load_voice_model(raw: dict, folder: Path, where: str) -> VoiceModel:
    model_id = _part(raw, "id", where)
    emotions_file = _part(raw, "emotions", where)
    data = _part(_read_json(folder / str(emotions_file), where), "emotions", where)
    emotions: dict[str, dict[str, EmotionSetting]] = {}
    for emotion in EMOTIONS:
        if emotion not in data:
            raise PackError(f"{where}: the Emotion '{emotion}' has no settings")
        emotions[emotion] = {}
        for intensity in INTENSITIES:
            value = data[emotion].get(intensity)
            if not (isinstance(value, list) and len(value) == 2):
                raise PackError(f"{where}: '{emotion}' has no '{intensity}' setting")
            exaggeration, cfg_weight = (float(v) for v in value)
            if exaggeration > MAX_EXAGGERATION:
                raise PackError(
                    f"{where}: '{emotion}' {intensity} has exaggeration {exaggeration}, "
                    f"above {MAX_EXAGGERATION}"
                )
            emotions[emotion][intensity] = EmotionSetting(exaggeration, cfg_weight)
    return VoiceModel(str(model_id), emotions)


def _load_voices(
    voices_file: str, folder: Path, where: str
) -> tuple[tuple[BuiltInVoice, ...], str, str]:
    path = folder / voices_file
    data = _read_json(path, where)
    entries = _part(data, "voices", where)
    voices = []
    for entry in entries:
        voice_id = entry.get("id") or "?"
        here = f"{where}: Voice '{voice_id}'"
        for name in ("id", "gender", "age", "accent", "timbre", "clips", "credit"):
            _part(entry, name, here)
        if entry["gender"] not in GENDERS:
            raise PackError(f"{here}: unknown gender '{entry['gender']}'")
        if entry["age"] not in AGES:
            raise PackError(f"{here}: unknown age band '{entry['age']}'")
        timbre = _strings(entry["timbre"], f"{here}.timbre")
        if not 1 <= len(timbre) <= 3 or set(timbre) - set(TIMBRE_WORDS):
            raise PackError(f"{here}: timbre must be one to three of {', '.join(TIMBRE_WORDS)}")
        if not isinstance(entry.get("narrator_ok"), bool):
            raise PackError(f"{here}: the required part 'narrator_ok' is missing")
        if "neutral" not in entry["clips"]:
            raise PackError(f"{here}: the neutral clip is missing")
        clips = {}
        for emotion, name in entry["clips"].items():
            clip = path.parent / name
            if not clip.is_file():
                raise PackError(f"{here}: the clip {name} is missing ({clip})")
            clips[emotion] = clip
        voices.append(
            BuiltInVoice(
                id=entry["id"],
                gender=entry["gender"],
                age=entry["age"],
                accent=entry["accent"],
                timbre=timbre,
                narrator_ok=entry["narrator_ok"],
                clips=clips,
                credit=entry["credit"],
            )
        )
    ids = [v.id for v in voices]
    if len(set(ids)) != len(ids):
        raise PackError(f"{where}: two Voices share an id")
    narrator = _part(data, "default_narrator", where)
    if not any(v.id == narrator and v.narrator_ok for v in voices):
        raise PackError(f"{where}: the default Narrator '{narrator}' is not a Narrator Voice")
    return tuple(voices), str(narrator), str(data.get("clip_text", ""))


def _load_chapter_headings(raw: dict, where: str) -> ChapterHeadings:
    words = raw.get("number_words") or {}
    numbering = _strings(raw["numbering"], f"{where}.numbering") if raw.get("numbering") else ()
    if set(numbering) - {"arabic", "roman", "words"}:
        raise PackError(f"{where}: numbering must be among arabic, roman, words")
    return ChapterHeadings(
        words=_strings(raw["words"], f"{where}.words") if raw.get("words") else (),
        numbering=numbering,
        units=tuple(words.get("units", ())),
        tens=tuple(words.get("tens", ())),
        joiner=words.get("joiner", "-"),
        standalone=tuple(raw.get("standalone", ())),
        lone_number=bool(raw.get("lone_number", False)),
        numbered_titles=bool(raw.get("numbered_titles", False)),
    )


def load_pack(folder: Path) -> LanguagePack:
    where = f"Language pack '{folder.name}'"
    raw = _read_json(folder / "pack.json", where)
    language = _part(raw, "language", where)
    if language != folder.name:
        raise PackError(f"{where}: pack.json says language '{language}'")
    for name in REQUIRED_PARTS:
        _part(raw, name, where)

    voices, narrator, clip_text = _load_voices(
        str(raw["voices"]), folder, f"{where}, part 'voices'"
    )
    headings = raw.get("chapter_headings")
    speech_verbs = raw.get("speech_verbs")
    dictionary = raw.get("dictionary")
    if dictionary:
        dictionary = (folder / dictionary).read_text(encoding="utf-8").split()
    return LanguagePack(
        language=language,
        path=folder,
        quotation=_load_quotation(raw["quotation"], f"{where}, part 'quotation'"),
        sentences=_load_sentences(raw["sentences"], f"{where}, part 'sentences'"),
        voice_model=_load_voice_model(raw["voice_model"], folder, f"{where}, part 'voice_model'"),
        voices=voices,
        default_narrator=narrator,
        clip_text=clip_text,
        chapter_headings=(
            _load_chapter_headings(headings, f"{where}, part 'chapter_headings'")
            if headings
            else None
        ),
        speech_verbs=(
            frozenset(_strings(speech_verbs, f"{where}, part 'speech_verbs'"))
            if speech_verbs
            else None
        ),
        dictionary=frozenset(dictionary) if dictionary else None,
        export_lines=raw.get("export_lines") or None,
        work_title=(
            _load_work_title(raw["work_title"], f"{where}, part 'work_title'")
            if raw.get("work_title")
            else None
        ),
        names=_load_names(raw["names"], f"{where}, part 'names'") if raw.get("names") else None,
    )


def load_packs(packs_dir: Path | None = None) -> dict[str, LanguagePack]:
    """Every pack under `packs_dir`, by language code. Raises PackError on the first bad one."""
    packs_dir = packs_dir or PACKS_DIR
    packs = {
        folder.name: load_pack(folder)
        for folder in sorted(packs_dir.iterdir())
        if (folder / "pack.json").is_file()
    }
    if not packs:
        raise PackError(f"No Language packs found in {packs_dir}")
    return packs


@lru_cache
def get_packs() -> dict[str, LanguagePack]:
    return load_packs()


def get_pack(language: str) -> LanguagePack:
    return get_packs()[language]
