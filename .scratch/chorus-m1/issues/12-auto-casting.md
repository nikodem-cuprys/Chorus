# Auto-casting

Type: task (AFK)
Status: ready-for-agent
Blocked by: 04, 11

## What to build

After analysis, every Speaker gets a Voice from the built-in Voices of the Work's Language pack. Cloned Voices are never auto-cast.

- **Narrator:** the pack's default Narrator Voice (`af_bella`), never given to a Character.
- **Narrating Character:** in a first-person chapter, the Narrator and the Narrating Character share one Voice, cast by that Character's traits. This is the one exception to the rule above.
- **Characters:** those with the most lines get unique Voices from the 11 left. The rest share the closest match by labels. Characters who share a Voice should never both speak in the same chapter; where that is impossible, pick the pair with the fewest chapters in common.
- **Children and elderly Characters** get the closest adult Voice of their gender.
- **Unknown gender:** matched on age band across all 11 Character Voices, preferring the Voice with the fewest lines so far.
- Each Character records that its Voice was auto-cast. The Work page lists the cast (Character, line count, Voice) for checking.

## Acceptance criteria

- On the Alice tea-party passage, the four Characters get four different Voices, none of them `af_bella`.
- In "A Scandal in Bohemia", Watson's lines and the narration share one Voice that is not `af_bella`.
- Unit tests: a cast of 20 Characters over 5 chapters with no shared Voice speaking in the same chapter where possible; unknown-gender Characters spread over the least-used Voices.

## Spec

`docs/spec/03-pipeline.md` (Casting), `docs/spec/04-models-and-libraries.md` (Built-in Voices).
