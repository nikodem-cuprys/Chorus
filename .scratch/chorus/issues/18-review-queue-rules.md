# Which lines the review queue asks about

Type: prototype
Status: resolved
Blocked by: none

## Question

The analysis model gives no confidence score. Ticket 09's four rules catch 14 of approach B's 21 wrong lines on the sample passages, at the cost of 70 questions. Try better rules and a second pass in which Qwen3.5-4B scores its own doubt per line, on the same sample Scripts (`../prototypes/attribution/`, `../prototypes/script-review/`). Resolves with the chosen way of picking queue lines, its catch rate and its number of questions on the samples.

## Answer

Chosen by the user on 2026-10-03: five text rules plus a blind second labelling run. On the six sample passages (288 quoted lines, 21 wrong in approach B's Scripts) this asks 40 questions and catches 19 of the 21, against 61 questions and 14 catches for ticket 09's rules.

A quoted line goes into the queue when any of these holds:

| Rule | Lines asked | Wrong lines among them |
|---|---|---|
| No Speaker was found (Unknown, or a name outside the Character list) | 7 | 7 |
| A quoted line is given to the Narrator | 13 | 2 |
| The paragraph's own narration says "said X" and the label is someone else | 13 | 10 |
| The same Speaker has two paragraphs in a row and the second has no narration | 5 | 4 |
| The line addresses its own Speaker by name | 4 | 2 |
| A second labelling run names a different Speaker, or none | 23 | 14 |

- **Second run:** approach B's attribution pass again, with the same Character list and prompt, but in 600-word chunks instead of 900, so every line is read in different context. It is no more accurate than the first run (266 of 288 right against 267); its value is that the two runs disagree on wrong lines. It took 923 s on the samples, on top of 1,344 s for the first analysis: about 70% more.
- **Missed lines:** two. "Impossible, Mr. Bennet, impossible..." given to Lizzy instead of Mrs. Bennet, and an unattributed servant's line in Jane Eyre given to Mrs. Reed. Both runs made the same mistake and no tight rule fires.
- **Self-rating does not work:** shown its own labels and asked to rate each sure, unsure or wrong, Qwen3.5-4B rated 279 of 288 "sure", including every line it had labelled Unknown, and never named a different Speaker. It caught 1 wrong line for 9 questions, in 637 s. Dropped.
- **Dropped from ticket 09's rules:** "marked as a thought" (27 questions, no catches) and "deep in an untagged exchange" (15 questions, 3 catches). "Mentions its own Speaker" is replaced by the stricter "addresses its own Speaker".
- **Other ways tried:** tight rules alone 32 questions, 16 catches; a wider rule set alone 48 and 19; wide plus the second run 54 and all 21. Three of the wide rules were written after looking at the missed lines, so those scores are fitted to this sample.
- **Counting:** ticket 09 reported 70 questions; 61 of them are about lines and the rest about Characters and Scenes. Those Character and Scene questions were not part of this ticket and are unchanged.
- **Limits:** six passages and 21 wrong lines is a small base, and the reference labels are Claude's from ticket 08, not the user's. The speech-verb list in the "said X" rule is English, so that rule needs a list per language. The main review screen stays the place where the remaining errors are found.

Scripts and results: `../prototypes/review-queue/` (`rules.py` scores every rule and combination, `rerun.py` is the second run, `doubt.py` the rejected self-rating).
