# TXT import

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-13: `backend/chorus/importing/txt.py`, used by the import job for `.txt` uploads.

- **Encoding:** the BOM (UTF-8, UTF-16, UTF-32), else strict UTF-8, else `charset-normalizer` 3.5.2. The encoding is always in the warnings: `import.warning.encoding` ("read as UTF-8"), or `import.warning.encoding_detected` when it was guessed.
  - The detector ties Windows-1250, 1252 and 1257 exactly on English text with a few accented letters, and picked 1250, which turned "naïve" into "naďve". A tie now goes to Windows-1252, and a text that reads the same in 1252 is named Windows-1252.
  - A Polish text in Windows-1250 does not tie and is still read as 1250 (tested).
- **Paragraphs:** split at blank lines; wrapped lines are joined and runs of spaces collapsed. A paragraph whose lines are all indented by two spaces or more (verse) keeps its line breaks. One space is not enough: Holmes indents some of its prose by one space. `_underscores_` become italics.
- **Chapters:** a heading is a paragraph of one or two short lines whose first line matches the pack's patterns. The second line is a subtitle when it is short, starts with a capital and is not itself a heading. A multi-line contents list is therefore never taken for headings.
  - The pack's patterns now name a **style** per match: word ("CHAPTER XII", "PART I"), standalone ("EPILOGUE"), lone number ("II.") and the new **numbered title** ("I. A SCANDAL IN BOHEMIA": a number, a full stop and a title in capitals; `numbered_titles` in `pack.json`).
  - **Lone numbers start chapters only when the file has no other style.** Otherwise they stay inside the chapter as headings: Holmes's sections I–III inside "A Scandal in Bohemia", and the epilogue's I and II in Crime and Punishment.
  - A heading with nothing under it (a part title) opens the next chapter: "PART I: CHAPTER I".
  - Text before the first heading is front matter. With no headings, everything is one chapter, with `import.warning.no_chapters`.
- **Section breaks:** three or more blank lines, or a line of `*`, `⁂`, dashes and similar. Doubled breaks collapse into one, and breaks at a chapter's edges are trimmed.
- **Gutenberg:**
  - The `*** START OF …` and `*** END OF …` lines split off the header and the licence. They become front and back matter blocks with the new `boilerplate: true` flag, meaning never voiced. The EPUB reader now sets the same flag on Gutenberg's `#pg-header` and `#pg-footer`.
  - The header's Title, Author and Language lines become the metadata; the language name is mapped to its code through lingua.
  - `[Illustration: …]` notes, which can run over several paragraphs, are dropped. A chapter heading inside one is kept (Pride and Prejudice's "Chapter I."), and the blank lines around a dropped illustration do not count as a Section break.
- **Frontend:** the Import screen accepts `.txt`, the new warning messages are in the catalogue, and boilerplate blocks are shown greyed out.

Acceptance, checked by `tests/test_txt_import.py` (23 tests):

| Text | Chapters | First and last title |
|---|---|---|
| pg11 Alice | 12 | "CHAPTER I: Down the Rabbit-Hole" … "CHAPTER XII: Alice’s Evidence" |
| pg1260 Jane Eyre | 38 | "CHAPTER I" … "CHAPTER XXXVIII—CONCLUSION" |
| pg1342 Pride and Prejudice | 61 | "Chapter I." … "CHAPTER LXI." |
| pg1661 Holmes | 12 | "I. A SCANDAL IN BOHEMIA" … "XII. THE ADVENTURE OF THE COPPER BEECHES" |
| pg2554 Crime and Punishment | 40 | "PART I: CHAPTER I" … "EPILOGUE" (six parts open their first chapter) |
| pg5200 Metamorphosis | 3 | "I" … "III" |

- **Gutenberg boilerplate:** in every text, the header ends with the START line and the licence starts with the END line. All of it is `boilerplate`, and no chapter contains "Project Gutenberg".
- **Windows-1252:** a sample passage saved as Windows-1252 (with "café", "naïve", "façade" added) imports with the right characters and "Windows-1252" in the warnings.
- **No headings:** a file without headings is one chapter, with the warning.
- **Other tests:** Section breaks, contents lists, verse, italics, BOMs, an empty file, and an upload through the API.

Not done:

- Gutenberg's `--` dashes are left as they are.
- Gutenberg `[Footnote …]` blocks are not recognised; they stay as paragraphs.
- Pride and Prejudice's printer's line ("CHISWICK PRESS…") ends the last chapter, as it does in the EPUB.
