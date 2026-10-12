# Open questions and risks

Found while writing the spec and left undecided on purpose. Each needs a decision before or during the milestone named. The milestone tag is the earliest milestone it blocks.

## Undecided

### Analysis and the Script

1. **[M1] The second labelling run in M1.** It adds about 70% to analysis time and only feeds the question queue, which arrives in M3. Run it from M1, or add it in M3 (and then re-run it over already-analysed Works, or only for new ones)?
2. **[M1] Long lines and the voice model.** A line is one piece of audio, but a narration line can be a long paragraph. Chatterbox's longest reliable input was not measured. Is a long line voiced in parts (by sentence) and joined, and is the prototype's 0.3 s between sentences kept?
3. **[M1] Pause lengths.** Only 0.3 s (between sentences), 0.45 s (between lines) and 0.75 s (new paragraph) have values, all from the prototype and not tuned by ear. The "long pause" (after titles and epigraphs), the "longest pause" (Section break) and the "short pause" (verse line ends) have none.
4. **[M1] How kinds of text are detected.** Letters, epigraphs, verse and footnotes come from the import structure where the Source marks them (EPUB and AO3 markup). How they are found in TXT, PDF and loosely marked EPUBs is not decided, nor how an unquoted italic passage is judged to be a thought.
5. **[M1] Chapter-heading patterns per language.** TXT and PDF heading detection uses English patterns ("Chapter", "Part"). Ticket 28's Language pack list does not include them. Should they be a part of the pack?
6. **[M1] Text encoding of TXT files.** UTF-8 only, or detected?
7. **[M1] Long Works and the Character list.** The prototype capped the list at 30 Characters and 8 aliases each, and only ever saw passages of under 2,000 words. A novel's list must still fit beside a 900-word chunk in 8k context. How large the list may grow, and what happens past that, is untested.
8. **[M1] Narrating Character per chapter.** Ticket 20 records it per chapter; the prototype detected first or third person once per passage. How a chapter's Narrating Character is found (per chapter, or once per Work and then checked) is not decided.
9. **[M3] Matching pinned lines after a new analysis.** Pins must survive a new analysis, but if line splitting changes, a line's identity changes. Whether a pin is matched by text, by position, or both is not decided.
10. **[M3] A removed Character's lines.** Removing a Character could send its lines to Unknown, to the Narrator, or ask. Not decided.
11. **[M3] Undo.** The review prototype had Undo in the top bar; ticket 09's decision does not mention it.
12. **[M1] The "ready for review" state.** Ticket 22 lists it between analysing and voicing, but the default path voices straight after analysis. Is it a moment between the two, a state the Work stays in when the user turns automatic voicing off, or just a label on Works never reviewed?

### Casting and Voices

13. **[M1] Sharing Voices without Scenes.** Ticket 13 says Characters who share a Voice should not meet "in one Scene" where possible. Scenes are gone (ticket 26). The replacement unit (a chapter, or a window of lines) is not decided, nor the order in which labels count when finding the closest match (gender, age band, accent, timbre).
14. **[M1] Characters of unknown gender** have no rule for casting.
15. **[M6] Clips for cloning.** Required length, format, and whether Chorus trims or cleans the clip.

### Pronunciation

16. **[M4] Which dictionary** decides that a word is unusual, so it becomes a candidate.
17. **[M4] How a word is matched** in the text: capitals, possessives ("Niamh's"), names of two words.
18. **[M4] "Try it" while the GPU is busy.** The GPU queue has one slot, so "try it" would wait behind a voicing job that can take a day. Pause the job, run it on the CPU, or wait?

### Export

19. **[M1] MP3 and M4B layout.** One M4B per Work is implied by "with chapters"; whether MP3 is one file per chapter or per Work, the bitrates, the tags and the embedded cover are not decided. YouTube needs 48 kHz AAC, while Chatterbox writes 24 kHz.
20. **[M1] ffmpeg's licence** in the image was not checked (an ffmpeg build with libx264 is GPL). It runs as a separate process, as Calibre does, so it should be an aggregate; confirm.
21. **[M8] The AO3 commercial-use line.** Ticket 10 puts it in the YouTube export checklist and on the Publishing screen, which only the user sees. Ticket 28 lists it among the listener-facing export lines, which would put it in the video description. Which is it?
22. **[M8] Video length limits.** Unverified YouTube accounts can upload only 15 minutes per video, and nothing may be over 12 hours. Does the export warn about long chapters, and how is a chapter over 12 hours split, now that there are no Scenes to split at?
23. **[M8] Default title format** for a chapter video.

### Publishing

24. **[M9] "Made for kids".** YouTube requires `selfDeclaredMadeForKids` to be set on every upload. The default and whether the user is asked are not decided.
25. **[M9] Playlist privacy.** Presumably the same as the videos (private while locked); not stated in any ticket.

### Platform

26. **[M1] Base image flavour.** Ticket 05 named `nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04`; ticket 25 ran on the `base` flavour, since the torch wheel brings its own CUDA and cuDNN libraries. The spec uses `base`; confirm in the image build.
27. **[M1] The llama.cpp build.** The spec pins b11318, the only build measured in the container. A newer build may score differently (see risks); moving builds means re-scoring the samples.
28. **[M1] The language detector library** (ticket 28 left it to the build).
29. **[M5] Setting the network password.** In the interface, or by an environment variable at start-up; and how it is stored.

## Risks

- **Analysis memory:** 3.3 GB at peak with about 190 MiB to spare beside a desktop holding 572 MiB. A busier desktop pushes it into system memory under WSL2, or makes it fail on Linux. M1 is not done until this is shown again on the real image.
- **The split voice model not heard yet:** the audio was compared by numbers only (waveform differences below -75 dB). M1 is not done until it is checked by ear.
- **Attribution is not reproducible across builds:** 267 against 259 of 288 with the same prompts and temperature 0. The scores were against Claude's reference labelling, not the user's.
- **Emotion is often wrong** and the prompt is untuned; Emotion settings were chosen on two of the 12 Voices only, and Respellings were not tested on strong Emotions or on the other ten Voices.
- **Speed figures come from short samples:** about 0.2 s per word for analysis and 2.2 times real time for voicing, measured on passages under 2,000 words.
- **Untested hosts:** no Linux host and no card without a desktop has been measured. Docker Desktop's support for Windows 10 is ending.
- **Chatterbox 500M being English-only** (with a multilingual sibling as a separate model) was stated from memory in ticket 28 and not checked. It matters for the second Language pack.
- **YouTube, not confirmed from a primary source:** the 50-id limit per `videos.list` request; whether Analytics returns figures for private videos and counts the owner's own plays; that the private lock does not affect reads; the Analytics default quota; whether the scopes are "sensitive". Whether YouTube approves compliance audits for personal single-user projects is not documented.
- **Monetisation later:** YouTube's Partner Program rejects "mass-produced, repetitive" content, and dozens of still-image chapter videos could draw that label. AO3's terms ban commercial use of AO3 works outright.
