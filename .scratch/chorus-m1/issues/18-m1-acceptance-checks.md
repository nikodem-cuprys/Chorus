# M1 acceptance: listening and memory checks

Type: prototype (needs the user's ears)
Status: ready-for-human
Blocked by: 14, 15, 16

## What to do

The checks that make M1 done, beyond the tickets' own acceptance criteria.

1. **Listen to the split-loaded Chatterbox.** Voice the six sample passages in the real image and listen to them. Compare with the clips in `.scratch/chorus/prototypes/chatterbox-fit/` (`listen.html`) and the listening test; line 06 is the one that differed most under half-precision weights. The verdict is the user's.
2. **Tune the six pause lengths by ear** on the same passages: between sentences, between lines, new paragraph, verse line end, long pause, Section break. Claude prepares versions with each value changed; the user picks. Write the chosen values into the pause settings file and into `docs/spec/03-pipeline.md`.
3. **Analysis memory beside a desktop.** Run analysis on a whole Work in the real image with a normal desktop on the card and record the card's peak. Ticket 24 measured 3.3 GB added and about 190 MiB to spare. If it spills or fails, stop and reopen the analysis memory question.
4. **End to end:** import a full novel in each format group (EPUB, TXT, PDF, a Calibre format), let it run with no review, play a chapter, export MP3 and M4B, and listen to some of the M4B in an audiobook player.

## Resolves with

The user's verdicts on 1 and 2, the measurements for 3, and a note of anything 4 turned up. Problems found become new tickets.

## Spec

`docs/spec/07-milestones.md` (M1, "Done when").
