# The Library and how listening works in Chorus

Type: grilling
Status: resolved
Blocked by: none

## Question

What does the in-app Library hold and show (Works, their pipeline state, exports, YouTube status from ticket 12), and how does listening in the browser work: chapters, saved position, bookmarks, following the text while listening, jumping from a line in the review screen to its audio, and whether earlier versions of regenerated lines are kept?

## Answer

Decided by the user on 2026-10-03 in a grilling session.

### Library

- **Layout:** a grid of cards, one per Work: cover (or a generated title card), title, author, total length, its state with progress when a job runs, and small marks for lines waiting for audio, outdated exports and YouTube links. Search by title or author; sort by recently opened, added or title. No folders, tags or series.
- **States:** importing, analysing, ready for review, voicing, ready to listen, or failed (with the reason). A paused job shows as paused. A Work played to the end is marked as listened.
- **Work page:** clicking a card opens the Work page: the cover, a Continue button that opens the reading view at the saved position, the chapter list with each chapter's state and length, the running job with its controls, the exports with their outdated flags, pasted YouTube links, the Work's switches (ticket 21), and import failures and warnings (ticket 03). An unreviewed Work offers Review (the question queue) beside Continue.
- **Exports:** written to a folder mounted from the host, one sub-folder per Work, so they are ordinary files. The Work page lists them with a download button, the date and the outdated flag; each can be deleted from the list.
- **Deleting a Work:** one confirmation that names the Work, then the Source copy, the Script with all corrections, all audio, bookmarks, the position and previous takes are removed. The exports folder is left alone and YouTube videos are never touched. No trash and no undo.
- **Update from Source:** fetches the AO3 page again or takes a new file. Chapters whose text is unchanged keep their Script, corrections, audio, bookmarks and position; new or changed chapters are analysed and voiced with the existing Characters and Voices. In a changed chapter, corrections are kept where the line's text still matches.

### Listening

- **The reading view is the player.** A player bar sits at the bottom; the line being spoken is highlighted and the text scrolls with it; clicking any line plays from that line, which is also how a line in review is heard. The bar keeps playing while the user visits the Library.
- **Controls:** play/pause, previous and next line, back 15 seconds, previous and next chapter, a chapter list with lengths, speed 0.75x to 2x, keyboard shortcuts. No sleep timer.
- **Early listening:** a chapter can be played as soon as all its lines are voiced; voicing goes in reading order.
- **Position:** one per Work, saved automatically on the server as a line rather than a time, so it survives re-voicing and is shared between devices.
- **Bookmarks:** put on a line from the player or the reading view, with an optional short note; a list per Work jumps to each.
- **What plays:** lines marked not voiced are skipped; lines waiting for audio play their old audio (ticket 20); a chapter being re-assembled plays its old version until the new one is ready.
- **Earlier takes:** each line keeps its current audio and the one before it. Both can be played, and "restore previous" swaps them, re-assembles the chapter and flags exports as outdated like any re-voiced line. Older takes are deleted. This amends ticket 11, where a corrected line simply replaced its file.
- **Other devices:** the Library, the Work page and the player are laid out to work in a phone browser over the home network (password required, ticket 11). Review and correction are designed for a desktop screen only. No offline listening and no app; for that the user exports an M4B.
