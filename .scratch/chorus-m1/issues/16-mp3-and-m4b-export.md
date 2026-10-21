# MP3 and M4B export

Type: task (AFK)
Status: resolved
Blocked by: 14

## What to build

Export a Work's Audio drama into the host's exports folder, one sub-folder per Work, as ordinary files that survive deleting the Work.

| | M4B | MP3 |
|---|---|---|
| Files | one per Work | one per chapter, numbered file names |
| Audio | AAC, mono, 64 kbps | mono, 96 kbps |
| Chapters | chapter markers from the assembled chapter lengths | one file per chapter |
| Tags | title, author, cover | title, author, track number, cover |

- Export runs on the `other` queue, so it can run while another Work is being voiced. It has pause, resume and cancel like other jobs (ticket 15).
- The Work page lists each export with its date and a download button; an export can be deleted from the list (the file too).
- An export of a Work still being voiced is refused with a message until every chapter is ready. (Exporting with lines waiting for audio is M3.)

## Acceptance criteria

- The M4B of the six sample passages opens in a common audiobook player with its chapters and cover.
- The MP3 files play in order with their tags.
- The files appear in the host folder under the Work's sub-folder and can be opened from the host directly.

## Spec

`docs/spec/03-pipeline.md` (MP3 and M4B export), `docs/spec/06-screens.md` (Work page).

## Answer

Built on 2026-10-21: `backend/chorus/exporting.py` (the export and its job), migration 0009 (the `export` table), `POST /api/works/<id>/exports` (`{"kind": "m4b" | "mp3"}`), `GET /api/exports/<id>/download`, `DELETE /api/exports/<id>`, and an Exports section on the Work page.

- **Where:** the exports folder (`/exports`, the host's `./exports` or `CHORUS_EXPORTS_DIR`), one sub-folder per Work named after it with its id, "03-holmes-scandal-in-bohemia (14)", so two Works with one title do not share a folder. Names are made safe for Linux, Windows and macOS hosts (no `<>:"/\|?*`, at most 80 characters). The M4B is named after the Work; the MP3s are `NN - <part>.mp3` in an `MP3` folder inside it. Files survive deleting the Work: only the record goes with it.
- **One per kind:** a new export of a kind replaces the one before it (its files deleted, its record replaced), so the Work page lists at most one M4B and one MP3 export, each with its date. Files are written in a hidden `.export-*` folder inside the Work's folder and moved into place only when all are done, so a failed export leaves the previous one untouched.
- **What is in it:** the assembled parts (ticket 14) in reading order, so the front matter with the Work title and author is the first M4B chapter and the first MP3, and the back matter the last. A part is named by the chapter's title from the table of contents, else its title line in the text ("CHAPTER II."), else "Chapter N"; the front and back matter are "Front matter" and "Back matter". These names are English constants until Language packs carry listener-facing lines (milestone 8).
- **M4B:** the parts' FLAC files through ffmpeg's concat demuxer, AAC mono 64 kbps (at 24 kHz), one chapter marker per part from the assembled lengths (an ffmetadata file), title, album, artist and album artist, genre Audiobook, and the cover as an attached picture, `+faststart`.
- **MP3:** one file per part, LAME mono 96 kbps, ID3v2.3 with title (the part), artist and album artist, album (the Work), track `n/N` and the cover as an attached picture.
- **Cover:** the Source's cover converted to an RGB JPEG of at most 1400 px; without one (every TXT, PDF without metadata), a generated 1400 × 1400 title card with the title and authors in DejaVu Serif (in the image; Pillow's own font elsewhere). Pillow 12.3.0, already in the GPU stack, is now in `pyproject.toml` (the dependency layer rebuilt in 13 minutes).
- **Refused until ready:** `POST /exports` answers 409 `export.error.not_ready` unless the Work is "ready" and every part's audio is current; the job checks again when it runs. The Work page disables both buttons until then and says why.
- **Job:** `export` on the `other` queue, so it runs while another Work is voicing; progress from ffmpeg's `-progress` output as a percentage of the length. Pause, resume and cancel are ticket 15's.
- **Download:** the M4B as itself (`audio/mp4`); the MP3s as one uncompressed zip named after the Work's folder, built in a temporary file and deleted once sent. **Delete** removes the record and the files, and the folders they leave empty.

Acceptance, in the container (ffmpeg 6.1.1) on the six sample passages assembled in ticket 14:

- **All twelve exports** (an M4B and the MP3s for each Work) finished in **45 s** in all, four at a time on the `other` queue, 3 to 12 s each. 12 to 15 MB per Work for both together.
- **M4B**, checked with ffprobe from the host: AAC, mono, 24 kHz, 62 to 69 kbps on real speech; durations equal the sum of the parts (Holmes 620.9 s = 4.7 + 616.2); chapters "Front matter" at 0 s and "Chapter 1" at 4.7 s (Pride and Prejudice: "CHAPTER II." at 342.0 s); the title card as attached picture, 1400 px, looked at. **Not opened in an audiobook player:** none is installed on this machine; ticket 18 should open one in e.g. VLC, Apple Books or Smart AudioBook Player and confirm the chapter list and cover show.
- **MP3:** mp3, mono, 96 kbps, cover attached, `track` 1/2 and 2/2, title and album set. Artist is empty for the samples because their TXT Sources have no author; the unit tests check it with one.
- **On the host:** every file is under `exports/<Work> (<id>)/` on the D: drive, readable by ffprobe directly from Windows. The downloads answer with the right type and name (`03-holmes-scandal-in-bohemia.m4b`, 5.2 MB; the zip, 7.6 MB).
- **Unit tests** (`tests/test_exporting.py`, skipped without ffmpeg and ffprobe): safe names, the M4B's codec, chapters (to 2 ms of the assembled lengths), tags and title card, the MP3s' names, codec, bit rate, tags and cover, the Source's own cover used, a new export replacing the old one with no staging folder left, the refusal (function and API), the job, list, zip download and delete through the API, the M4B download. Frontend: the export list with date, length, files, folder, download and delete; buttons disabled with the reason until the Work is ready.

Left for later:

- **Outdated flag** (milestone 3, when lines change after an export): the record keeps the parts it covers (`parts`) and its length, but nothing sets "outdated" yet.
- **No confirmation on Delete**, as the spec asks none for an export (only for deleting a Work).
