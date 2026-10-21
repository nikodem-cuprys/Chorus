# Pipeline

From Source to Published Audio drama, in order. The default path runs every stage up to the Audio drama without asking anything; review, export and Publishing are started by the user.

```
Source ──import──▶ Work ──analysis──▶ Script ──casting──▶ Voices ──voicing──▶ line audio ──assembly──▶ chapter audio
                                        ▲                                                                   │
                                        └──────── review and correction (optional) ── Regenerate ◀──────────┤
                                                                                                            ▼
                                                                    MP3 / M4B export · YouTube export · Publishing
```

## Import

Every importer produces the same Work, and nothing downstream knows the Source format.

**Shared Work structure:** title, authors, language, Source details (kind, file name or URL, time of import, content hash), metadata (summary, tags, series and index, rating and warnings for AO3, publisher, publication date), a cover image if the Source has one, front matter, chapters, back matter, and import warnings (such as "headers removed on 212 pages" or "no table of contents, split by headings"). Each chapter has an index, a title (or none), notes before, blocks and notes after. A block is a paragraph, heading, Section break, block quotation, letter, list item, footnote, epigraph or verse, made of text spans carrying marks (italic, bold, underline, strike, small capitals, superscript) and a reference back to where it came from in the Source. Blocks are plain text with marks, never HTML.

| Source | How |
|---|---|
| EPUB 2 and 3 | Chorus's own reader on `zipfile` and `lxml`: `META-INF/container.xml`, then the package's spine for reading order, the navigation document (or the NCX as fallback) for chapter titles and boundaries. Without a usable table of contents: one chapter per spine item, or split at `h1`/`h2`. Images are dropped. |
| PDF with a text layer | `pdfplumber` for characters with font name, size and position, `pypdf` for bookmarks. Chorus's own code removes repeated headers and footers and page numbers, detects italics from the font name or slant, rebuilds paragraphs from spacing and indents, joins lines across page breaks, and removes hyphens at line ends (keeping a hyphen when the joined word is not in a word list but both halves are). Chapters from the bookmarks, else from headings by font size or the Language pack's heading patterns. Pages without a text layer are rejected (no OCR). |
| TXT | Chorus's own reader. Encoding: the byte-order mark if there is one, else UTF-8, else detected with `charset-normalizer`; the encoding used is shown among the import warnings. Chapters are lines that match the Language pack's heading patterns ("Chapter 12", "CHAPTER XII", "Part One", a lone number); with none found, or no patterns in the pack, the whole file is one chapter. Runs of blank lines or `***` become Section breaks. |
| MOBI, AZW3 and anything else Calibre converts (DOCX, FB2, RTF, HTML, ODT…) | Calibre's `ebook-convert` run as a separate process into EPUB, then the EPUB reader. |
| AO3 by URL (milestone 2) | One user-started request for `GET /works/<id>?view_adult=true&view_full_work=true` with an honest User-Agent naming Chorus, parsed with the same structure AO3's own downloads use (preface, chapters, chapter notes, afterword). `/downloads/` is never used, since robots.txt disallows it. No crawling, search or background refresh. On 429 or 5xx: back off, honour `Retry-After`, retry a few times, then fail with "AO3 is busy, try later or upload the download instead". A work for logged-in users only gets "download it from AO3 (EPUB or HTML) and upload it"; Chorus never asks for AO3 credentials. |
| AO3 upload (milestone 2) | An AO3 EPUB or HTML download, recognised by its publisher "Archive of Our Own" and its preface/chapters/afterword structure, read with the AO3 parser so the summary, notes and tags are kept as metadata and out of the story text. |

- **Rejected with a clear message:** DRM-protected files (for EPUB, `META-INF/encryption.xml` is present), PDFs with no text layer, and files no reader or Calibre can open.
- **Language:** from the Source's metadata when it states one (EPUB and AO3 do), otherwise from an offline language detector (`lingua-py`) run on the text. Regional variants count as the base language (`en-GB` is `en`). It is shown on the Work page, where the user can change it. A Work whose language has no Language pack gets a notice that the English pack will be used, and runs anyway; setting the language to English by hand removes the notice.
- **Changing the language later** runs nothing by itself: the Script and audio are flagged outdated, the user starts a new analysis when ready, pinned corrections survive, and Voices are cast again from the new language's set.
- **AO3 is remembered:** a Work records that its Source was AO3, for the commercial-use line.
- **Before milestone 7,** a changed Source (such as an AO3 work with new chapters) is imported again as a new Work.

## Analysis

Analysis runs on the GPU queue as one child process with the llama.cpp server (Qwen3.5-4B, 8k context, one slot, thinking off, temperature 0). Model output is constrained by a JSON schema. Prompts are in English for every language. Every finished chunk is saved.

1. **Kinds of text.** Each passage gets its kind from the import structure, and only from markup the Source actually has (EPUB and AO3 structure, footnote links, block quotations, PDF bookmarks and fonts where they are clear). Anything not marked is narration, including unquoted italic passages; the user changes a kind in the reading view (milestone 3). Detecting unmarked kinds is left for later (see [08](08-open-questions.md)). The kinds are: narration, chapter title, Work title and author, epigraph, letter (a letter, note or text message set as its own block), verse, footnote, list or table, AO3 summary or author note, and never-voiced material (tags, dedications, copyright pages, Gutenberg boilerplate, images and captions, tables of contents, page furniture). Text that will not be voiced stays in the Script, greyed out in the reading view, and is not analysed for Speaker or Emotion.
2. **Line splitting.** Paragraphs are split into lines: each quotation is one line, and the narration between quotations within a paragraph is one line. The quotation marks come from the Language pack. A quotation that continues into the next paragraph must stay one quotation (the prototype's splitter got this wrong for a song inside a speech). A letter read aloud inside quotation marks is ordinary dialogue, not a letter block. A Work whose text quotes mostly with the pack's alternative marks (‘ ’ in English) is split with those; a closing mark followed by a letter is an apostrophe. The front and back matter are split and voiced like a chapter, except their lists (contents, lists of illustrations), which are never voiced.
3. **Character list.** The Work is cut into chunks of whole paragraphs of about 900 words, never across a chapter. Chunk by chunk, the model sees the list so far (each Character's canonical name, gender, age band and aliases) and returns only what is new: Characters not yet listed, and new aliases of listed ones. Code merges them: an alias is refused if it is not a name (at most four words starting with a capital, particles such as "de" aside; no pronouns or lists), does not appear in the chunk, or already belongs to another Character, and a Character listed again is merged rather than added. Gender is female, male or unknown; the age band is child, young adult, adult, elderly or unknown, "unknown" only when the text says nothing. For each chunk the model also says whether the text is told in the first or third person, and if first person, who the narrating Character is. A Character the text never names is listed under a short description ("Gregor's mother"). A chapter takes the majority answer of its chunks as its Narrating Character (or none), so Works whose chapters alternate between narrators are handled; a tie goes to first person, since a first-person chunk with little narration is often answered "third" while a third-person text almost never gets "first", and "I" or "the narrator" never counts as a name. A Narrating Character missing from the list is added, with the gender and age the model gives for the narrator. Names are compared without a leading article, and a gender the model leaves unknown is taken from a title in the name ("Mr. Bennet"), both by the Language pack's name rules. The Work title line Chorus makes is the Narrator's and is not analysed. Every attribution prompt gets the whole list, untrimmed: on Pride and Prejudice the whole book's list is 54 Characters in under 900 tokens, and trimming it to the Characters named nearby lost those referred to only by description (M1 ticket 03). Rewriting the whole list on every chunk, as the first prototype did, was dropped: its output grows with the list and would overflow 8k context partway through a novel.
4. **Speaker attribution and Emotion.** Chunk by chunk, with the Character list and the last 150 words of the previous chunk as context, every quoted line gets a Speaker (a listed Character, the Narrator for a quotation nobody says, such as a quoted word or title, or Unknown), a kind (speech, thought, or written text being read), an Emotion and an intensity. In a first-person chapter, the Narrating Character's own lines get that Character's name, never the Narrator.
5. **Second labelling run (from milestone 3).** Step 4 is run again with the same Character list and prompt, but in chunks of about 600 words, so every line is read in a different context. It is no more accurate on its own; it is there to find disagreements. It adds about 70% to the analysis time. It arrives with the question queue in milestone 3; a Work analysed before then gets its second run the first time the user opens Review.
6. **Review queue (from milestone 3).** A quoted line is put in the question queue when any of these holds:
   - No Speaker was found (Unknown, or a name not in the Character list).
   - A quoted line was given to the Narrator.
   - The paragraph's own narration says "said X" (from the Language pack's speech-verb list) and the label is someone else.
   - The same Speaker has two paragraphs in a row and the second has no narration.
   - The line addresses its own Speaker by name.
   - The second run names a different Speaker, or none.

   The queue also asks about Characters with a single line. On the sample passages this asks 40 questions and catches 19 of the 21 wrong lines.
7. **Silent Characters are dropped.** After attribution, Characters with no lines leave the list. Duplicates and wrong merges in the list (two entries for one person, or one person's name filed under another) are not fixed automatically; the user merges or splits them in review.
8. **Pinned corrections survive.** When a Work is analysed again, corrected lines and Characters keep what the user set. A line keeps its audio if its Speaker, Emotion, intensity and text came out the same.

**Emotions:** neutral, happy, excited, amused, angry, sad, afraid, anxious, surprised. Two intensities: normal and strong. The Narrator has no Emotion. Thoughts are never strong. A letter is neutral unless the user sets an Emotion.

**After analysis:** voicing starts straight away, unless the setting "wait for my review before voicing" (global, and per Work; off by default; from milestone 3) is on. Then the Work stops in the state "ready for review" until the user starts voicing. Works never reviewed carry a small mark either way.

**Speed:** on the six sample passages (10,621 words) one analysis pass took about 1,250 s and the second run about 890 s in the container: about 3.5 hours for a 100,000-word novel without the second run, 5 to 6 hours with it.

**Accuracy to expect:** about 90% of Speakers right (259 to 267 of 288 on the samples with the prototype's full-list Character pass, depending on the llama.cpp build; 270 to 276 with M1's delta list, M1 tickets 11 and 12). Emotion is often wrong and the prompt is untuned. Known failure cases the reading view must make quick to fix: a Character missing from the list, so their lines become Unknown; turn-taking lost in long untagged exchanges; a line given to the person it addresses; speakers who are only described, never tagged; thoughts and group lines given to the Narrator; an invented Character; a first-person narrator split into two Characters ("I" and "Jane").

## Casting

Auto-casting runs straight after analysis and uses built-in Voices of the Work's language only.

- **Narrator:** the Language pack's default Narrator Voice (`af_bella` for English). The user can swap it. It is never given to a Character.
- **Narrating Character:** in a chapter told in the first person, the Narrator and the Narrating Character share one Voice, auto-cast by that Character's traits: the chapter's narration is read in the Narrating Character's Voice. The user can separate them in the cast. This is the one exception to the rule above. Narrating Characters are cast first, and the narration they read counts as their lines.
- **Characters:** those with the most lines get unique Voices from the 11 left, while a Voice of their gender is free. The rest share the closest match by labels. Characters who share a Voice should never both speak in the same chapter; where that is impossible, Chorus picks the pair with the fewest chapters in common. Child and elderly Characters get the closest adult Voice of their gender, since no built-in Voice is a child or elderly. A Character of unknown gender is matched on age band across all 11 Character Voices, preferring the Voice with the fewest lines so far, so minor unnamed speakers spread out instead of piling on one Voice.
- **Cloned Voices** are never auto-cast; they are used only where the user assigns them.

## Voicing

Voicing runs on the GPU queue as one child process with Chatterbox 500M, after analysis has finished.

- **Order:** reading order, chapter by chapter. A chapter can be played as soon as all its lines are voiced.
- **Batches:** T3 runs over a batch of lines, then leaves the card, then S3Gen runs over the same batch (see [02-architecture.md](02-architecture.md#gpu-turn-taking)).
- **Text sent to the model:** the line's text with the Work's Respellings put in place of their words. The Script's text never changes.
- **Voice:** a Character's line is read in the Character's Voice; narration in the chapter's narration Voice (the Narrating Character's in a first-person chapter, else the Narrator's); a quoted line whose Speaker is Unknown in the Narrator's Voice, with its Emotion.
- **Reference clip:** the Voice's neutral clip.
- **Settings per line:** a Character line uses its Emotion and intensity, looked up in the voice model's Emotion settings (`exaggeration` and `cfg_weight`). The Narrator always uses neutral (0.5 / 0.5). No setting goes above `exaggeration` 0.9.
- **Seed:** each line stores its seed. Re-voicing a line reuses it, which reproduces the same take, so only what the user changed changes. A New take picks a new seed.
- **Watermark:** Chatterbox's watermark is on. A global switch to turn it off arrives in milestone 8; it applies to audio generated afterwards, and existing audio keeps what it was made with.
- **Long lines:** a line is split into sentences using the Language pack's sentence rules; each sentence is voiced with the line's Voice, settings and seed, and the sentences are joined with 0.3 s between them. Short inputs keep the voice model reliable.
- **Output:** one FLAC file per line (24 kHz, as Chatterbox writes it). A line with nothing to say ("* * *", a lone dash) is a quarter-second of silence: given no words, the model says a sentence of its own.
- **Not voiced:** lines in passages marked not voiced, and kinds whose switch is off.

**Speed:** about 2 times real time with the two halves loaded in turn (2.0 on the six sample passages, M1 ticket 13): a 10-hour Audio drama takes most of a day.

## Assembly

Each chapter's audio is put together from its line files with ffmpeg, on the non-GPU queue, and cached. The front matter (with the Work title and author) and the back matter are assembled the same way, as parts of their own before the first chapter and after the last.

- **When:** as soon as all of a chapter's lines are voiced, so it can be played while later chapters are still being voiced. A Work is ready to listen when every part is assembled.
- Each clip's own leading and trailing silence is trimmed first (below −50 dB, keeping 0.04 s).
- Pauses come from one fixed set of lengths, kept in one settings file (not per Work) and tied to nothing in the Script except structure. Starting values, all tuned by ear during milestone 1's listening check:

| Where | Start value |
|---|---|
| Between sentences of one line (voicing joins them) | 0.3 s |
| Between lines | 0.45 s |
| At a new paragraph | 0.75 s |
| At each line end of verse | 0.3 s |
| Long pause: after the Work title and author, a chapter title, an epigraph's source line | 1.5 s |
| Longest pause: at a Section break | 2.5 s |
- **What is read, by default:**

| Kind | Default | Who and how | Per-Work switch |
|---|---|---|---|
| AO3 summary and author notes | Skipped | Narrator, neutral, where they stand | On |
| Tags, dedications, copyright pages, Gutenberg boilerplate | Skipped | Never voiced | None |
| Work title and author | Voiced | Narrator, once before chapter one, then a long pause | Off |
| Chapter title | Voiced | Narrator, as written, then a long pause; nothing for a chapter without a title | Off |
| Epigraph | Voiced | Narrator, after the chapter title, then its source line, then a long pause | Off |
| Section break | Longest pause | Nothing is said | None |
| Thought | Voiced | The thinking Character's Voice with the line's Emotion, never strong; no echo or filter. A thought whose thinker is unclear is read by the Narrator | To the Narrator |
| Letter, note, text message set as its own block | Voiced | The writer's Voice if the writer is a known Character, else the Narrator; signature and date lines in the same Voice | None |
| Footnotes and endnotes | Skipped, marker dropped | Narrator, at the end of the paragraph, introduced by "Footnote" | On |
| Verse and songs | Voiced | Spoken, never sung, by whoever says it | None |
| Images, captions, tables of contents, page furniture | Skipped | Never voiced | None |
| Lists and tables inside the story | Voiced | Narrator, as plain text | None |

- **Emphasis** (italics or capitals for stress, italic titles) changes nothing in the delivery.
- **Switches** live on each Work's settings panel, and a global settings page holds the defaults a newly imported Work starts with (milestone 3; milestone 1 uses the defaults with no switches). Changing a switch on a Work that has audio puts the affected lines on the waiting list.

## Regenerate

What happens after a correction (milestone 3):

- **What is re-voiced:** only lines whose Voice, Emotion, intensity or text changed. A changed Speaker counts as a changed Voice. A Voice change re-voices all of that Character's lines; a Narrator Voice change re-voices all narration; changing a chapter's Narrating Character re-voices that chapter's narration. Splitting or joining lines re-voices the resulting lines. A new or changed Respelling re-voices every line containing the word. Neighbouring lines are untouched.
- **Not re-voiced:** adding or removing a Section break changes only a pause, so the chapter is re-assembled; chapter edits that leave lines unchanged re-voice nothing except a changed chapter title.
- **When:** only when the user presses Regenerate. Corrections collect as lines waiting for audio, with a count and a rough time.
- **Meanwhile:** old audio keeps playing so the chapter stays whole, and waiting lines carry a mark in the reading view. Lines never voiced (for example, just split) are skipped by the player.
- **Previous take:** a re-voiced line keeps the take before it. Both can be played, and "restore previous" swaps them, re-assembles the chapter and flags exports outdated like any re-voiced line.
- **During a running job:** corrections are allowed and the job is never restarted. Lines not voiced yet use the corrected values when their turn comes; lines already voiced join the waiting list. Pressing Regenerate during the job queues the waiting lines after it.
- **During or after an export:** an export uses the audio as it was when it started and always finishes. Once lines are re-voiced, the export and each affected chapter video are flagged outdated.
- **Exporting with lines waiting:** Chorus says how many lines are waiting and offers "Regenerate, then export" or "Export anyway" (old audio, flagged outdated at once). It does not block.

## Update from Source (milestone 7)

The user fetches the AO3 page again or gives a new file. Chapters whose text is unchanged keep their Script, corrections, audio, bookmarks and position. New or changed chapters are analysed and voiced with the existing Characters and Voices. In a changed chapter, corrections are kept where the line's text still matches.

## MP3 and M4B export

Written to the host's exports folder, one sub-folder per Work, so the files survive deleting the Work. The Work page lists each export with its date, a download button and the outdated flag, and each can be deleted from the list.

| | M4B | MP3 |
|---|---|---|
| Files | one per Work | one per chapter, with numbered file names |
| Audio | AAC, mono, 64 kbps | mono, 96 kbps |
| Chapters | chapter markers from the assembled chapter lengths | one file per chapter |
| Tags | title, author, cover | title, author, track number, cover |

Line audio stays 24 kHz FLAC; the YouTube export resamples to 48 kHz.

## YouTube export (milestone 8)

An export, not Publishing: the user uploads the files by hand in YouTube Studio.

- **Per chapter:** an upload-ready MP4, a description, a thumbnail, and an upload checklist. One video per chapter, meant to be grouped by the user in one playlist per Work; never one long video.
- **Video:** a still image at 1 fps with the audio as 48 kHz AAC, `-t` set to the audio's length:
  `ffmpeg -loop 1 -framerate 1 -i cover.png -i chapter.m4a -map 0:v -map 1:a -c:v libx264 -preset veryfast -tune stillimage -pix_fmt yuv420p -g 60 -c:a copy -t <duration> -movflags +faststart out.mp4`. About 1.4 s per 10 minutes of audio.
- **Image and thumbnail:** the Work's cover if the Source has one, else a generated title card; the Work title and chapter title are drawn on it. 1280×720 JPEG under 2 MB; the same image is the still frame.
- **Description:** generated and editable before upload; it ends with a line saying the voices are AI-generated. YouTube's limits apply: title up to 100 characters, description up to 5,000 bytes, no `<` or `>`.
- **Checklist:** reminds the user to tick YouTube's "altered or synthetic content" box; for a Work whose Source was AO3, it shows the line about AO3's Terms of Service banning commercial use, every time.
- **Video links:** the user can paste each chapter's YouTube link into Chorus; the Library and the Work page show it.
- **Outdated:** Chorus records when each chapter was last exported for YouTube and flags chapters whose audio changed since. A pasted link is kept and shown as "video outdated" until the user re-exports and either pastes a new link or confirms the video was replaced.

## Publishing (milestone 9)

Uploading from the app to the user's YouTube channel.

- **The user's own Google Cloud project.** Chorus never ships shared credentials. The Connect wizard walks the user through creating a project, enabling the YouTube Data API v3 and the YouTube Analytics API, setting the OAuth consent screen to "In production" (in Testing, refresh tokens expire after 7 days), creating a Web client with the redirect `http://localhost:<port>/oauth/youtube/callback`, and pasting the client ID and secret. Connect runs on the Docker host (see [02-architecture.md](02-architecture.md#access)), with `access_type=offline`.
- **Scopes:** `youtube` (uploads, playlists, every Data API read) and `yt-analytics.readonly` (statistics), asked once at Connect. `youtube.upload` is not used. If the user unticks statistics on Google's screen, Publishing still works and the dashboard shows only the live counters, with a "grant statistics access" button.
- **A failed token refresh** puts the connection in a "reconnect YouTube" state; it is not a failed job.
- **The private lock:** every upload from a project that has not passed YouTube's API compliance audit is locked private and cannot be made public or appealed. A setting "my Google Cloud project has passed the YouTube audit" is off by default. While it is off, the YouTube page and each uploaded chapter carry a notice: videos uploaded by Chorus are private and cannot be made public, their numbers stay near zero, and for public videos use YouTube export and paste the link. Uploaded videos are labelled "private (locked)". The only privacy offered is private unless the setting is on.
- **One click per Work:** renders the videos (as for YouTube export), uploads them with resumable uploads, creates the Work's playlist and adds each video in chapter order, sets thumbnails and the synthetic-media flag. Nothing is uploaded without that click. A refused thumbnail (403) is a warning, not a failure. Uploads have their own quota of 100 per day; on `quotaExceeded` the job waits for the reset at midnight Pacific time.
- **Regeneration:** Chorus uploads the new video and puts it in the playlist in the old one's place. The old video stays on the channel, outside the playlist, and Chorus tells the user. It never deletes a video.
- **Statistics:** see the YouTube page in [06-screens.md](06-screens.md#youtube-page). Live counters (views, likes, comments, upload and processing status) come from the Data API, batched up to 50 ids per call, hourly while the dashboard is in use and on a Refresh button. Watch time and average percentage listened come from the Analytics API once a day, 2 to 3 days late. Only the latest figures are stored, with the time they were fetched; a chart asks YouTube for its date range when opened. Authorisation is re-checked at least every 30 days. "Disconnect YouTube" deletes all stored figures at once and keeps pasted links.

## Permissions and disclosure

Chorus informs and never blocks.

- **Works the user did not write:** one warning, shown once ever, the first time the user makes a YouTube export or Publishes: the author's permission is needed, including podfic permission for fanworks. Nothing is recorded per Work. Import, generation, listening and MP3/M4B export never ask.
- **Cloning a voice:** no question and no checkbox when a clip is added.
- **AO3 and commercial use:** one line about AO3's ban on commercial use in the YouTube export checklist and on the Publishing screen, every time, for Works from AO3.
- **Synthetic-content flag at Publishing:** `containsSyntheticMedia` is on by default and can be turned off per Work. The first time a cloned Voice is in a Work being Published, Chorus asks "is this your own voice?" and stores the answer on the Voice. If it is not the user's own, the flag is forced on for that Work.
- **YouTube export** does not use the own-voice answer: it always reminds the user to tick YouTube's box and writes the AI-voice line.
- **README:** a few lines on the author's permission, the speaker's consent and the AO3 commercial-use point.
