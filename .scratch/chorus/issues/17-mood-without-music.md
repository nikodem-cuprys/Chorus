# How a Scene's Mood is heard without music

Type: prototype
Status: resolved
Blocked by: 16

## Question

The audio drama has no music or sound effects, and Scene detection is coarse (ticket 08). Using only what Chorus controls (the Chatterbox settings chosen in ticket 16, the Narrator's delivery, and the length of pauses between lines and Scenes at assembly), can a listener hear a Scene's Mood? Render one or two sample Scenes in two or three Moods and compare by ear. Resolves with the Mood list and what each Mood changes in delivery, or the decision to drop Mood from the Script.

## Answer

Mood is dropped from the Script. A listener cannot hear it through what Chorus controls, and the user decided on 2026-10-03 that the Narrator should not act at all.

- **Result by ear:** two Scenes (a dialogue-heavy one from Jane Eyre, a narration-heavy one from Metamorphosis) were each assembled as calm, tense, melancholic and cheerful, changing only the Narrator's Chatterbox settings and the pauses. The user's verdict: "all narration is sounding as calm mood", and an Emotion needs context to be heard, otherwise it is ambiguous and confusing.
- **Narrator:** always voiced with the neutral settings from ticket 16 (`exaggeration` 0.5, `cfg_weight` 0.5). An emotional Narrator is foreign to an audio drama. Only Character lines carry an Emotion, including a Character's quoted thoughts.
- **Pauses:** one fixed set of lengths, tied to nothing in the Script. The user could not tell the versions apart by their pauses (0.6 to 1.6 times the standard). The prototype's standard, not tuned by ear: 0.3 s between sentences of one Narrator passage, 0.45 s between lines, 0.75 s at a new paragraph, with each clip's own leading and trailing silence trimmed first.
- **Mood label:** removed. The analysis stops producing a Mood per Scene and review never shows it. A Scene is now a continuous stretch of a chapter with one setting; `CONTEXT.md` is updated.
- **Measurements that agree:** across the four Moods the Narrator's pace stayed between 2.8 and 3.3 words per second, so the settings barely change speed. The analysis was also unreliable at Mood in ticket 08 (the Mad Tea Party came out as anxious, melancholic and tense).
- **Left open:** with Mood gone, a Scene carries only a setting, and nothing decided so far uses it in the audio; whether the Script still needs Scenes is not settled. Who voices the narration of a first-person Work is ticket 20; the neutral-Narrator rule here was heard only with `af_bella` as a third-person-style Narrator.
- **Not recorded:** the user gave the verdict in words; the blind guesses and the per-Mood dropdowns on the listening page were not pasted back. The Narrator was tried up to `exaggeration` 0.7 only, not at the ticket 16 ceiling of 0.9.

Listening page, scripts and the 82 clips: `../prototypes/mood-delivery/` (`listen.html`, `gen.py`, `build_page.py`, `out/`).
