# Chapter assembly and plain playback

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-21: `backend/chorus/assembly.py` (the stage and its job), migration 0008 (each chapter's assembled audio, and the front and back matter's on the Work), `POST /api/works/<id>/assembly`, `GET /api/works/<id>/audio/<part>`, and plain players on the Work page.

- **Parts:** each chapter is one file. The front matter (where the Work title and author are read, before chapter one) and the back matter are parts of their own, as the Work page already lists them. A part with no voiced lines has no audio. Parts are named as in the API: `front`, `back`, or the chapter's index.
- **When:** the voicing child queues an `assembly` job (on `other`) for each part as soon as its batch is saved, and the parent queues one for the whole Work when voicing ends. A part is assembled only when every voiced line in it has its current take. When every part is assembled, the Work's state becomes **ready** ("Ready to listen"); "voiced" now means voiced and still being assembled.
- **Trim:** Python reads each take and finds its first and last sample above −50 dB, keeping 0.04 s at each end (`SILENCE_DB`, `MARGIN`). A take that is silent all through keeps one sample, so it still carries its pause.
- **ffmpeg:** one run per part: `atrim` (by sample) and `apad` (the pause after it) on each take, then `concat`, written as 24 kHz 16-bit FLAC to `data/works/<id>/audio/` and moved into place when complete. The length is checked against the sum of trimmed takes and pauses (within 10 ms); it came out sample-exact in testing.
- **Pauses** (`pauses_after`), read from `pauses.json` on every run, from structure only: `between_lines` inside one paragraph, `new_paragraph` across paragraphs, `verse_line_end` between adjacent verse blocks, `section_break` where a Section break block lies between two lines, `after_title` after the Work title, a chapter title and an epigraph's last line (its source line). Where several apply, the longest wins. After a part's last line only a long pause stays (so the front matter ends with the 1.5 s after the title).
- **Verse inside one line:** a verse block whose lines are joined with line breaks (TXT verse, EPUB `<br>`) is one Script line, so its line-end pauses must be inside the take: voicing now splits verse at its line ends too and joins them with `verse_line_end`. Verse voiced before this change keeps its take (the text it was made from is the same) until it is voiced again.
- **Cache:** each part stores a key over its takes (file, Voice, Emotion, intensity, text, seed, length) and the pause after each. Assembling again skips parts whose key matches, so a changed pause re-assembles exactly the parts it touches. A new analysis deletes the assembled audio along with the line audio.
- **Work page:** each part in the chapter list has a plain `<audio>` player once it is assembled, with its length (`12:34`) after the word count; a part not yet assembled says "Not ready yet". No player is shown before voicing starts. The file is served as `audio/flac` with range requests (206).

Acceptance, in the container (ffmpeg 6.1.1), on the six sample passages voiced in ticket 13:

- **All six assembled** (the six Works' 12 parts) in **13 s** together; every Work is "ready". Parts: the front matter 3.8 to 4.7 s (the title and author; 342 s for Pride and Prejudice, whose first chapter has no heading of its own, so it is front matter, ticket 09), chapters 294 to 755 s. Trimming took 10 to 72 s off each Work's takes (2 to 10%; Alice's the most). **Not listened to:** whether −50 dB with a 0.04 s margin cuts no soft ends is for ticket 18.
- **Pauses in the file:** in Holmes' chapter, the silent runs measured in the assembled audio cluster at 0.53 s (36 of 38 between-lines pauses: 0.45 s plus the two 0.04 s margins). The samples have only title, between-lines and new-paragraph pauses: no Section breaks, epigraphs or verse, so those are checked by the unit tests only.
- **A changed pause:** `new_paragraph` set to 1.5 in the worker's `pauses.json` and Holmes assembled again: 616.191 s became 639.441 s, +23.25 s = 31 new-paragraph pauses × 0.75 s exactly. Set back, assembled again: 616.191 s.
- **Playing while voicing:** in the unit tests, voicing killed in chapter two leaves the front matter and chapter one assembled and playable (200), chapter two not (404), and the Work not ready.
- **Unit tests** (`tests/test_assembly.py`, skipped without ffmpeg): every kind of pause from its place in the Script, verse voiced with its line-end pause, trimming, a chapter's length against the sum of its trimmed takes and pauses (5 ms), the cache and a changed pause, nothing assembled before all lines are voiced, a chapter assembled as soon as it is voiced (with the API), voicing ending with the Work ready, a new analysis discarding the audio. Frontend: players for ready parts, "Not ready yet", "Ready to listen", no players before voicing.

Left for later:

- **Old version while re-assembling** (docs/spec/06-screens.md, What plays): a part's file is replaced only once the new one is complete, but the Work page shows the part as ready whenever a file exists, even out of date. That matters from milestone 3, when lines change after voicing.
- **Assembly jobs show in the job list** like any other; a whole-Work re-assembly is only an API call (`POST /assembly`), with no button. Ticket 15 may want one.
