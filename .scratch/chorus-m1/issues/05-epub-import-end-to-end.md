# EPUB import into a Work, end to end

Type: task (AFK)
Status: resolved
Blocked by: 01, 04

## What to build

The first vertical slice: upload an EPUB in the browser and see the Work.

- The shared Work structure in the database: Work, chapters, blocks (paragraph, heading, Section break, block quotation, letter, list item, footnote) made of spans with marks, notes before and after each chapter, front and back matter, metadata, cover, import warnings, and a stored copy of the Source.
- The EPUB reader on `zipfile` and `lxml`: container, spine, nav (NCX as fallback); chapters from the table of contents, else one per spine item or split at `h1`/`h2`; marks kept; images dropped; the cover kept.
- DRM-protected EPUBs (`META-INF/encryption.xml`) rejected with a clear message.
- The language from metadata, else from `lingua-py`; base language only. The Work page shows it and lets the user change it. A language with no pack shows the notice that the English pack will be used.
- The import job runs on the `other` queue.
- Screens: Import (upload), the plain list of Works (title, author, state), and the Work page with the chapter list and each chapter's text.

## Acceptance criteria

- The clean Gutenberg EPUB and the synthetic AO3-layout EPUB in `.scratch/chorus/samples/` import with the right chapters, titles and italics.
- An EPUB containing `encryption.xml` is rejected with the DRM message.
- Changing the language to one without a pack shows the notice; changing it back to English removes it.
- Importer tests run against the sample fixtures.

## Spec

`docs/spec/03-pipeline.md` (Import), `docs/spec/05-data-model.md` (Work, Chapter), `docs/spec/06-screens.md` (Import, Library, Work page).

## Answer

Built on 2026-10-13.

- **Work structure:** `work` and `chapter` tables (migration 0003; `job.work_id` is now a foreign key). Blocks are JSON lists of `{type, spans: [{text, marks}], level?, ref}`. `ref` points back to the Source file and element path. Front and back matter are block lists on the Work. Notes before and after are columns on Chapter, empty until AO3's parser (M2). The Source copy and the cover are stored in `data/works/<id>/`. The readers build the shared `chorus.importing.ImportedWork`.
- **EPUB reader (`chorus/importing/epub.py`):** reads the container, the spine (linear documents only), the nav document or else the NCX `navMap`, and the metadata (title, authors, language, publisher, date, description, subjects, Calibre and EPUB 3 series). The cover comes from `cover-image`, else `<meta name="cover">`. The documents are walked into one stream of blocks with markers where each TOC entry points, and the stream is cut there.
- **Front and back matter:** TOC entries before the first one whose heading or label matches the pack's chapter-heading patterns are front matter; entries after the last match are back matter. Gutenberg's `#pg-header` and `#pg-footer` are always front and back matter. A segment holding nothing but headings (a part title page) joins the next chapter. The title is the chapter's leading heading text, else the TOC label.
- **Dropped:** images, figures and their captions, page-number spans, and footnote-reference links such as "[1]". Soft hyphens are removed.
- **No usable TOC:** the book is split at `h1`/`h2` when a document has more than one of them, else one chapter per spine document. Either way, a warning is shown.
- **DRM:** `META-INF/encryption.xml` is rejected with `import.error.drm`, **except** when every encrypted file is a font under the IDPF or Adobe font-obfuscation algorithm. That is not DRM, and DRM-free retail EPUBs often have it.
- **Language:** `dc:language` reduced to the base language. Without one, `lingua-language-detector` 2.1.1 (all languages, low-accuracy mode) runs on the first 1,500 words. `PATCH /api/works/{id}` sets it by hand. `GET /api/languages` lists the detector's languages with `has_pack`. The Work page names languages through the browser's `Intl.DisplayNames`, and shows the "English pack is used" notice when there is no pack.
- **Job:** `import` on the `other` queue. An expected failure raises `JobFailed`/`ImportRejected`, which marks the job and the Work failed with a catalogue message and no traceback. Unexpected errors still raise.
- **Screens:**
  - **Library:** a plain list of title, author and state, plus jobs and Voices.
  - **Import:** file upload, then go to the Work page.
  - **Work page:** cover, title, author, state, language selector with the notice, error, warnings, the chapter list with word counts, front and back matter, and each part's text with marks.
  - **Routing:** a small History-API router (`frontend/src/router.tsx`).

Acceptance, checked:

- **Gutenberg EPUB:** 61 chapters, "Chapter I." to "CHAPTER LXI.". Illustration captions are dropped from the headings. Italics are kept, for example "“*You* want to tell me". Gutenberg's header, the preface and the list of illustrations are front matter; the licence is back matter. No warnings.
- **AO3-layout EPUB:** chapters "Chapter 1: Transformed" and "Chapter 2: The Door", italics kept, the preface is front matter and the afterword back matter. `is_ao3` is set from the publisher.
- **`encryption.xml`:** an EPUB with AES or Adobe ADEPT encryption fails with the DRM message, on both the Work and the job.
- **Language notice:** setting `pl` gives `has_language_pack: false` and shows the notice (frontend test). Setting `en` again removes it.
- **Tests:** `tests/test_epub_import.py` (19 tests, against the sample fixtures and small EPUBs built in the test) and frontend tests for the block renderer and the Work page.
- **Real server:** uvicorn on SQLite with in-process jobs (Docker was not running). Uploading both samples with curl imports them, `/works/1` serves the app, and the cover and chapters are served. The pages were **not** looked at in a browser: the Chrome extension was not connected.

Left for later or noted:

- **AO3 notes:** chapter notes, the summary and the end notes stay as ordinary blocks inside chapters, front and back matter, until AO3's parser (M2). In M1 they would be voiced as part of a chapter.
- **Typos in headings:** titles are kept as the Source writes them, including Gutenberg's typo "CHAPTERXXVII.". The Work's state rests at `imported` until ticket 11 chains analysis after import.
- **Detector memory:** lingua loads lazily and only when metadata has no language, once per worker process.
