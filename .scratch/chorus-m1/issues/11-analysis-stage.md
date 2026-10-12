# Analysis stage

Type: task (AFK, needs the GTX 1050 Ti)
Status: ready-for-agent
Blocked by: 02, 03, 09, 10

## What to build

Approach B as a job on the `gpu` queue: the Character list, then Speaker attribution with Emotion and intensity. No second labelling run and no review queue (both M3).

- One child process per analysis: it starts llama.cpp's server (Qwen3.5-4B Q4_K_M, all layers on the card, 8k context, `-np 1`, thinking off, temperature 0), runs every request, stops the server and exits.
- Chunks of whole paragraphs of about 900 words; only lines that will be voiced are analysed.
- **Character pass:** chunk by chunk, one global list with canonical name, aliases, gender and age band, merging rather than duplicating; for each chunk, first or third person and the narrating Character. Each chapter takes the majority answer of its chunks as its Narrating Character (or none); a missing Narrating Character is added to the list. Trim the list for the prompt with the rule chosen in ticket 03.
- **Attribution pass:** chunk by chunk, with the list and the last 150 words of the previous chunk, every quoted line gets a Speaker (a Character, the Narrator, or Unknown), a kind (speech, thought, written), one of the nine Emotions (neutral, happy, excited, amused, angry, sad, afraid, anxious, surprised) and an intensity (normal, strong). In a first-person chapter the Narrating Character's own lines get their name, never the Narrator. The prompts start from the prototype's (`.scratch/chorus/prototypes/attribution/approach_b.py`), without disgusted and without Scenes.
- Output constrained by JSON schemas; prompts in English. The analysis model sits behind an engine interface.
- Every finished chunk is saved, so the stage continues where it stopped.
- When analysis ends, voicing is queued for the Work (once ticket 13 exists).

## Acceptance criteria

- The six sample passages, imported as TXT, are analysed in the container; Speakers are scored with `.scratch/chorus/prototypes/attribution/score.py` against the reference. Record the score here; expect about 259 to 267 of 288.
- In "A Scandal in Bohemia" the Narrating Character is Watson; in Pride and Prejudice there is none.
- The card's memory is sampled during the run, with a desktop on the card, and the peak recorded here (expect about 3.3 GB added).
- Killing the worker mid-analysis and starting again resumes from the last saved chunk.

## Spec

`docs/spec/03-pipeline.md` (Analysis), `docs/spec/04-models-and-libraries.md` (Analysis model, Measurements), `docs/spec/02-architecture.md` (GPU turn-taking, Engines).
