# Milestones

Nine milestones, each usable on its own. "Shown" is what the milestone can be demonstrated doing. Every milestone is judged by listening on the sample passages in `.scratch/chorus/samples/` and by importing its fixtures.

## M1 — Automatic path

**Shown:** import a file, get a multi-voice Audio drama with no review, play it in the browser and export it as MP3 and M4B with chapters.

- **Packaging:** Docker Compose (web, worker, Redis, PostgreSQL) from one image on the frozen stack; models downloaded on first run with progress; the startup health check.
- **Sources:** every file format except AO3. Chorus's own readers for EPUB, text-layer PDF and TXT; MOBI, AZW3 and anything else Calibre converts go through `ebook-convert` to EPUB. TXT chapters from heading lines, else one chapter; blank-line runs or `***` become Section breaks. DRM and image-only PDFs rejected.
- **Language:** the English Language pack; a Work's language from metadata or the offline detector, changeable by the user; the notice for a Work without a pack.
- **Analysis:** approach B (Character list, then Speaker attribution with Emotion and intensity), without the second labelling run; the Narrating Character per chapter by majority of its chunks; kinds of text from markup only. An early build ticket runs the Character pass on a whole novel from `samples/raw/` and decides from the result how the list is trimmed to fit the prompt.
- **Text handling:** TXT encoding detection; chapter-heading patterns and sentence rules in the English Language pack; long lines voiced by sentence.
- **Casting:** auto-cast from the 12 built-in Voices, with the default Narrator and the Narrating Character rule.
- **Voicing and assembly:** Chatterbox with its two halves in turn; seeds per line; the fixed pauses from their start values; ticket 21's default handling of special text, without switches. Every Work goes straight from analysis to voicing.
- **Jobs:** full control from the start: resume after a crash, pause, resume, cancel without losing finished lines, progress over server-sent events. A novel takes about a day to voice.
- **Screens:** first run, import, a plain list of Works, the Work page with chapters, the job and plain chapter playback, and MP3/M4B export into the host folder.
- **Also:** interface text through the message catalogue, English only; localhost only; the watermark always on; the responsible-use note in the README.
- **Done when, in addition:** the split-loaded Chatterbox has been checked by ear on the sample passages, the six pause lengths have been tuned by ear on them, and the analysis stage has been shown to stay inside the card with a desktop attached (3.3 GB peak, about 190 MiB spare when measured).

**Left out on purpose:** AO3, review and correction, recasting, chapter editing, the special-text switches, pronunciation, the cover grid and the reading-view player, bookmarks, the phone layout and network access, Polish, Voice cloning, Update from Source, YouTube export and Publishing.

## M2 — AO3

**Shown:** import an AO3 work by URL, or from an uploaded AO3 download, with the summary and author notes recognised as such and skipped by default.

- The single-request URL fetch with backoff, the logged-in-only message, the AO3 upload parser, and the Work's "from AO3" mark.
- An updated AO3 work is imported again as a new Work until M7.

## M3 — Review and correction

**Shown:** fix wrong Speakers and Emotions, then regenerate only those lines.

- The reading view (text, line editor, cast panel, top bar, Changes panel) and the question queue, fed by the queue rules and the second labelling run. The second run joins analysis here; a Work analysed in M1 or M2 gets it the first time the user opens Review.
- The setting "wait for my review before voicing" (global and per Work, off by default) and the "ready for review" state.
- Corrections at the four scopes, with pinning; a new analysis keeps pinned values.
- Regenerate and New take, with the previous take kept and restorable; old audio marked while waiting; exports flagged outdated; corrections during a running job.
- Add and merge Characters; recast any Character or the Narrator among the built-in Voices; set a chapter's Narrating Character, or separate the Narrator from it.
- Add and remove Section breaks; split a chapter at a line, merge two chapters, edit a chapter title.
- The special-text switches per Work, with global defaults; mark a passage not voiced or change its kind.

## M4 — Pronunciation

**Shown:** the per-Work pronunciation list with candidates; try a Respelling, save it, and every line containing the word is re-voiced.

## M5 — Library and player

**Shown:** comfortable listening, including on a phone.

- Cover grid with search and sort; the Work page in full.
- The reading view as the player: spoken line highlighted, click to play, position saved per Work as a line, bookmarks with a note, the previous take playable.
- The phone layout of the Library, the Work page and the player, and opening Chorus to the network with a single password.
- Polish filled into the message catalogue, and the completeness test switched on from here.

## M6 — Voice cloning

**Shown:** clone a Voice from a user-supplied clip, label it, and assign it to a Character or the Narrator.

## M7 — Update from Source

**Shown:** re-import a changed Source (a new file, or the AO3 page fetched again), keeping unchanged chapters and pinned corrections.

## M8 — YouTube export

**Shown:** one video per chapter with a cover carrying the title text, the upload checklist, the AI-voice line, pasted video links, and "outdated" flags after regeneration.

- The ticket 10 items that matter here: the one-time permission warning, the AO3 commercial-use line, and the global switch to turn the watermark off.

## M9 — Publishing (final)

**Shown:** connect a Google Cloud project, upload a Work with one click into a playlist, and see the YouTube dashboard. Old videos are never deleted.

- The Connect wizard with both scopes and the audit setting; the private-lock notice; the synthetic-content flag per Work and the own-voice question; upload, playlist, thumbnails, quota waits; replacement after regeneration; the statistics refresh and the YouTube page.
