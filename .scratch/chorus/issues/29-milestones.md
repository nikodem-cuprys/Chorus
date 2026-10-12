# Milestones: the build order

Type: grilling
Status: resolved
Blocked by: 24, 25, 26, 27, 28

## Question

Break the build into milestones, each one usable on its own and ready to split into build tickets. Known fixed points: English first; review is optional, so a fully automatic path from Source to Audio drama comes before the review screen; YouTube export comes before one-click Publishing, which is the final milestone (ticket 12). Decide the order of the rest (importers one by one or together, analysis, voicing, the Library and player, review and correction, pronunciation, Export to MP3 and M4B, Voice cloning, Update from Source, the phone layout), what each milestone can be shown doing, and what is deliberately left out of the first one.

## Answer

Chosen by the user on 2026-10-12, in a grilling session. Nine milestones, each usable on its own. "Shown" is what the milestone can be demonstrated doing.

**M1 — Automatic path**
- Shown: import a file, get a multi-voice Audio drama with no review, play it in the browser and export it as MP3 and M4B with chapters.
- Sources: every file format except AO3. Chorus's own readers for EPUB, text-layer PDF and TXT; MOBI, AZW3 and anything else Calibre can convert (DOCX, FB2, RTF, HTML, ODT…) go through `ebook-convert` to EPUB. TXT chapters come from lines that look like chapter headings ("Chapter 12", "CHAPTER XII", "Part One", a lone number); with none, the whole file is one chapter. Runs of blank lines or `***` become Section breaks.
- Pipeline: English Language pack, language from metadata or the offline detector, the notice for a Work without a pack; analysis by approach B; auto-cast from the 12 built-in Voices; voicing with Chatterbox's two halves loaded in turn (ticket 25). Ticket 21's default handling of special text, without the switches.
- Jobs: full control from the start — resume after a crash, pause, resume, cancel without losing finished lines, progress (chapter, line count, percentage, time left) over server-sent events. A novel takes about a day to voice.
- Screens: a plain list of Works; a Work page with chapters, the job and plain chapter playback.
- Also: Docker Compose, models downloaded on first run with progress; interface text through the message catalogue, English only; localhost only; Chatterbox's watermark always on; the responsible-use note in the README.
- Done when, in addition: the split-loaded Chatterbox has been checked by ear on the sample passages, and the analysis stage has been shown to stay inside the card with a desktop attached (ticket 24: 3.3 GB peak, about 190 MiB spare).

**M2 — AO3**
- Shown: import an AO3 work by URL or from an uploaded AO3 download, with author notes and summaries recognised as such. An updated AO3 work is imported again as a new Work until M7.

**M3 — Review and correction**
- Shown: fix wrong Speakers and Emotions, then regenerate only those lines.
- The reading view, the review queue (ticket 18), corrections at the four scopes with pinning (ticket 09), Regenerate and New take with the previous take kept (ticket 22), old audio marked while waiting and exports flagged outdated (ticket 20).
- Add and merge Characters; recast any Character among the built-in Voices.
- Add and remove Section breaks; split a chapter at a line, merge two chapters, edit a chapter title (needed because heading detection on TXT and PDF will sometimes be wrong).
- Ticket 21's per-Work switches with global defaults; mark a passage not voiced or change its kind.

**M4 — Pronunciation**
- Shown: the per-Work pronunciation list with candidates, try a Respelling, save it, and every line containing the word is re-voiced (ticket 19).

**M5 — Library and player**
- Shown: comfortable listening, including on a phone.
- Cover grid with search and sort; the reading view as the player (spoken line highlighted, click to play, position saved per Work, bookmarks with a note, the previous take playable).
- The phone layout of the player, and opening Chorus to the network with a single password.
- Polish filled into the message catalogue, and the completeness test turned on from here.

**M6 — Voice cloning**
- Shown: clone a Voice from a user-supplied clip and assign it to a Character or the Narrator.

**M7 — Update from Source**
- Shown: re-import a changed Source, keeping unchanged chapters and pinned corrections.

**M8 — YouTube export**
- Shown: one video per chapter with a cover carrying the title text, the upload checklist, the AI-voice line, pasted video links and "outdated" flags after regeneration (ticket 12).
- The ticket 10 items that matter here: the one-time permission warning, the AO3 commercial-use line, the synthetic-content flag per Work, and the global switch to turn the watermark off.

**M9 — Publishing (final)**
- Shown: connect a Google Cloud project, upload with one click, see the dashboard of ticket 27. Old videos are never deleted.

**Deliberately left out of M1:** AO3, review and correction, recasting, chapter editing, the special-text switches, pronunciation, the cover grid and reading-view player, bookmarks, the phone layout and network access, Polish, Voice cloning, Update from Source, YouTube export and Publishing.

**Amends earlier tickets:**
- Ticket 03 / the map's import list: TXT and every Calibre-convertible format are Sources too.
- Ticket 28: the catalogue is in the first build, but Polish and its completeness test arrive in M5, not the first build.

Placed by Claude without a separate question and accepted with the plan: first-run model download in M1; exports flagged outdated in M3.
