# MOBI, AZW3 and other formats through Calibre

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-13: `backend/chorus/importing/calibre.py`. Checked against the real Calibre 7.6.0 in the Chorus image.

- **Route:** every upload that is not `.epub`, `.pdf` or `.txt` is written to a temporary folder **with its own extension** (Calibre picks the input format from it). `ebook-convert source.<ext> converted.epub` runs as a separate process, with `QT_QPA_PLATFORM=offscreen`, in its own process group. The EPUB reader then reads the result.
- **Source kind:** the original extension (`mobi`, `azw3`, `docx`…), not EPUB. A file with no extension is rejected without running Calibre.
- **Calibre's output is recognised, never shown raw:**
  - `DRMError` or "locked with/by DRM": `import.error.drm`.
  - "No plugin to handle input format": `import.error.unsupported_format`.
  - Any other failure, or no EPUB written: `import.error.conversion_failed` (Calibre's log stays in the exception for the worker's log).
  - No `ebook-convert`: `import.error.converter_missing`.
- **Time limit:** `CHORUS_CALIBRE_TIMEOUT_SECONDS`, 600 by default. Past it, the whole process group is killed and the import fails with `import.error.conversion_timeout`. The program path is `CHORUS_EBOOK_CONVERT`, which the startup check now uses as well.
- **Found with the real conversion:** an EPUB that Calibre makes from a MOBI loses Gutenberg's `#pg-header` and `#pg-footer` ids. The licence's first paragraphs then stayed in the last chapter of the MOBI import but not the AZW3 one.
  - The EPUB reader now also recognises Gutenberg's `*** START OF` and `*** END OF` lines by their text, as the TXT reader does; the patterns moved to `chorus.importing`.
  - Removing a header no longer drops the table-of-contents markers inside it.
- **Frontend:** the Import screen accepts any file, and the catalogue has the new messages.

Acceptance, checked on the stack (`tests/integration/test_calibre.py`, `CHORUS_STACK_URL=http://localhost:8000`):

- **`alice-gutenberg.azw3` and `alice-gutenberg.mobi`:** both import with the same 12 chapter titles and word-for-word the same chapter text.
- **DOCX:** a DOCX built by the test (a title, two "Heading 1" chapters, italic runs) imports as chapters "Chapter 1" and "Chapter 2", with "stormy" and "over" kept as italics.
- **Encrypted file:** the Alice MOBI with its header's encryption field set to Mobipocket DRM gets the DRM message.
- **Unreadable format:** a `.xyz` file gets the unreadable-format message.
- **Unit tests:** `tests/test_calibre_import.py` (8 tests) cover each outcome with a stand-in `ebook-convert`, including the time limit stopping a hung conversion.

Not checked: a real DRM-protected Kindle file from a shop (none available). The MOBI with its encryption flag set is what Calibre's DRM check reads.
