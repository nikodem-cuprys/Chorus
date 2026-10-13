# Character list on a whole novel

Type: prototype (AFK run, then the user decides)
Status: resolved
Blocked by: none

## Question

The Character pass of approach B was only ever run on passages under 2,000 words, with caps of 30 Characters and 8 aliases. On a whole novel, how big does the list get, does it still fit beside a 900-word chunk in 8k context, and does its quality hold? Decide from the result how the list is trimmed for the prompts.

## What to do

- Run the Character pass (from `.scratch/chorus/prototypes/attribution/approach_b.py`) over a whole novel from `.scratch/chorus/samples/raw/` (Pride and Prejudice), with the llama.cpp server in the container image from ticket 24 of the wayfinding (`chorus-llama:b11318-cuda12.6.3-sm61`, model in the `chorus-models` volume), with the caps raised.
- Record per chunk: list size, prompt tokens, time, and whether the output was cut off.
- Record the final list: Characters, aliases, duplicates, invented Characters, named speakers missing.
- Record the per-chunk first or third person answers and each chapter's majority, to check the Narrating Character rule.
- Try at least one trimming approach (for example: only Characters named in this chunk or the one before, plus the last few Speakers) and compare it with the full list on the attribution pass of a few chapters.

## Resolves with

The measurements, a recommended trimming rule, and the user's choice. Ticket 11 uses that rule.

## Spec

`docs/spec/03-pipeline.md` (Analysis, step 3), `docs/spec/08-open-questions.md` (Risks).

## Comments

- 2026-10-13, prototype run, waiting for the user's choice. Pride and Prejudice (`samples/raw/pg1342.txt`): 61 chapters, 121,629 words, 1,767 quotations, 167 chunks of about 900 words inside chapters. Qwen3.5-4B Q4_K_M on the llama.cpp server of ticket 24 (b11318, one slot, 8k context, temperature 0, thinking off) on the GTX 1050 Ti. Code and outputs: `.scratch/chorus/prototypes/novel-cast/` (`book.py`, `cast.py`, `attr.py`, `out/`).

  **Two ways of building the list**

  | | Full list each chunk (approach B as prototyped, Character cap raised to 200) | Delta: only new Characters and aliases, checked and merged by code |
  |---|---|---|
  | Chunks run | first 40 (stopped there) | all 167 |
  | Time | 3,407 s for 40 chunks (85 s each, rising to 137 s) | 4,723 s for all 167 (28 s each); 796 s for the first 40 |
  | Output per chunk | grows with the list: 484 tokens at chunk 1, 2,154 at chunk 40 | flat: mostly 100 to 400 tokens |
  | Largest prompt | 3,444 tokens at chunk 40, and growing; prompt plus output would pass 8k somewhere around chunks 60 to 80 | 3,807 tokens |
  | Cut off | 2 of 40 (one ran to 4,804 tokens) | 4 of 167, each hitting its 1,500-token limit |
  | List at the end | 58 entries at chunk 40, with Mr. Collins three times and Lady Catherine, Miss Darcy, Bingley and Wickham twice each; non-people such as "the patient", "the other ladies"; pronoun aliases in nearly every entry; at chunk 16 the list fell from 27 entries to 13 | 54 entries for the whole book |

  **Quality of the delta list** (with the code checks: an alias must appear in the chunk, start with a capital and not be a pronoun or a list, and must not already belong to someone else)

  - Right: every main Character is there; narration was answered third person in all 167 chunks.
  - Duplicates: Charlotte and Charlotte Lucas, Sir William and Sir William Lucas, Miss Bingley and Caroline Bingley, Kitty and Catherine, Lady Catherine and "Lady Catherine herself".
  - Wrong merges: Mrs. Gardiner, Miss Lucas and Mrs. Annesley as aliases of Elizabeth; Miss Darcy, Georgiana, Miss de Bourgh and Rosings as aliases of Lady Catherine; Mrs. Collins of Mr. Collins; William Goulding of Wickham; Louisa (Mrs. Hurst) of Miss Bingley. Mrs. Gardiner and Georgiana therefore have no entry of their own.
  - About a dozen entries never speak (Mr. Morris, Miss Watson, Sir Lewis de Bourgh, Miss Pope, Pen, Pratt, ...).
  - Aliases turned into copied text ("Jane could not have been wearied by long expectations"): the "must appear in the chunk" check made the model copy sentence starts. A filter of at most four capitalised words keeps 37 real aliases and drops them.
  - Age band came out "unknown" for every Character in this form (the full form filled it in).
  - A first delta run without the code checks (`out/delta-v1`, 24 chunks) had Jane as an alias of Elizabeth by chunk 24 and padded aliases with pronouns and descriptions.

  **Attribution with the novel's list** (approach B's attribution prompt; the delta list after the alias filter)

  | | Roster | Chapters 1 and 2, against the ticket 08 reference |
  |---|---|---|
  | List from the passage alone (tickets 08 and 24) | 12 | 58 of 64 |
  | Whole novel list, every prompt | 54 (858 tokens) | 57 of 64 |
  | Trimmed: Characters named in this chunk or the one before, plus the last five Speakers | 8 to 9 (about 180 tokens) | 42 of 64 |

  - The trimmed roster dropped Mrs. Bennet from chapter 1, which only calls her "his lady", so all 17 of her lines went to Mrs. Long. Trimming by mentions fails whenever a Character is referred to by description.
  - The whole list costs nothing measurable in time: about 100 s per chunk either way.
  - Chapter 43 (Pemberley, 62 quotations), no reference: with either roster most of the Gardiners' lines are wrong, because the list has no Mrs. Gardiner (merged into Elizabeth) and only "Gardiner". With the whole list they went to Mrs. Bennet, Mrs. Long, Mr. Bennet and Mr. Collins; with the trimmed one mostly to Lizzy and Mrs. Hill. 20 of 62 labels differ between the two.

  **Reading:** size is not the problem on a whole novel. 54 entries are under 900 tokens and fit beside a chunk in 8k with room to spare; trimming makes attribution worse. The problem is the list's quality: wrong merges and missing people propagate straight into attribution, and the full-list form gets worse with length and will not fit a novel at all.

## Answer

Chosen by the user on 2026-10-13 from the measurements in the comment above.

- **The list is built as a delta.** For each chunk the model sees the list so far (one line per Character: name, gender, age band, aliases) and returns only Characters who are new and new aliases of listed ones. Code merges them and refuses an alias that is not a name (a pronoun, a list, or anything but at most four words that start with a capital, particles such as "de" aside), does not appear in the chunk, or already belongs to another Character. A re-listed Character is merged, not added. A new Character does not need their name in the chunk (Mrs. Bennet is only "his lady" in chapter 1). The prompt is in `.scratch/chorus/prototypes/novel-cast/cast.py` (`DELTA_SYSTEM`).
- **No trimming:** every attribution prompt gets the whole list. 54 Characters are under 900 tokens; trimming by mentions scored 42 of 64 against 57.
- **List quality:** after attribution, Characters with no lines are dropped automatically. Duplicates and wrong merges are left for the user to merge or split in review (M3). M1's automatic output will contain them.
- **Age band:** ticket 11 fixes the prompt so the model gives gender and age band from what the text says, "unknown" only when it says nothing, and checks on the samples that most Characters get one.
- **Not chosen:** the full-list form (4.3 times slower, output growing with the list, would overflow 8k around chunk 60 to 80 of a novel, loses and duplicates people), and a cleanup request or a further prototype ticket for list quality.

Known weaknesses carried forward: wrong merges propagate into attribution (chapter 43's Gardiners), four of 167 delta chunks were cut off at their 1,500-token limit and added nothing, and the delta list keeps about a dozen people who never speak until the drop after attribution removes them.
