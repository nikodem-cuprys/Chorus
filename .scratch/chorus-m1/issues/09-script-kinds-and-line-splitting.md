# The Script: kinds of text and line splitting

Type: task (AFK)
Status: ready-for-agent
Blocked by: 04, 05

## What to build

The deterministic part of analysis, which needs no model: turning a Work's blocks into the lines of a Script.

- Lines and Characters in the database (`docs/spec/05-data-model.md`, Line and Character), with the Script as the chapters' lines in order.
- Kinds of text from markup only: chapter title, Work title and author, epigraph, letter, verse, footnote, list or table, AO3 summary or author note, and never-voiced material (tags, dedications, copyright pages, Gutenberg boilerplate, images and captions, tables of contents, page furniture). Anything not marked is narration, including unquoted italic passages.
- The ticket 21 defaults decide which kinds are voiced in M1 (no switches yet): summaries, author notes and footnotes are not voiced; titles, epigraphs, letters, verse and lists are.
- Line splitting with the pack's quotation rules: each quotation is one line, and the narration between quotations inside a paragraph is one line. A quotation that runs on into the next paragraph stays one quotation (English convention: the paragraph opens with a quotation mark and the previous one did not close).
- A letter read aloud inside quotation marks stays ordinary dialogue.
- The reading view does not exist yet; the Work page shows each chapter's lines with their kind, for checking.

## Acceptance criteria

- The six passages in `.scratch/chorus/samples/passages/` split into the same quoted lines as the prototype (`.scratch/chorus/prototypes/attribution/lines/`), except the Hatter's song in the Alice passage, which now stays one quotation.
- The Gutenberg EPUB's chapter titles, and a TXT file's Gutenberg boilerplate, come out as their kinds (voiced and never voiced respectively). Recognising AO3 summaries and notes is M2.
- Tests cover the multi-paragraph quotation and each kind.

## Spec

`docs/spec/03-pipeline.md` (Analysis steps 1 and 2; Assembly table of kinds).
