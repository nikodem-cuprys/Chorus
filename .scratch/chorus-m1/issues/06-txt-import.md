# TXT import

Type: task (AFK)
Status: ready-for-agent
Blocked by: 05

## What to build

A reader that turns a plain-text file into the shared Work structure.

- Encoding: the byte-order mark if present, else UTF-8, else detected with `charset-normalizer`. The encoding used is shown among the import warnings.
- Paragraphs from blank lines; hard-wrapped lines inside a paragraph are joined.
- Chapters from lines that match the Language pack's heading patterns. With none found, or no patterns in the pack, the whole file is one chapter, with an import warning saying so.
- Runs of blank lines or a `***`-style line become Section breaks.
- Project Gutenberg's header and licence text is recognised and marked as never voiced.

## Acceptance criteria

- The full Gutenberg texts in `.scratch/chorus/samples/raw/` (`pg1342.txt` and the others) import with the right chapter count and titles, and their Gutenberg boilerplate is marked never voiced.
- A file in Windows-1252 imports with the right characters and the encoding in the warnings.
- A file with no headings imports as one chapter with the warning.
- Tests cover each of the above.

## Spec

`docs/spec/03-pipeline.md` (Import), `docs/spec/02-architecture.md` (Language packs).
