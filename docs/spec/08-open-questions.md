# Open questions and risks

Found while writing the spec and left undecided on purpose. Each needs a decision before or during the milestone named. The milestone tag is the earliest milestone it blocks.

## Undecided

The milestone 1 items were decided on 2026-10-12 and written into the sections they touch.

### Analysis and the Script

1. **[after M1] Kinds of text without markup.** Milestone 1 takes kinds only from markup and treats everything else as narration, including unquoted italic passages. Whether letters, epigraphs, verse, footnotes and italic thoughts are ever detected in TXT, PDF and loosely marked EPUBs (by rules, or by the analysis model), and in which milestone, is not decided.
2. **[M3] Matching pinned lines after a new analysis.** Pins must survive a new analysis, but if line splitting changes, a line's identity changes. Whether a pin is matched by text, by position, or both is not decided.
3. **[M3] A removed Character's lines.** Removing a Character could send its lines to Unknown, to the Narrator, or ask. Not decided.
4. **[M3] Undo.** The review prototype had Undo in the top bar; ticket 09's decision does not mention it.

### Voices

5. **[M6] Clips for cloning.** Required length, format, and whether Chorus trims or cleans the clip.

### Pronunciation

6. **[M4] Which dictionary** decides that a word is unusual, so it becomes a candidate.
7. **[M4] How a word is matched** in the text: capitals, possessives ("Niamh's"), names of two words.
8. **[M4] "Try it" while the GPU is busy.** The GPU queue has one slot, so "try it" would wait behind a voicing job that can take a day. Pause the job, run it on the CPU, or wait?

### Export

9. **[M8] The AO3 commercial-use line.** Ticket 10 puts it in the YouTube export checklist and on the Publishing screen, which only the user sees. Ticket 28 lists it among the listener-facing export lines, which would put it in the video description. Which is it?
10. **[M8] Video length limits.** Unverified YouTube accounts can upload only 15 minutes per video, and nothing may be over 12 hours. Does the export warn about long chapters, and how is a chapter over 12 hours split, now that there are no Scenes to split at?
11. **[M8] Default title format** for a chapter video.

### Publishing

12. **[M9] "Made for kids".** YouTube requires `selfDeclaredMadeForKids` to be set on every upload. The default and whether the user is asked are not decided.
13. **[M9] Playlist privacy.** Presumably the same as the videos (private while locked); not stated in any ticket.

### Platform

14. **[M5] Setting the network password.** In the interface, or by an environment variable at start-up; and how it is stored.

## Risks

- **Analysis memory:** 3.3 GB at peak with about 190 MiB to spare beside a desktop holding 572 MiB. A busier desktop pushes it into system memory under WSL2, or makes it fail on Linux. M1 is not done until this is shown again on the real image.
- **The split voice model not heard yet:** the audio was compared by numbers only (waveform differences below -75 dB). M1 is not done until it is checked by ear.
- **Attribution is not reproducible across builds:** 267 against 259 of 288 with the same prompts and temperature 0. The scores were against Claude's reference labelling, not the user's.
- **Emotion is often wrong** and the prompt is untuned; Emotion settings were chosen on two of the 12 Voices only, and Respellings were not tested on strong Emotions or on the other ten Voices.
- **The Character list on a whole novel** is the weakest part of analysis (M1 ticket 03): on Pride and Prejudice it had duplicates (Charlotte and Charlotte Lucas), wrong merges (Mrs. Gardiner filed under Elizabeth, Georgiana under Lady Catherine) and missing people, and those errors go straight into attribution (most of the Gardiners' lines in chapter 43 were wrong). Until review exists (M3), automatic output will carry them.
- **Speed figures come from short samples:** about 0.2 s per word for analysis and 2.2 times real time for voicing, measured on passages under 2,000 words.
- **Untested hosts:** no Linux host and no card without a desktop has been measured. Docker Desktop's support for Windows 10 is ending.
- **Chatterbox 500M being English-only** (with a multilingual sibling as a separate model) was stated from memory in ticket 28 and not checked. It matters for the second Language pack.
- **YouTube, not confirmed from a primary source:** the 50-id limit per `videos.list` request; whether Analytics returns figures for private videos and counts the owner's own plays; that the private lock does not affect reads; the Analytics default quota; whether the scopes are "sensitive". Whether YouTube approves compliance audits for personal single-user projects is not documented.
- **Monetisation later:** YouTube's Partner Program rejects "mass-produced, repetitive" content, and dozens of still-image chapter videos could draw that label. AO3's terms ban commercial use of AO3 works outright.
