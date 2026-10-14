# The Script: kinds of text and line splitting

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-14: `backend/chorus/script.py`, the `line` table (migration 0004), and a Text / Lines switch on the Work page's reader.

- **When:** the Script is built at the end of every import (`build_script`), from the pack of the Work's language. Changing the language does not rebuild it; ticket 11 should rebuild it when analysis starts.
- **Line:** Work, chapter (none for front and back matter), part (`front`, `chapter`, `back`), position in the whole Work, the first and last paragraph it comes from (indexes into the part's blocks; for a chapter, notes before + blocks + notes after as one list), spans with marks, text, kind (`narration` or `quote`; ticket 11 makes a quote speech, thought or written), passage, voiced.
- **Passages from markup only:** heading → chapter title; epigraph, letter, verse, list item → their kinds; footnote; chapter notes → AO3 note; Gutenberg boilerplate → never voiced; paragraphs and block quotations → narration. The EPUB reader now also recognises epigraphs (`epigraph` class or epub:type) and verse (`poem`, `verse`, `stanza`, `song`, `lyrics`, `z3998:*`) as block types.
- **Made by Chorus:** a Work title and author line opens the Script ("Pride and Prejudice, by Jane Austen", from the pack's new optional `work_title`). A chapter whose title came from the table of contents, with no heading in its text, gets a chapter-title line.
- **Voiced in M1:** narration, chapter titles, the Work title, epigraphs, letters, verse, lists. Not voiced: footnotes, AO3 notes, never-voiced text.
- **Front and back matter (decided with the user):** voiced like a chapter, except their lists (contents, lists of illustrations), which are never voiced. The P&P sample TXT has no "Chapter I" heading, so its first chapter is front matter; this keeps it voiced. The cost: a Gutenberg EPUB's title page and Saintsbury's preface are read too.
- **Splitting:** narration and verse are split at quotation marks; every other passage is one line per block, so a letter block stays whole and a letter read inside quotation marks is ordinary dialogue. A quotation open at a paragraph's end runs on when the next paragraph opens with the mark again (English convention) or when, within 3 paragraphs, the next mark is a closing one (a song inside a speech). Otherwise it ends with its paragraph, as in the prototype. A Section break or another kind of block ends it.
- **Single curly quotes (left open by ticket 04):** the pack gets `alternative_pairs: [["‘", "’"]]`, used for a Work whose text opens more quotations with ‘ than with “ or ". A closing mark followed by a letter is never a closing mark, so "don’t" and "it’s" stay inside. A plural possessive ("the girls’ room") inside a single-quoted speech would still close it early.
- **Pack marks** must now be single characters.

Acceptance:

- **Six passages:** the same quotations as the prototype (once its `_underscores_` are taken as italics), 288 in all. The two that differ are both in the Alice passage: the Hatter's "Twinkle, twinkle, little bat" now stays inside his speech, and so does "Up above the world you fly", the second song (same pattern, also cut out by the prototype). `tests/test_script.py::test_the_sample_passages_split_like_the_prototype`.
- **Gutenberg EPUB:** every chapter's first line is its chapter title, voiced; the header and licence are never voiced. **TXT** (`pg5200.txt`): the header and licence are never voiced.
- **Tests:** a multi-paragraph speech (curly and straight marks), the song, an unclosed quotation, the lookahead limit, a Section break, letters, single marks with apostrophes, marks kept on cut spans, and each kind.

Not checked in a browser: Docker and the Chrome extension were both unavailable. The API was checked against a local server instead.

Left for later:

- **Epigraphs** are recognised only by explicit markup. A block quotation right after a chapter heading (Gutenberg's usual epigraph) is narration.
- **Dash dialogue** (`dash_starts_dialogue`) is not used yet; English does not need it.
- **Works imported before this ticket** have no lines until they are imported again (or analysed, from ticket 11).
