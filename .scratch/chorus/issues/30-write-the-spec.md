# Write the build-ready spec

Type: task (AFK)
Status: resolved
Blocked by: 29

## Question

Write the spec in `docs/spec/` from the map's Decisions so far and the tickets behind them: product scope, architecture, the full pipeline from Source import to Published Audio drama, the chosen models and libraries, the data model, the screens, and the milestones from ticket 29. Use the terms in `CONTEXT.md`. Where a later ticket amended an earlier one (ticket 22 on previous takes against ticket 11, ticket 23 on the YouTube permission against ticket 04, ticket 21 on epigraphs against the import research), the spec states the later decision only. List anything found undecided while writing instead of deciding it silently. Resolves when the spec exists and every line of Decisions so far is reflected in it.

## Answer

Written on 2026-10-12 in [`docs/spec/`](../../../docs/spec/README.md), from the map's Decisions so far and tickets 01 to 29. Eight parts: scope, architecture, pipeline, models and libraries, data model, screens, milestones, and open questions. The README has a table placing every ticket's decision in a section.

- **Later decisions only:** ticket 22's previous take over ticket 11; ticket 23's `youtube` + `yt-analytics.readonly` scopes over ticket 04's `youtube.upload`; ticket 21's voiced epigraphs over the import research; ticket 26's dropped Scenes over tickets 08, 09, 11 and 21; ticket 10's own-voice rule for the synthetic-media flag over ticket 04's "forced on for any clone"; ticket 29's Source formats over ticket 03, and Polish in M5 over ticket 28; ticket 24 and 25's measurements over the 2.8 GB budget.
- **Glossary:** `CONTEXT.md` gains **Line** (one quotation, or the narration between quotations within a paragraph; one Speaker, one piece of audio), which every ticket used without a definition.
- **Undecided, listed rather than decided** (29 items in `docs/spec/08-open-questions.md`): among them, the M1 ones: whether the second labelling run is in M1, how long lines are fed to the voice model, the missing pause lengths, how letters, epigraphs, verse and unquoted thoughts are detected outside EPUB and AO3 markup, chapter-heading patterns per language, the Character list's size on a whole novel, the Narrating Character per chapter, the "ready for review" state, Voice sharing now that Scenes are gone, the MP3/M4B layout, and ffmpeg's licence. Also the ticket 10 against ticket 28 conflict over where the AO3 commercial-use line goes.
- **Risks** carried into the spec: the 190 MiB margin for analysis, the split voice model not yet heard, attribution scores differing across llama.cpp builds, untuned Emotion, untested Linux hosts.

## Comments

- 2026-10-12, M1 open questions settled by the user in a grilling session and written into the spec: the second labelling run joins analysis in M3 (earlier Works get it when Review is first opened); long lines are voiced by sentence and joined at 0.3 s, with sentence rules a required part of the Language pack; pause start values 1.5 s (long), 2.5 s (Section break) and 0.3 s (verse), all six tuned by ear in M1; kinds of text from markup only in M1; heading patterns an optional part of the pack; TXT encoding detected with charset-normalizer; the Character list on a whole novel is measured by an early M1 build ticket; the Narrating Character per chapter by majority of its chunks; "wait for my review before voicing" as a setting (off by default, from M3); Characters sharing a Voice kept out of the same chapter; unknown-gender Characters get the least-used Voice; one M4B per Work (AAC mono 64 kbps) and one MP3 per chapter (mono 96 kbps); lingua-py as the language detector; ffmpeg as an aggregate; the `base` image flavour and llama.cpp b11318 confirmed as pins. Fourteen non-M1 items remain in `docs/spec/08-open-questions.md`.
