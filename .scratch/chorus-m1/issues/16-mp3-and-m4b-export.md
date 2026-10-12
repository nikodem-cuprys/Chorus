# MP3 and M4B export

Type: task (AFK)
Status: ready-for-agent
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
