# Auto-casting

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-20: `backend/chorus/casting.py`, migration 0006 (the Work's Narrator Voice; each Character's Voice and whether it was auto-cast), and the cast on the Work page (each Character's Voice, marked "auto-cast", and the Narrator's).

- **When:** at the end of every analysis job, after the Work is marked analysed. By hand: `python -m chorus.casting <work id>`.
- **Narrator:** the pack's default (`af_bella`), never given to a Character.
- **Narrating Character:** cast like any Character, but first, and the narration of the chapters they narrate counts as their lines, so nobody shares their Voice lightly. `casting.narration_voice(work, chapter, characters)` gives the Voice reading a chapter's narration: the Narrating Character's in a first-person chapter, the Narrator's elsewhere. Voicing (ticket 13) uses it.
- **Characters**, Narrating Characters first and then by lines, most first, each take an unused Voice of their gender while one is left (closest age first). The rest share: the Voice of their gender whose Characters share the fewest chapters with them, then the closest age, then the fewest lines so far. A Character's chapters are those they speak in and those they narrate.
- **Age:** child and elderly are matched as adult; young adult prefers `am_fenrir`, the one young-adult Voice.
- **Unknown gender:** matched across all 11 Character Voices with the same order, so minor unnamed speakers spread over the least-used Voices.
- **Kept:** a Voice the user chose (`voice_auto` false) is not changed and counts as taken (no interface for it until milestone 3). Cloned Voices are never auto-cast.

Found on the sample passages and fixed in analysis (ticket 11's code):

- **Watson was cast with a female Voice.** The narrator rule added him with gender unknown. The Character pass now also gives the narrator's gender and age with each chunk's narration answer, and the rule fills them in. Watson is now male, adult.
- **Mr. Bennet was cast with a female Voice.** The model said his gender was unknown. A new optional Language pack part `names` lists titles that say a gender (English: "Mr.", "Sir", "Lord", "Mrs.", "Miss", "Lady" and so on), and a gender left unknown is taken from a title in the name or an alias.
- **Alice had seven Characters for four people** ("the Hatter" and "Hatter", "the March Hare" and "March Hare", "the Dormouse" and "Dormouse"), which would have given each person two Voices. `names` also lists articles, which are left out when names are compared.

Acceptance, in the container, after analysing the six sample passages again (now 276 of 288 Speakers right, Holmes 40 of 40):

- **Alice:** Alice `af_alloy`, Hatter `am_eric`, March Hare `am_michael`, Dormouse `bm_daniel`: four different Voices, none `af_bella`.
- **"A Scandal in Bohemia":** Watson narrates the chapter; his lines and its narration are both `am_eric`, Holmes is `am_michael`, the Narrator `af_bella` (front matter only).
- Also: Pride and Prejudice: Mrs. Bennet `af_alloy`, Mr. Bennet `am_eric`, Lizzy, Kitty and Lydia three more female Voices. Jane Eyre: Jane (narrating, a child) `af_alloy`, John Reed (a young adult) `am_fenrir`.
- **Unit tests** (`tests/test_casting.py`): 20 Characters over 5 chapters, where no two sharing a Voice speak in the same chapter, and the busiest 10 have Voices of their own; where sharing in a chapter cannot be avoided, the pair with the fewest chapters in common; unknown-gender Characters land on the three least-used Voices; child and elderly get adult Voices, a young adult `am_fenrir`; a Narrating Character keeps a Voice of their own; on a Work, a Voice the user chose is kept, narration counts for the Narrating Character, and `narration_voice` follows the chapter. `tests/test_languages.py` covers the `names` part; `tests/test_analysis.py` the article and title rules.

Left for later:

- Timbre and accent are not used for matching; only gender and age.
- No interface yet for changing a Voice or separating the Narrator from the Narrating Character (milestone 3).
