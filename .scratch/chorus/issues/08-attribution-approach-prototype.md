# Speaker attribution and emotion approach, judged on the sample passages

Type: prototype
Status: resolved
Blocked by: 02, 06

## Question

Which approach should Chorus use for Speaker attribution, Emotion and Mood? Run the 1-3 approaches recommended by the research on the sample passages within 4 GB, and have the user compare the resulting Scripts side by side (who speaks each line, which Emotion). Resolves with the chosen approach and the known failure cases that the review UI must make easy to fix.

## Comments

- 2026-10-01, prototype run, waiting for the user's verdict. Both approaches ran on the six sample passages (288 quotes, 10,621 words) with Qwen3.5-4B Q4_K_M on the 1050 Ti (llama.cpp b11318, CUDA 12 build, all layers on the card, 8k context, thinking off, about 19 tokens/s). Speakers scored against a reference labelling made by Claude from the texts, not by the user.

  | Passage | Quotes | A: BookNLP + LLM, right | B: LLM-only, right |
  |---|---|---|---|
  | Pride and Prejudice ch. 1-2 | 64 | 58 | 58 |
  | Alice, tea party | 128 | 120 | 125 |
  | Holmes | 40 | 36 | 39 |
  | Jane Eyre ch. 1 | 29 | 26 | 26 |
  | Metamorphosis | 18 | 11 | 11 |
  | Crime and Punishment | 9 | 8 | 8 |
  | Total | 288 | 259 (89.9%) | 267 (92.7%) |
  | Time for all six | | 1644 s | 1343 s |

  - A takes the Speaker from BookNLP where the speaker is mentioned in the quote's own paragraph (206 quotes; 195 right, 11 wrong) and from the LLM elsewhere. Three variants were tried: Character list from BookNLP clusters alone (rejected: renamed Alice as "Elsie", called third-person passages first-person; kept in `rejected/`); text-based list plus BookNLP speakers added under BookNLP's own phrase (267/288, but duplicates such as "her mother" next to Mrs. Bennet); the same with an LLM check that merges such phrases into existing Characters (259/288: it also merged the father, the sister and the drunken man into the wrong Character). The table shows the last.
  - Failure cases seen: Characters missing from the list, so their lines become "Unknown" (Metamorphosis family); turn-taking lost in long untagged exchanges (Bennets, three lines); a line addressed to someone given to that person ("I hope Mr. Bingley will like it, Lizzy" to Lizzy); speakers only described, not tagged (the maids in Jane Eyre; "he called me 'Rat! Rat!'"); thoughts and group lines given to the Narrator; BookNLP pinning "said he" to the wrong person; an invented Character ("Joan" from a mispronounced "Jane"); the first-person narrator missing from the Character list (now added by code); runaway alias and Scene lists until the output was cut off (now capped in the output schema); Emotion often off ("happy" for "Wicked and cruel boy!"); Scenes split with no change of setting (Holmes: five Scenes in the first five paragraphs).
  - The line splitter treats a verse sung inside a speech as narration (the Hatter's song), because the quote spans paragraphs.
  - Setup: the llama.cpp server build b11318 hung after one or two requests on this machine, so each call starts the command-line program. llama.cpp projected about 3.0 GB at 8k context against 3.3 GB free with a desktop on the card; the 16k context from ticket 02 was not used. BookNLP 1.0.8 needed three one-line Windows path fixes, `setuptools<81` and `PYTHONUTF8=1`; it ran on CPU in 16 to 46 s per passage. `research/analysis-models-in-4gb.md`, referenced by ticket 02, does not exist.
  - Not done: approach C (go_emotions baseline); any tuning of the Emotion prompt; a run with thinking on.
  - Files: `../prototypes/attribution/` (`compare.html`, `score.py` with the reference, `scripts/`, `booknlp/`, `rejected/`). Models and environments are outside the repo in `C:\Users\nikod\AppData\Local\chorus-frozen\` (`llm/`, `booknlp-env/`) and `C:\Users\nikod\booknlp_models\`.

## Answer

Chorus uses approach B: LLM-only chunked Speaker attribution with a global Character and alias list (Qwen3.5-4B Q4_K_M on llama.cpp, 8k context, thinking off). Decided by the user on 2026-10-01 after comparing the Scripts in `compare.html`. Their reason: most of the lines B gets wrong are unclear in the text itself. BookNLP is dropped, so the pipeline has no English-only attribution step.

B scored 267 of 288 speakers (92.7%) against A's 259 (89.9%) and ran faster (1343 s against 1644 s for the six passages). The score is against a reference made by Claude, not by the user.

Failure cases the review UI must make easy to fix:

- A Character missing from the Character list, so their lines become "Unknown" (Metamorphosis family): add a Character and assign many lines at once.
- Turn-taking lost in long untagged exchanges: reassign a run of lines quickly.
- A line given to the person it addresses instead of the one who says it.
- Speakers only described, never tagged (the maids in Jane Eyre).
- Thoughts and group lines given to the Narrator.
- An invented Character ("Joan" from a mispronounced "Jane"): merge or delete a Character.
- Emotion often wrong: change the Emotion on a line.
- Scenes split with no change of setting: merge Scenes.
- A verse sung inside a speech treated as narration, because the quote spans paragraphs (a line-splitter fault, not the model's).

Left open: the Emotion prompt was not tuned, approach C (go_emotions baseline) and a thinking-on run were not tried, and the llama.cpp server build b11318 hung on this machine, so each call started the command-line program.
