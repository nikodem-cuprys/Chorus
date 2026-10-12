# Data model

Entities and what they hold, in PostgreSQL unless noted. Field names are descriptive, not final column names. Audio files live on the data volume; the database holds their paths.

## Work

- Title, authors, cover image (from the Source, else a generated title card).
- Language code (`en`, `pl`; base language only), and whether it came from metadata, the detector or the user.
- Source: kind (EPUB, MOBI, AZW3, PDF, TXT, other Calibre format, AO3 by URL, AO3 upload), file name or URL, time of import, content hash, and a stored copy of the Source file.
- Whether the Source was AO3.
- Metadata from the Source: summary, tags, series and index, rating and warnings, publisher, publication date.
- Import warnings.
- State: importing, analysing, ready for review, voicing, ready to listen, failed (with the reason). A paused job shows as paused.
- Whether it has been reviewed, and whether it has been played to the end ("listened").
- Times added and last opened.
- Settings: the special-text switches (copied from the global defaults at import), and the synthetic-content flag for Publishing (on by default).
- The Narrator's Voice for the Work.
- The listening position: one line.

## Chapter

- Work, index, title (or none), content hash of its text (for Update from Source).
- Narrating Character, or none for a chapter told in the third person; whether the user corrected it.
- Whether the Narrating Character and the Narrator share a Voice (the default) or the user separated them.
- Its blocks of text, with kinds and marks as imported, notes before and after, and Section breaks (each from the Source or set by the user, and pinned if the user changed it).
- Assembled audio file and its length; whether it needs re-assembly.
- When it was last exported for YouTube.

## Line

The Script is the chapters' lines in order, plus the Character list.

- Chapter, position, paragraph, text with its marks, a reference back to the Source.
- Kind of text (narration, speech, thought, written; and the passage kind: chapter title, Work title, epigraph, letter, verse, footnote, list, AO3 note or summary, never voiced).
- Voiced or not (from the switches, or set by the user).
- Speaker: the Narrator, a Character or Unknown.
- Emotion and intensity (Character lines only).
- Seed.
- Pins: which of its values the user corrected. A pinned value survives a new analysis.
- Current take and previous take: two audio files, each with the Voice, Emotion, intensity, text and seed it was made with.
- Waiting for audio: its current take no longer matches its values.
- Whether it is in the review queue, and which rules put it there.

## Character

- Work, canonical name, aliases.
- Gender and age band (from analysis, correctable).
- Voice, and whether the user chose it or it was auto-cast.
- Pinned: the user added, renamed or corrected it, so a new analysis keeps it.

Merging two Characters moves all lines and aliases to the one kept. Where a removed Character's lines go is not decided (see [08](08-open-questions.md)).

## Voice

Built-in and cloned Voices share one format.

- Id, language, gender (female, male, neutral), age band (child, young adult, adult, elderly), accent, two or three timbre words from the fixed list, "suits the Narrator".
- Clips: one neutral reference clip now; the format allows more clips per Voice (for example, one per Emotion) later.
- Built-in or cloned. Built-in Voices are read-only files shipped with the Language pack (`voices.json` and the clips), with their source and credit. Cloned Voices are stored in the database and on the data volume, with labels filled in by the user.
- For a cloned Voice: "is this your own voice?" (not asked yet, yes, no), asked the first time it is in a Work being Published.

## Pronunciation entry

- Work, word, Respelling (one ordinary-looking word, no hyphens).
- Candidates are not stored as entries: Chorus lists Character names and words not in the Language pack's dictionary, and an entry exists only once the user types a Respelling.

## Bookmark

- Work, line, optional short note, time created.

## Job

- Work (or none), kind (import, analysis, voicing, re-voicing, try-it, assembly, export, YouTube export, YouTube upload, statistics refresh), queue (GPU or other).
- State: queued, running, paused, cancelled, failed (with the reason), done.
- Progress: stage, chapter x of y, lines done of total, measured speed for the time-left estimate.
- Progress itself is not a separate record: what is finished is the saved chunks and line audio, which is why a job can resume.

## Export

- Work, kind (MP3, M4B, YouTube export), folder path on the host, time, chapters covered.
- Outdated: set when any line it contains is re-voiced after it started.

## YouTube records (milestones 8 and 9)

- **Chapter video:** chapter, YouTube video id or pasted link, origin (uploaded by Chorus, or pasted), state (uploading, processing, private (locked), outdated, replaced, removed on YouTube, not on your channel), and the latest figures with the time fetched (views, likes, comments, watch time, average percentage listened; the delayed figures carry the date they run up to).
- **Work playlist:** playlist id and the number of videos in it.
- **Connection** (one): client id, encrypted client secret and tokens, scopes granted, "project has passed the YouTube audit" (off by default), channel subscribers and total views with the time fetched.

## Global settings

- Default special-text switches for new Works.
- Watermark on or off (milestone 8).
- Interface language.
- Network password (milestone 5).
- Whether the one-time permission warning has been shown.

## What survives what

| Event | Kept | Changed |
|---|---|---|
| Correction | everything else | the corrected values, pinned; affected lines become waiting |
| Regenerate | seeds | waiting lines get a new current take; the old one becomes the previous take; chapters re-assembled; exports flagged outdated |
| New analysis | pinned values and Characters; audio of lines whose Speaker, Emotion, intensity and text came out the same | everything not pinned |
| Update from Source | unchanged chapters in full; in changed chapters, corrections on lines whose text still matches | new and changed chapters analysed and voiced with the existing Characters and Voices |
| Delete Work | the exports folder; YouTube videos | the Source copy, Script, corrections, audio, previous takes, bookmarks and position are removed; one confirmation naming the Work; no trash, no undo |
| Disconnect YouTube | pasted links | all stored figures deleted at once |
