# The English Language pack

Type: task (AFK)
Status: ready-for-agent
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
