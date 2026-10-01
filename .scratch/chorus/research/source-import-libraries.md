# Source import: libraries per format, AO3 rules, and a shared Work structure

Research for ticket [03-source-import-libraries](../issues/03-source-import-libraries.md). Read on 2026-09-29. Versions and dates are from PyPI/GitHub on that day.

## TL;DR

| Source | Recommended | License | Why |
|---|---|---|---|
| EPUB (2 and 3) | Own thin reader: stdlib `zipfile` + `lxml` (or `beautifulsoup4`), following the EPUB 3.3 spec (container.xml, then OPF spine, then nav/NCX) | lxml BSD-3-Clause, bs4 MIT | EbookLib, the usual choice, is **AGPL-3.0**. EPUB reading needs only a small part of it. |
| MOBI / AZW3 (KF8) | Calibre `ebook-convert` run as a **subprocess** (MOBI/AZW3 to EPUB), then the EPUB reader | GPL-3.0 (a separate program, so the image is an aggregate) | Most mature converter, handles mobi7 and KF8. AO3 itself uses it to build its downloads. |
| MOBI (lighter alternative) | `mobi` 0.4.1 (KindleUnpack fork) | GPL-3.0-only | Works in-process, so a Python import makes Chorus a combined GPL work. Use it only if Chorus is GPL/AGPL. |
| Text-layer PDF | `pdfplumber` 0.11.10 (on `pdfminer.six`), with `pypdf` 6.19 for the outline/bookmarks | MIT / MIT / BSD-3-Clause | Gives per-character font name, size and position, which lets us detect italics, headers/footers and headings. De-hyphenation and chapter detection are our own code. |
| PDF (if AGPL is acceptable) | PyMuPDF 1.28.2 | AGPL-3.0 or a paid Artifex licence | Faster, has built-in `TEXT_DEHYPHENATE` and an italic span flag. Its licence clashes with "monetization may happen later". |
| AO3 by URL | `httpx`/`requests` + `lxml`: one GET of `/works/<id>?view_adult=true&view_full_work=true`, parsed as HTML | BSD / Apache-2.0 | This path is allowed by robots.txt. The official `/downloads/` path is `Disallow`ed for every user agent. |
| AO3 by upload | AO3's own EPUB (the EPUB reader) or HTML download (the AO3 HTML parser) | n/a | Covers restricted (login-only) works without Chorus handling AO3 credentials. |

Licence rule of thumb for the Docker image: anything **imported into Chorus's Python process** must be permissive (MIT/BSD/Apache) unless Chorus itself is released under GPL/AGPL. GPL **command-line tools run via exec/pipes** (Calibre) are separate programs and can ship in the same image as an aggregate.

## Licensing and bundling

- GNU GPL FAQ, "MereAggregation": separate programs shipped together form an aggregate, allowed even next to non-free code. Communicating "via exec, pipes" suggests separate programs. Sharing an address space suggests one combined work. [gnu.org/licenses/gpl-faq.html](https://www.gnu.org/licenses/gpl-faq.html)
- Same FAQ, on interpreters: a program that uses GPL libraries or modules "must be released under a GPL-compatible license". A Python `import` of a GPL or AGPL package therefore puts Chorus under GPL-compatible terms. [gnu.org/licenses/gpl-faq.html](https://www.gnu.org/licenses/gpl-faq.html)
- Licences checked:
  - EbookLib 0.20 (2025-10-26): AGPLv3+. [pypi.org/project/EbookLib](https://pypi.org/project/EbookLib/), [github.com/aerkalov/ebooklib](https://github.com/aerkalov/ebooklib)
  - PyMuPDF 1.28.2 (2026-08-06): AGPL-3.0, or a commercial licence from Artifex. [pypi.org/project/PyMuPDF](https://pypi.org/project/PyMuPDF/)
  - mobi 0.4.1 (2025-09-14): GPL-3.0-only. [pypi.org/project/mobi](https://pypi.org/project/mobi/), [github.com/iscc/mobi](https://github.com/iscc/mobi)
  - Calibre: GPL-3.0. [github.com/kovidgoyal/calibre](https://github.com/kovidgoyal/calibre)
  - pdfplumber 0.11.10 (2026-06-15): MIT. [pypi.org/project/pdfplumber](https://pypi.org/project/pdfplumber/)
  - pdfminer.six 20260107: MIT. [pypi.org/project/pdfminer.six](https://pypi.org/project/pdfminer.six/)
  - pypdf 6.19.0 (2026-09-16): BSD-3-Clause. [pypi.org/project/pypdf](https://pypi.org/project/pypdf/)
  - pypdfium2 5.13.0: BSD-3-Clause / Apache-2.0. [pypi.org/project/pypdfium2](https://pypi.org/project/pypdfium2/)
  - beautifulsoup4 4.15.0: MIT. [pypi.org/project/beautifulsoup4](https://pypi.org/project/beautifulsoup4/)
  - lxml: BSD-3-Clause. [github.com/lxml/lxml](https://github.com/lxml/lxml)
- The ticket asks for commercially usable picks. Everything recommended above is permissive except Calibre, which stays out-of-process. If the architecture ticket (11) chooses to release Chorus under AGPL, EbookLib and PyMuPDF become options and would save code.

## EPUB

- The format is simple enough to read directly. `META-INF/container.xml` has a `rootfile` that points to the package document (EPUB 3.3 §4.2.6.3.1). The package's **spine** "defines ... the default reading order" (§5.7). The **navigation document** (`nav epub:type="toc"`, §7.4.2) gives chapter titles. EPUB 2 **NCX** is a deprecated legacy feature that reading systems still support (§5.9.5), so it is the fallback when there is no nav. [w3.org/TR/epub-33](https://www.w3.org/TR/epub-33/)
- Proposed reader:
  1. Walk the spine.
  2. Map TOC entries (href plus fragment) to chapter boundaries. When there is no usable TOC, fall back to one chapter per spine item, or to split points at `h1`/`h2`.
  3. Turn the XHTML into Blocks: `p`, headings, `blockquote`, `hr` or scene-break markers.
  4. Keep inline `em/i/strong/b/u/s` as emphasis spans, and drop images.
- EbookLib (AGPLv3+) handles EPUB2 and EPUB3, spine and TOC. [pypi.org/project/EbookLib](https://pypi.org/project/EbookLib/) It only saves the zip/OPF parsing and brings AGPL with it. It is not recommended unless Chorus is AGPL.
- DRM-protected EPUBs are out of scope. Detect `META-INF/encryption.xml` and reject with a clear message. (This is spec-level knowledge. Rejecting is a proposal, not a sourced requirement.)

## MOBI and AZW3

- Calibre `ebook-convert` lists MOBI, AZW, AZW3 and AZW4 as inputs and can output EPUB 2 or 3 (`--epub-version`). [manual.calibre-ebook.com ebook-convert](https://manual.calibre-ebook.com/generated/en/ebook-convert.html) Pipeline: `ebook-convert in.azw3 out.epub`, then the EPUB reader. Only one reader of structure has to be maintained.
- `mobi` (KindleUnpack fork) unpacks **unencrypted** mobi7 and KF8/AZW3 to EPUB, HTML or PDF, with no DRM support. [github.com/iscc/mobi](https://github.com/iscc/mobi) It is lighter than Calibre but GPL in-process.
- Neither tool removes DRM, and Chorus should not. Kindle Store files are usually DRM-protected, so expect "cannot import encrypted file" to be a common error.
- Risk to verify in a prototype or the Docker ticket (05): Calibre is large and depends on Qt. Check that `ebook-convert` runs headless in the image and measure how much it adds to the image size. (Not measured here.)

## Text-layer PDF

- `pdfplumber` exposes each character's `fontname`, `size`, `upright` and coordinates, and `extract_words(extra_attrs=["fontname","size"])`. [pypi.org/project/pdfplumber](https://pypi.org/project/pdfplumber/) `pdfminer.six` supplies font, colour and exact position. [pypi.org/project/pdfminer.six](https://pypi.org/project/pdfminer.six/)
- None of the permissive libraries give clean prose out of the box. These heuristics are Chorus code:
  1. **Headers, footers and page numbers:** drop lines in the top and bottom page bands whose normalised text, with digits stripped, repeats across many pages, plus lines that are only a number or roman numeral. Calibre's PDF input has the same idea as `--pdf-header-skip/--pdf-footer-skip` and the regex options. [manual.calibre-ebook.com ebook-convert](https://manual.calibre-ebook.com/generated/en/ebook-convert.html)
  2. **Italics:** the font name contains `Italic`/`Oblique`/`-It`, or the characters are not upright. PyMuPDF's docs warn that flags taken from font metadata "may not always be accurate", and the same applies here. [pymupdf vars](https://pymupdf.readthedocs.io/en/latest/vars.html)
  3. **Paragraphs:** rebuild them from line spacing and first-line indent, and join lines across page breaks.
  4. **De-hyphenation:** a line that ends in `-` and is followed by a lowercase start is joined. Keep the hyphen when the joined word is not in a wordlist but both halves are, as in "well-known". PyMuPDF's `TEXT_DEHYPHENATE` only "ignore[s] hyphens at line ends and join[s]". [pymupdf vars](https://pymupdf.readthedocs.io/en/latest/vars.html)
  5. **Chapters:** use the PDF outline (bookmarks via `pypdf`) first. Otherwise, lines whose font size is well above body size, or that match `^(chapter|part|prologue|epilogue)\b` / roman numerals (English-first; the patterns should be per-language).
- Pages with no text layer are OCR territory, which the map puts out of scope. Detect them and reject. pypdfium2 (permissive) is a faster text engine, but its helpers do not expose per-character font info. [pypi.org/project/pypdfium2](https://pypi.org/project/pypdfium2/)
- PDF import quality is the most likely to disappoint. It deserves real sample files in ticket 06.

## AO3

Primary sources: the AO3 ToS and TOS FAQ, read from the OTW's own source repo because `archiveofourown.org/tos` and `/faq` returned HTTP 525 to every fetch today. The text is in `config/locales/views/en.yml` and `app/views/home/tos_faq.html.erb` of [github.com/otwcode/otwarchive](https://github.com/otwcode/otwarchive), plus the live `robots.txt` and the admin post on data scraping. The "Downloading Fanworks" FAQ could not be reached, so its wording is not quoted.

**What the rules say**

- ToS I.F "What you can't do" (effective 19 Nov 2024) forbids using AO3 "to conduct any commercial activity, whether for direct or indirect commercial advantage, including ... scraping Content in order to commercialize it", and "to interfere with or disrupt AO3".
- TOS FAQ, "Do you have a policy on bots or scraping?": "The use of bots or scraping for spam, commercial promotion, or other purposes that violate our policies is forbidden. This includes scraping AO3 for the purposes of obtaining material for commercial generative AI or creating an app that hosts or paywalls AO3 content. The use of bots or scraping for purposes that do not violate our policies is generally allowed. However, we reserve the right to implement robots.txt or other protocols limiting what bots can do ... [and] may also ban specific bots."
- The admin post "AI and Data Scraping on the Archive" says AO3 uses "technical measures to hinder large-scale data scraping on AO3, such as rate limiting", and that there is no policy "against responsible data collection". No thresholds are published. [archiveofourown.org/admin_posts/25888](https://archiveofourown.org/admin_posts/25888) Our own requests saw `429 Too Many Requests` and 525 errors from AO3's front end today, so expect throttling.
- `robots.txt` (live), for `User-agent: *`: `Disallow: /works?`, `/downloads/`, `/autocomplete/`, `/external_works/` and the search URLs. It also blocks GPTBot, ChatGPT-User and CCBot completely. [archiveofourown.org/robots.txt](https://archiveofourown.org/robots.txt)

**How downloads work** (from the source)

- **Formats:** the route is `downloads/:id/:download_title.:format`, and the controller serves `html, pdf, mobi, epub, azw3`. EPUB, MOBI, AZW3 and PDF are made by Calibre `ebook-convert` from AO3's own HTML. Chapters are marked by fixed XPaths: `div#chapters > h2.toc-heading` for single-chapter works, `div#chapters > div.meta.group > h2.heading` for multi-chapter ones, and `div#preface` / `div#afterword`. Series title and index are written as Calibre series metadata. So AO3 EPUB and HTML have a **stable, known layout**, and the preface, chapter notes and afterword can be told apart from the story text. (`app/controllers/downloads_controller.rb`, `app/models/download_writer.rb`, `config/routes.rb`)
- **What cannot be downloaded:** drafts, works hidden by an admin, and works in unrevealed collections. Admins can turn downloads off site-wide. (`downloads_controller.rb`)
- **Restricted works:** `check_visibility` sends logged-out users to the login page (`application_controller.rb`). Getting one by URL would mean Chorus holding the user's AO3 session or password.
- **Adult works:** passing `view_adult=true` on the work page sets the `view_adult` cookie and skips the adult-content interstitial. `view_full_work=true` puts every chapter on one page. (`works_controller.rb#show`)
- **Series:** no series download route exists. Importing a series means reading `/series/<id>` and then one request per work.

**Constraints proposed for Chorus**

1. Import by URL is user-initiated and fetches **one work** with one request, `GET /works/<id>?view_adult=true&view_full_work=true`, sent under an honest User-Agent that names Chorus.
   - That URL is not matched by robots.txt, while `/downloads/` is. Parse the page with the same selectors AO3's own converter relies on.
   - No crawling, search or background refresh.
2. On 429 or 5xx, back off and honour `Retry-After`. Retry a few times, then fail with "AO3 is busy, try later or upload the download instead". Space the works of a series import several seconds apart, and ask for confirmation first.
3. Restricted works: do **not** collect AO3 passwords. Show "this work is for logged-in users only: download it from AO3 (EPUB or HTML) and upload it". Accepting a session cookie from the user is possible, but it is an open question and not recommended.
4. Upload path: detect AO3 EPUB/HTML by `publisher = Archive of Our Own` and the `#preface/#chapters/#afterword` structure, then use the AO3 parser so author notes, summary and tags are kept as metadata and kept out of the story text.
5. **Commercial use:** Publishing an AO3 work to a monetized YouTube channel would fall under "commercial activity ... for direct or indirect commercial advantage", and apps that "host or paywall AO3 content" are named as forbidden. This goes to ticket 10 (permissions and consent) and the Publishing spec. It is a separate question from the author's copyright and podfic permission.

## Proposed shared Work structure

Every importer produces the same value, and nothing downstream knows the Source format. Emphasis is kept as inline spans because Emotion and delivery analysis may use it: italics often mark inner thoughts, and emphasis marks stress.

```python
@dataclass
class Work:
    title: str
    authors: list[str]
    language: str            # BCP-47, e.g. "en"; from metadata, else detected
    source: SourceInfo       # kind: epub|mobi|azw3|pdf|ao3_url|ao3_upload; filename or URL; imported_at; content hash
    metadata: dict           # summary, tags, series {title, index}, rating, warnings (AO3), publisher, pubdate
    front_matter: list[Block]  # AO3 preface notes, epigraph, dedication: kept, but not narrated by default
    chapters: list[Chapter]
    back_matter: list[Block]   # afterword and end notes
    warnings: list[str]        # import problems: "headers removed on 212 pages", "no TOC, split by headings"

@dataclass
class Chapter:
    index: int
    title: str | None
    notes_before: list[Block]  # AO3 chapter notes and summary
    blocks: list[Block]
    notes_after: list[Block]

@dataclass
class Block:
    kind: Literal["paragraph", "heading", "scene_break", "blockquote", "letter", "list_item", "footnote"]
    spans: list[Span]          # empty for scene_break
    source_ref: str            # e.g. "OEBPS/ch03.xhtml#p12" or "pdf:p41" for tracing back and regenerating

@dataclass
class Span:
    text: str
    marks: set[Literal["italic", "bold", "underline", "strike", "small_caps", "superscript"]]
```

Design notes:

- Blocks and Spans are plain text plus marks, not HTML, so analysis and TTS never parse markup. Scenes are left out: they are an analysis result. A `scene_break` Block is a strong hint for Scene detection.
- Author notes, summaries and epigraphs are kept, but separately from `blocks`. This is where the "Special text" item on the map ("Not yet specified") decides what is narrated.
- `source_ref` and the content hash support "regenerate one line" and re-importing an updated AO3 work (chapters added).
- Each importer is a function `import_x(path_or_url) -> Work`. Calibre-backed formats go through `to_epub`, then `import_epub`.

## Open questions and follow-ups

- **Docker (ticket 05):** Calibre headless in the image, and its size. The alternative is `mobi` in-process if Chorus is GPL.
- **Architecture (ticket 11):** Chorus's own licence (permissive, GPL or AGPL) decides whether EbookLib, PyMuPDF and `mobi` can be imported.
- **Permissions (ticket 10):** the AO3 ToS ban on commercial use conflicts with future monetization and with YouTube Publishing of AO3 works.
- **Samples (ticket 06):** include a hard PDF (running headers, hyphenation, drop caps), an AO3 EPUB with notes, and an AZW3.
- DRM-protected files are rejected, never decrypted. This is worth writing into "Out of scope".
- Not verified: the wording of AO3's "Downloading Fanworks" FAQ (site unreachable), and whether AO3 allows a restricted work's download URL without a session. The controller does no per-user check, but nginx may; this was not tested and should not be relied on.
