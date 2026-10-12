# Character list on a whole novel

Type: prototype (AFK run, then the user decides)
Status: ready-for-agent
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
