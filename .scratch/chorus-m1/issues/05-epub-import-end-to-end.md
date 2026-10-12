# EPUB import into a Work, end to end

Type: task (AFK)
Status: ready-for-agent
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
