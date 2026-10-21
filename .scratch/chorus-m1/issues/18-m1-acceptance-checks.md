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

## Comments

**2026-10-21, Claude: parts 2 and 3 started.**

- **Part 3 (analysis memory):** Pride and Prejudice (Work 8, EPUB, 121,677 words, 61 chapters, 173 chunks) is being analysed in the real image with the desktop on the card (808 MiB before loading). Card and Windows' shared GPU memory are sampled every 2 s (`sample_card.ps1` in the session scratchpad). The voicing job analysis queues afterwards is paused at once, so it does not take the card for a day without the user deciding. Early readings: peak 3,907 MiB on the card (3,099 MiB added, about 190 MiB free), shared memory at most 176 MiB (within the 123 to 192 MiB seen on runs that fit), so no spill so far.
- **Part 2 (pauses):** `.scratch/chorus-m1/pause-tuning/make_variants.py` builds real excerpts of the voiced samples with each pause at four lengths, put together as assembly does, and `out/listen.html` to pick from (the audio is not committed; run the script again to rebuild it). The six samples have no verse, Section break or epigraph, so `pause-test.txt` (Work 17: two chapters, dialogue, two verse stanzas, a Section break) is queued behind the analysis and the page is rebuilt when it is voiced.
- **Found: the pause between sentences is heard as longer than the one between lines.** Voicing joins a line's sentences as Chatterbox writes them, each with its own silence at the end and start, which is not trimmed. At the current 0.3 s the heard silence is 0.52 to 0.75 s; between lines (0.45 s plus the two 0.04 s margins) it is 0.53 s. If shorter settings do not fix it by ear, voicing should trim each sentence before joining (as assembly trims each take).
- **Found: TXT never marks verse.** The TXT reader keeps an indented stanza's line breaks but leaves it a paragraph (ticket 06), so it is narration: voiced as one run of text, with no `verse_line_end` pause. For the pause test, Work 17's two stanzas were marked verse in the database by hand. Making set-out lines `verse` blocks in the TXT reader is a small new ticket.
- **Found: the six sample files' "#" header lines are voiced.** Each sample opens with notes (title, source, licence, word count, what it stresses), which the TXT import reads as text: 40 to 50 words of notes are the first narration of every sample. Not a Chorus bug, but worth knowing when listening for part 1; re-importing the passages without the header and voicing again fixes it.

**2026-10-21, Claude: part 3 measured.** Pride and Prejudice's analysis ran **3 h 8 min** (13:31 to 16:40 UTC) for 121,677 words, about 2.6 h per 100,000 words (the spec's 3.5 h was estimated from the samples), and found 40 Characters. Sampled 3,671 times:

- **Card:** desktop 808 MiB before loading; peak **3,908 MiB** (3,100 MiB added, **188 MiB free**), in the Character pass; the attribution pass peaked at 3,757 MiB. Ticket 24 measured 3,330 MiB added beside a 572 MiB desktop; here the desktop held more and the peak above it was lower.
- **Shared memory:** median 136 MiB, at most 213 MiB (twice, briefly). Runs that fit showed 123 to 192 MiB in tickets 24 and 25; a real spill was 862 MiB (ticket 25). **No spill.**
- **Verdict:** analysis fits beside this desktop, with under 200 MiB to spare. A busier desktop would still spill (WSL2) or fail (Linux), as the spec says.
- **Found and fixed: the time left was twice too long.** The percentage weighted an attribution chunk as three Character chunks (from the six dialogue-heavy samples); on this novel the passes took 88 and 100 min. At 50% the estimate said 129 min for 60. Now `ATTRIBUTION_WEIGHT` is 1.15 and each pass's speed is measured on its own, so the attribution half's estimate does not depend on the weight. Replaying the recorded run: 156 min estimated for 171 at 10%, 100 for 94 at 50%, 52 for 43 at 75%, 19 for 20 at 90%.
- The voicing job analysis queued (job 100) was paused at once; resume it on the Work page to voice the novel (about a day), for example as part 4's EPUB.
