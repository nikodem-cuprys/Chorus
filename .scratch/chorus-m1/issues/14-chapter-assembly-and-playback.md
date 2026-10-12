# Chapter assembly and plain playback

Type: task (AFK)
Status: ready-for-agent
Blocked by: 13

## What to build

Each chapter's line audio put together into one chapter file, and a plain player on the Work page.

- Assembly with ffmpeg on the `other` queue, as soon as a chapter's lines are all voiced; the result is cached.
- Each clip's leading and trailing silence trimmed first.
- Pauses from one settings file (not per Work), with these start values: 0.3 s between sentences of one line (used by ticket 13), 0.45 s between lines, 0.75 s at a new paragraph, 0.3 s at verse line ends, 1.5 s after the Work title and author, a chapter title and an epigraph's source line, 2.5 s at a Section break.
- The Work title and author are read once before chapter one; chapter titles and epigraphs where they stand.
- Plain playback on the Work page: each ready chapter can be played; a chapter still being voiced shows as not ready.
- The Work's state moves to "ready to listen" when every chapter is assembled.

## Acceptance criteria

- The six sample passages play from start to end with the pauses above; changing a value in the settings file and re-assembling changes the pause.
- A chapter can be played while later chapters are still being voiced.
- Tests check the assembled length against the sum of trimmed clips and pauses.

## Spec

`docs/spec/03-pipeline.md` (Assembly), `docs/spec/06-screens.md` (Work page).
