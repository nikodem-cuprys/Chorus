# Screens

Every screen works at desktop width. The Library, the Work page and the player also work in a phone browser over the home network (milestone 5); review and correction are designed for a desktop screen only. All text goes through the message catalogue.

## First run

Shown until the models are downloaded: each model with its size and a progress bar. Then the Library.

## Import

Reached from the Library. Upload a file, or (milestone 2) paste an AO3 work URL or upload an AO3 download. Rejections say why: DRM, no text layer, AO3 busy, AO3 work for logged-in users only. After import the Work appears in the Library and analysis starts by itself.

## Library

- **Milestone 1:** a plain list of Works with title, author, state and progress.
- **From milestone 5:** a grid of cards, one per Work: cover (or a generated title card), title, author, total length, state with progress when a job runs, and small marks for lines waiting for audio, outdated exports and YouTube links. Search by title or author; sort by recently opened, added, or title. No folders, tags or series. A Work played to the end is marked as listened.

## Work page

- Cover, title, author, language (changeable, with the notice when there is no Language pack).
- **Continue,** which opens the reading view at the saved position. An unreviewed Work also offers **Review**, which opens the question queue.
- The chapter list, with each chapter's state and length (milestone 1: plain playback of each chapter here).
- The running job with pause, resume and cancel, and its progress.
- Exports with date, download button, outdated flag and delete; buttons to export MP3, M4B and (milestone 8) for YouTube.
- Pasted YouTube links (milestone 8) and the YouTube section (milestone 9).
- The Work's settings panel: the special-text switches and "wait for my review before voicing" (milestone 3), and the synthetic-content flag (milestone 9). A Work stopped at "ready for review" shows a button to start voicing.
- Import failures and warnings.
- Update from Source (milestone 7) and Delete, with one confirmation naming the Work.

## Reading view (milestone 3; the player from milestone 5)

The main screen for review and for listening.

- **Text:** the Work as prose, each line tinted by its Speaker. Text that is not voiced is greyed out. Section breaks show as dividers. Lines waiting for audio carry a mark.
- **Line editor:** click a line to change its Speaker, Emotion, intensity, or speech/thought; split it or join it with the next; mark it not voiced or voiced again; change its kind (narration, letter, verse, epigraph, footnote, note); play it; New take; play and restore the previous take. Shift-click selects a run of lines; "swap the two Speakers" fixes lost turn-taking.
- **Scope of a correction:** this line, the selected lines, that Speaker's lines from here on, or all of that Speaker's lines. Merging Characters and changing a Voice apply to the whole Work.
- **Structure:** insert a Section break between any two lines or remove one; split a chapter at a line, merge two chapters, edit a chapter title; set or clear a chapter's Narrating Character.
- **Cast panel** beside the text: every Character with its line count and Voice; rename, merge into another, remove, drop an alias, add a Character; change the Voice (built-in Voices from milestone 3, cloned ones from milestone 6) with a sample to play; the Narrator's Voice; separate the Narrator from a Narrating Character.
- **Pronunciation panel** beside the cast (milestone 4): the candidate words (Character names and words not in the dictionary), each with a play button, a Respelling field and a "try it" button that renders the word in a short sentence with the Narrator Voice (about 20 s); selecting a word in any line sends it to the panel; any other word can be added.
- **Top bar:** the number of lines waiting for audio with a rough time, Regenerate, and a Changes panel listing corrections and waiting lines.
- **Player bar** (milestone 5): play/pause, previous and next line, back 15 seconds, previous and next chapter, a chapter list with lengths, speed from 0.75x to 2x, keyboard shortcuts. The line being spoken is highlighted and the text scrolls with it; clicking any line plays from there. The bar keeps playing while the user visits the Library. Bookmarks with an optional note, and a list per Work to jump to each. The position is saved automatically as a line. No sleep timer.
- **What plays:** lines marked not voiced are skipped; waiting lines play their old audio; lines never voiced are skipped; a chapter being re-assembled plays its old version until the new one is ready.

## Question queue (milestone 3)

The way into review, and optional like review itself. One question at a time with the surrounding text: a line from the queue rules, or a Character with a single line. The user picks a Speaker (number keys), keeps the guess (Enter) or skips (S). Every answer is a correction like any other.

## Settings

- The defaults for the special-text switches of new Works, and "wait for my review before voicing" (milestone 3).
- Interface language (Polish from milestone 5).
- Network password (milestone 5).
- Watermark switch (milestone 8).
- Voice library: built-in Voices with their labels and clips; add a cloned Voice from a clip, with labels filled in by the user (milestone 6). No question about consent.

## YouTube export (milestone 8)

From the Work page: the chapters to export, the outdated chapters marked, the one-time permission warning the first time, and the checklist (tick YouTube's synthetic-content box; the AO3 commercial-use line for AO3 Works). The description of each chapter can be edited. A field per chapter for the pasted video link, and "video replaced" for outdated chapters.

## Connect wizard (milestone 9)

Step by step: create the Google Cloud project, enable both APIs, set the consent screen to In production, create the Web client with the redirect shown, paste the client ID and secret, connect (only from the Docker host, which the wizard says), and the "project has passed the YouTube audit" setting.

## Publishing (milestone 9)

From the Work page: the videos to upload, titles (prefilled, editable), descriptions, thumbnails, the synthetic-content flag (forced on when a cloned Voice is not the user's own; the own-voice question the first time), the AO3 commercial-use line, the private-lock notice while the audit setting is off, and one Publish button.

## YouTube page (milestone 9)

- **For the Library:** connection state, channel subscribers and total views, and a table of Works with upload status and totals.
- **On each Work page:** that Work's chapters with a video, uploaded or pasted, marked as one or the other. Per chapter: status, views, likes, comments, watch time, average percentage listened, and the "video outdated" flag. Per Work: the sums, a chart of views per day, the playlist link and its number of videos. No dislikes, retention, traffic sources, geography or demographics.
- **States shown:** "private (locked)"; "not on your channel" for a pasted link to another channel's video (no figures); "removed on YouTube" (link kept until cleared); "replaced" after regeneration (link, no figures).
- Delayed figures carry the date they run up to; every panel says the numbers come from YouTube; only sums and averages of YouTube's own numbers are shown. A Refresh button, a "grant statistics access" button when that scope is missing, the private-lock notice while the audit setting is off, and Disconnect YouTube.
