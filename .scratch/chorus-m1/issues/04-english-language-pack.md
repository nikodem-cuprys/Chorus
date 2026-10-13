# The English Language pack

Type: task (AFK)
Status: resolved
Blocked by: 01

## What to build

The Language pack format and its loader, with English as the one pack.

- Required parts: quotation rules for the line splitter (mark pairs that open and close speech; whether a leading dash starts dialogue); sentence rules (sentence-end punctuation and an abbreviation list such as "Mr.", "Mrs.", "Dr.", "St."); the voice model id with its Emotion settings (from `.scratch/chorus/prototypes/emotion-settings/emotions.json`); the built-in Voices with the default Narrator (from `.scratch/chorus/prototypes/voice-library/library/`: `voices.json` and the 12 clips; default `af_bella`).
- Optional parts: chapter-heading patterns (heading words and numbering styles: "Chapter 12", "CHAPTER XII", "Part One", a lone number); the speech-verb list (unused until M3); a dictionary (unused until M4); listener-facing export lines (unused until M8).
- The loader validates a pack and fails loudly on a missing required part.
- Built-in Voices appear in the database as read-only Voices with their labels, language and credit.
- A sentence splitter that uses the pack's rules.

## Acceptance criteria

- Chorus starts with the English pack loaded and the 12 Voices listed with their labels.
- Removing a required part makes startup fail with a message naming the part.
- Tests: the English pack is complete, every Voice clip exists, and the sentence splitter keeps "Mr. Bennet" whole while splitting the sample passages at their sentence ends.

## Spec

`docs/spec/02-architecture.md` (Language packs), `docs/spec/04-models-and-libraries.md` (Emotion settings, Built-in Voices), `docs/spec/05-data-model.md` (Voice).

## Answer

Built on 2026-10-13.

- **Format:** one folder per language under `backend/chorus/languages/` (shipped as package data). `en/pack.json` holds the quotation rules (`“ ”` and straight `" "`; a leading dash does not start dialogue), the sentence rules (end marks `. ! ? …` and 50 abbreviations), the voice model (`chatterbox-500m` with `emotions.json` beside it), the path to `voices/voices.json`, the chapter-heading patterns and the speech verbs. The 12 clips are in `en/voices/`. In `voices.json` the labels are ids (`young_adult`, `american`); the interface translates them.
- **Loader:** `chorus.languages.load_packs` reads every pack and raises `PackError` with the pack and the part named, for example "Language pack 'en': the required part 'sentences' is missing". It also checks each Emotion and intensity (exaggeration at most 0.9), each Voice's labels against the fixed lists, that every clip exists, and that the default Narrator suits the Narrator. The web service loads the packs in its startup (lifespan), so a broken pack stops it.
- **Voices in the database:** a `voice` table (migration 0002). `chorus.voices.sync_built_in_voices` makes its built-in rows match the packs at every startup; nothing else writes them. The API has `GET /api/voices` (with `default_narrator`) and `GET /api/voices/{id}/clip`. The Library page lists them with their labels and a player.
- **Sentence splitter:** `LanguagePack.split_sentences`. A sentence ends at end marks plus any closing quotes or brackets, followed by a space. It does not end after a pack abbreviation (also after an opening quote: "“Mr."), after a single capital (the initial in "S. Place"), or before a lowercase letter ("How so? how can it affect them?").
- **Chapter headings:** `ChapterHeadings.is_heading` matches "Chapter 12", "CHAPTER XII", "Part One", "Chapter Twenty-One", "Chapter 3. The Ball", "Prologue" and a lone number. It is ready for tickets 06 and 07.

Acceptance:

- **12 Voices at startup:** checked with the unit tests (SQLite). `TestClient` runs the startup, lists all 12 with their labels and the default Narrator, and serves a clip. Not yet checked on the Compose stack: Docker was not running. A wheel build does contain `pack.json`, `emotions.json`, `voices.json` and the 12 clips.
- **Removing a required part:** each of the four makes `load_packs` fail with the part named, and the app's startup fails with the same error.
- **Tests (`tests/test_languages.py`):** the pack is complete, every clip exists and is a WAV, and "Mr. Bennet" stays whole. On all six sample passages, every sentence but the last in a paragraph ends at a sentence end. None ends at an abbreviation or initial, none starts lowercase, and joining them gives back the paragraph.

Left for later:

- **Dictionary (M4) and export lines (M8):** the loader accepts both, but the English pack has neither. The AO3 line is still open question 9.
- **Single curly quotes:** `‘ ’` is not a quotation pair, because `’` is also the apostrophe. Ticket 09 should decide this when it builds the line splitter, since British-style books need it.
- **Timbre words per Voice:** the spec says two or three, but six Voices have one, so the check allows one to three.

## Comments

2026-10-13, ticket 08: checked on the Compose stack (PostgreSQL). The web service starts with the pack loaded, `/api/voices` lists the 12 Voices with `af_bella` as the default Narrator, and clips are served as `audio/wav`.
