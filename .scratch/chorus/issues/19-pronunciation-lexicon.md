# Pronouncing names and invented words

Type: prototype
Status: resolved
Blocked by: none

## Question

Chatterbox 500M takes plain text, not phonemes. Can a respelling (e.g. "Hermione" as "Her-my-oh-nee") reliably fix how it says names and invented words from fantasy and fanfic? Try it on a handful of hard names. Then decide the per-Work pronunciation lexicon: where entries come from (the user, words Chorus flags as unusual), where the user edits them in the review screen from ticket 09, and whether a change re-voices every affected line. Resolves with whether respelling works and the lexicon design.

## Answer

Respelling works well enough to build on, as a one-word respelling applied only to words the user has heard said wrong. Judged by the user by ear on 2026-10-03: ten names, each written three ways, three clips per way (Chatterbox 500M, Voices `af_bella` with two seeds and `bm_lewis`).

| Name | As written | Respelled with hyphens | Respelled as one word |
|---|---|---|---|
| Hermione | right every time | wrong, odd pause (Her-my-oh-nee) | close but off (Hermyohnee) |
| Daenerys | right every time | wrong, odd pause (Duh-nair-iss) | close but off (Danairiss) |
| Cthulhu | right every time | close but off (Kuh-thoo-loo) | right every time (Kathooloo) |
| Siobhan | some clips only | close but off, odd pause (Shiv-awn) | some clips only (Shivawn) |
| Niamh | some clips only | right every time (Neev) | right every time (Neeve) |
| Nynaeve | right every time | right every time (Nye-neev) | right every time (Nyneeve) |
| Wei Wuxian | right every time | right every time (Way Woo-shyen) | right every time (Way Wooshyen) |
| Kvothe | close but off | right every time (Kwoh-th) | right every time (Quothe) |
| Thranduil | right every time | wrong, odd pause (Thran-doo-il) | right every time (Thrandooill) |
| Geralt | right every time | close but off (Geh-ralt) | right every time (Gherralt) |

- **Most names need nothing:** 7 of the 10 were right every time as written.
- **Respelling fixed 2 of the 3 problem names** (Niamh, Kvothe). Siobhan stayed unreliable in every spelling; Chorus has no further fix for such a word.
- **A respelling can make a good name worse:** Hermione and Daenerys went from right to "close but off". So nothing is respelled automatically.
- **One word, no hyphens:** hyphens gave 3 wrong names and 4 odd pauses; one-word respellings always sounded natural in the sentence. The user's overall choice was "as one word".
- **Consistency:** the same text "sometimes" came out differently between takes or Voices.

The pronunciation list, decided by the user:

- **One list per Work.** An entry is a word and its respelling. The respelling replaces the word only in the text sent to the voice model; the Script's text is unchanged.
- **Where entries come from:** Chorus lists the Character names and the words not found in an English dictionary as candidates, each with a play button. A candidate has no effect until the user types a respelling for it. The user can also add any other word.
- **Where it is edited:** a Pronunciation panel beside the cast in the reading view from ticket 09, with a play button, a respelling field and a "try it" button per word. Selecting a word in any line sends it to the panel.
- **Try before saving:** "try it" renders the word in a short sentence with the Narrator Voice (about 20 s on the 1050 Ti), because respellings sometimes miss.
- **Re-voicing:** adding or changing a respelling re-voices every line that contains the word and re-assembles the affected chapters, so the name sounds the same everywhere.

Not settled here: which dictionary decides that a word is unusual; how a word is matched in the text (capitalisation, possessives such as "Niamh's", names of two words); what "try it" does while a long generation job holds the GPU (job handling is ticket 20); and whether a respelling behaves the same on lines with a strong Emotion or on the other ten Voices, which were not tested. The "should sound like" targets were Claude's, and the user did not dispute any of them.

Listening page, scripts and the 90 clips: `../prototypes/pronunciation/` (`listen.html`, `gen.py`, `build_page.py`, `out/`).
