# MOBI, AZW3 and other formats through Calibre

Type: task (AFK)
Status: ready-for-agent
Blocked by: 02, 05

## What to build

Every format that is not EPUB, PDF or TXT goes through Calibre's `ebook-convert`, run as a separate process into an EPUB, which the EPUB reader then reads.

- Formats: MOBI, AZW, AZW3 and anything else Calibre takes as input (DOCX, FB2, RTF, HTML, ODT and so on).
- The Source kind is recorded as the original format, not EPUB.
- A DRM-protected Kindle file is rejected with the DRM message (Calibre's error is recognised, not shown raw).
- A format Calibre cannot read is rejected with a clear message.
- A time limit on the conversion, with a clear failure.

## Acceptance criteria

- `alice-gutenberg.azw3` and `alice-gutenberg.mobi` in `.scratch/chorus/samples/import/` import with the same chapters and text as each other.
- A DOCX made for the test imports with its headings as chapters and its italics kept.
- An encrypted file gets the DRM message.

## Spec

`docs/spec/03-pipeline.md` (Import).
