# PDF import

Type: task (AFK)
Status: ready-for-agent
Blocked by: 05

## What to build

A reader for PDFs with a text layer, on `pdfplumber` (characters with font, size and position) and `pypdf` (bookmarks). No AGPL libraries.

- Headers, footers and page numbers: drop lines in the top and bottom bands whose text, with digits removed, repeats across many pages, and lines that are only a number or a roman numeral.
- Italics from the font name (`Italic`, `Oblique`, `-It`) or slanted characters.
- Paragraphs rebuilt from line spacing and first-line indents, joined across page breaks; two-column pages read column by column.
- Hyphens at line ends removed when a lowercase start follows; a hyphen is kept when the joined word is not in a word list but both halves are ("well-known").
- Chapters from the bookmarks, else from headings by font size or the Language pack's heading patterns.
- Pages with no text layer: the file is rejected with a message that scanned PDFs are not supported.
- What was removed is reported among the import warnings ("headers removed on 212 pages").

## Acceptance criteria

- `.scratch/chorus/samples/import/hard-two-column.pdf` imports with no running headers or page numbers in the text, columns in the right order, and its 60 line-end hyphens resolved. This fixture has never been opened by a PDF reader, so check it renders first; fix the fixture if it is broken.
- A PDF made only of images is rejected with the scanned-PDF message.
- Tests cover header removal, de-hyphenation and chapter detection.

## Spec

`docs/spec/03-pipeline.md` (Import), `docs/spec/04-models-and-libraries.md` (Import libraries).
