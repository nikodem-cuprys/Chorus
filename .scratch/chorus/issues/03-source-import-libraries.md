# Libraries for importing EPUB, MOBI, text PDFs and AO3 into one Work structure

Type: research
Status: resolved
Blocked by: none

## Question

Which free Python libraries or tools best turn each Source format into a clean Work (chapters and paragraphs, italics and emphasis preserved, headers, footers and page numbers removed)? Cover EPUB (e.g. ebooklib), MOBI and AZW3 (e.g. `mobi`, Calibre `ebook-convert`), text-layer PDF (e.g. PyMuPDF, pdfplumber; chapter detection, de-hyphenation), and AO3 (downloading a work's official EPUB or HTML export by URL: AO3 terms of service, rate limits, adult-content and login-locked works, series). Also: which licenses allow bundling in a Docker image, and what shared Work structure all importers should produce.

## Answer

- **EPUB:** a thin reader of our own (stdlib `zipfile` + `lxml`, BSD), following the EPUB 3.3 spine and nav/NCX. EbookLib is AGPL, so it is avoided.
- **MOBI/AZW3:** Calibre `ebook-convert` (GPL-3.0) run as a subprocess to make an EPUB. Out-of-process use makes it an aggregate, so bundling it is fine.
- **PDF:** `pdfplumber` (MIT) plus `pypdf` (BSD) for bookmarks. Header/footer, de-hyphenation and chapter heuristics are our own code. PyMuPDF is better but AGPL.
- **AO3:** one user-initiated GET of `/works/<id>?view_adult=true&view_full_work=true` (allowed by robots.txt, which disallows `/downloads/`), with backoff on 429. Restricted works go through the upload path. The ToS bans commercial use and scraping to commercialize.
- All importers produce one shared Work (chapters, Blocks, Spans with italic/bold marks, with notes kept separate).

Details: [research/source-import-libraries.md](../research/source-import-libraries.md)
