# PDF import

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-13: `backend/chorus/importing/pdf.py` on `pdfplumber` 0.11.10 (pdfminer.six, MIT) and `pypdf` 6.19.0 (BSD-3-Clause). No AGPL libraries. Both resolve together with the frozen GPU constraints.

- **The fixture renders.** It opens in pdfplumber and pypdfium2 as 4 A4 pages: two columns, alternating running headers, page numbers, and `CHAPTER II` partway down a column. It did not need fixing.
- **Page furniture:** lines in the top and bottom 9% of a page are looked at. A line is removed as a header when, with digits ignored, it appears on at least min(3, max(2, pages/2)) pages and is not set larger than the body text. A line that is only a page number (arabic or roman, "Page 3 of 10", dashes or brackets around it) is removed. A non-repeating line near the top stays. Counts go to the warnings: `pdf_headers_removed` and `pdf_page_numbers_removed`.
- **Columns:** per page, the middle of the widest vertical strip (between 30% and 70% of the width) that no word crosses. The middle matters: the first empty position sat right after the longest left line, put a left-column "I" in the right column, and made every right-column line look indented.
  - Columns that start at about the same place share their margins across pages, so a page holding one short line still has proper edges for judging indents and short lines.
- **Paragraphs:** within a column, more than 1.25 times the usual line spacing, or a first-line indent over 0.6 em, starts a paragraph; more than 2.6 times is a Section break. Across a column or page break there is no spacing to go on, so a paragraph ends when:
  - the column's last line ends a sentence and is short, or
  - it ends a sentence and the column ended early (above the usual column bottom), or
  - it closes a quotation and the next line opens one (the pack's quotation marks), or
  - the next page starts a bookmark.
- **Headings:** text more than 1.1 times the body size is a heading. So is a short paragraph in body type that matches the pack's patterns.
- **Italics:** from the font name (`Italic`, `Oblique`, `-It`) or a slanted character matrix; bold from the font name.
- **Hyphens:** a hyphen at a line end before a lowercase letter is removed, **except** when the same hyphenated word appears elsewhere in the text mid-line ("well-known"). Before a capital ("Saint-
Malo") the hyphen stays and the lines join. A dash at a line end joins without a space.
  - **Deviation:** the spec's other rule (keep the hyphen when both halves are words but the joined word is not) needs a real dictionary. With only the document's words as the list, it kept 5 of the fixture's 60 wrongly ("some-where", "nurse-ry", "pass-ages", "child-ren's", "the-orise").
  - The packaged lists found are no good: `english-words` has Webster's 1934 without inflections, and its GCIDE is GPL. So that rule runs only when the Language pack has a `dictionary` (milestone 4); the code is in place.
- **Chapters:** top-level bookmarks (two or more), else headings that match the pack's patterns, else all headings (with `split_by_headings`), else one chapter (with `no_chapters`). Front and back matter are told apart as for EPUB. The arranging code moved from `epub.py` to `importing/chapters.py`, which both readers now use.
- **Rejections:**
  - All pages, or more than half, without text: `import.error.scanned_pdf`. Fewer get the warning `pdf_pages_without_text`, so a cover image page does not reject a book.
  - A password: `import.error.drm`.
  - A broken file: `import.error.unreadable`.
- **Metadata:** `/Title`, `/Author` and `/Lang`. Without a language, the detector runs as for other formats. Reading reports per-page progress on the job.
- **Fixed in passing:** ticket 06 pinned `charset-normalizer==3.5.2`, but the frozen GPU constraints pin 3.5.1, which would have broken the image build. It is now 3.5.1, and the TXT tests pass on it.

Acceptance, checked by `tests/test_pdf_import.py` (15 tests; `tests/pdfs.py` writes small PDFs by hand, as the fixture's builder does):

- **`hard-two-column.pdf`:** both chapters' paragraphs are **exactly** the source passages, 42 and 31 of them. So the columns are in order, no running header or page number is left, and all 60 line-end hyphens are resolved. The warnings say headers and page numbers were removed on 4 pages.
- **Images only:** a PDF made only of images is rejected with the scanned-PDF message, through the API as well.
- **Other tests:** header removal (including a header holding the page number), de-hyphenation (removed, kept for a known compound, kept before a capital), chapters from patterns, from large headings and from bookmarks, italics, a password, and a cover page without text.

Not checked: a real typeset novel PDF (none among the samples). Footnotes, drop caps and tables are not handled specially.
