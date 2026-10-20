# Analysis stage

Type: task (AFK, needs the GTX 1050 Ti)
Status: resolved
Blocked by: 02, 03, 09, 10

## What to build

Approach B as a job on the `gpu` queue: the Character list, then Speaker attribution with Emotion and intensity. No second labelling run and no review queue (both M3).

- One child process per analysis: it starts llama.cpp's server (Qwen3.5-4B Q4_K_M, all layers on the card, 8k context, `-np 1`, thinking off, temperature 0), runs every request, stops the server and exits.
- Chunks of whole paragraphs of about 900 words; only lines that will be voiced are analysed.
- **Character pass (delta form, ticket 03):** chunk by chunk, the model sees the list so far and returns only new Characters and new aliases; code merges them, refusing an alias that is not a name (at most four capitalised words, no pronouns or lists), is not in the chunk, or already belongs to another Character, and merging a re-listed Character. Start from `DELTA_SYSTEM` in `.scratch/chorus/prototypes/novel-cast/cast.py`. Ask for gender and age band from what the text says, "unknown" only when it says nothing (ticket 03 got "unknown" for every age band). For each chunk also first or third person and the narrating Character; each chapter takes the majority answer of its chunks as its Narrating Character (or none); a missing Narrating Character is added to the list.
- **No trimming:** every attribution prompt gets the whole Character list (ticket 03).
- **After attribution,** Characters with no lines are dropped from the list.
- **Attribution pass:** chunk by chunk, with the list and the last 150 words of the previous chunk, every quoted line gets a Speaker (a Character, the Narrator, or Unknown), a kind (speech, thought, written), one of the nine Emotions (neutral, happy, excited, amused, angry, sad, afraid, anxious, surprised) and an intensity (normal, strong). In a first-person chapter the Narrating Character's own lines get their name, never the Narrator. The prompts start from the prototype's (`.scratch/chorus/prototypes/attribution/approach_b.py`), without disgusted and without Scenes.
- Output constrained by JSON schemas; prompts in English. The analysis model sits behind an engine interface.
- Every finished chunk is saved, so the stage continues where it stopped.
- When analysis ends, voicing is queued for the Work (once ticket 13 exists).

## Acceptance criteria

- The six sample passages, imported as TXT, are analysed in the container; Speakers are scored with `.scratch/chorus/prototypes/attribution/score.py` against the reference. Record the score here; expect about 259 to 267 of 288.
- In "A Scandal in Bohemia" the Narrating Character is Watson; in Pride and Prejudice there is none.
- Most Characters on the sample passages get an age band other than "unknown"; no Character without lines is left on the list.
- The card's memory is sampled during the run, with a desktop on the card, and the peak recorded here (expect about 3.3 GB added).
- Killing the worker mid-analysis and starting again resumes from the last saved chunk.
- llama-server is started with `-m chorus.firstrun.gguf_path()`; with the network cut after first run, analysis still starts (ticket 10's third criterion).

## Spec

`docs/spec/03-pipeline.md` (Analysis), `docs/spec/04-models-and-libraries.md` (Analysis model, Measurements), `docs/spec/02-architecture.md` (GPU turn-taking, Engines).

## Answer

Built on 2026-10-20: `backend/chorus/analysis.py` (the stage and its job), `backend/chorus/analysis_model.py` (the engine interface and `LlamaServer`), migration 0005 (the `character` table; Speaker, Emotion and intensity on lines; a chapter's Narrating Character; `work.analysis`), `POST /api/works/<id>/analysis`, and on the Work page a Characters list, Speakers and Emotions in the Lines view, and "Analyse again".

- **When:** every import queues analysis on the `gpu` queue (`CHORUS_ANALYSE_AFTER_IMPORT`, on by default; off in the unit tests and for the integration tests, which import whole books). Work states: imported, analysing, analysed (until voicing exists), failed with the reason. Voicing is not queued yet (ticket 13 adds it where `analysis_job` ends).
- **Child process:** the job runs `python -m chorus.analysis <job id>`, which starts llama-server with `-m firstrun.gguf_path() -ngl all -c 8192 -np 1` on a free local port, sends every request to `/completion` (ChatML with the think block closed, temperature 0, JSON schema), stops the server and exits. Its errors go to the job and the Work as message keys.
- **Chunks:** whole paragraphs of about 900 words of voiced lines, never across a chapter or the front/back matter. The Work title line Chorus makes is the Narrator's and not analysed (it was a chunk and a request of its own).
- **Character pass:** `DELTA_SYSTEM` from ticket 03, with gender and age asked from what the text states or implies (titles, professions, spouses mean adult; schoolchildren child; and so on), gender and age placed before aliases in the schema, and two additions found on the first run (below): a Character never named is listed under a short description, and the narrator's name is the one others use, never "I". Code checks aliases as ticket 03 chose (at most four capitalised words, particles aside; no pronoun, list or comma; in the chunk; not someone else's). A re-listed Character is merged and fills in an unknown gender or age.
- **Narrating Character:** each chapter (and the front and back matter) takes the majority of its chunks' answers; **a tie goes to first person**, and "I" or "the narrator" never count as a name. A Narrating Character missing from the list is added (with gender and age unknown).
- **Attribution pass:** the prototype's prompt, with intensity normal or strong ("strong" only when clearly more intense), the nine Emotions, no Scenes; the whole list in every prompt, and the last 150 words of the previous chunk. Quotations are numbered within the chunk. A line the model leaves out is Unknown, speech, neutral. Narrator lines have no Emotion; thoughts are never strong. Afterwards, Characters with no lines leave the list unless they narrate a chapter.
- **Saved as it goes:** each chunk is committed with `work.analysis` (stage, chunks done, each chunk's narration answer, Narrating Characters). A new analysis of an analysed Work starts over: the Script is cut again (with the Work's current language) and the list emptied.
- **Starting again after a kill:** the Work still says "analysing", so `POST /analysis` is allowed then (refused only while importing or while an analysis of it is already queued), and continues from the saved chunk. A job Celery hands out again after a crash (after its one-hour visibility timeout) does nothing if the Work's analysis finished after that job was asked for.

Acceptance, in the container on the GTX 1050 Ti with a desktop on the card:

- **Score:** 270 of 288 Speakers right against ticket 08's reference (`score.py`'s reference and name matching; our quotations map in order onto the prototype's). Per passage: Pride and Prejudice 59/64, Alice 126/128, Holmes 33/40, Jane Eyre 27/29, Metamorphosis 17/18, Crime and Punishment 8/9. Analysis took 1,045 s for the six (ticket 24: about 1,250 s with the full-list form). Holmes' misses are the note Watson reads and the watermark letters, given to Unknown.
  - The first run, with ticket 03's prompt unchanged and a strict majority, scored **241**: the mother, father and sister in Metamorphosis and the drunken man were never listed (the prompt forbids descriptions as aliases and never said an unnamed person gets one as a name); Jane Eyre's narrator came out as a Character "I"; and Holmes' chapter had one chunk answered "first, Watson" and one "third", so it got no Narrating Character, Watson was never added and all his lines went to Holmes. The changes above fixed all three.
- **Narrating Character:** Watson in "A Scandal in Bohemia"; none in Pride and Prejudice (also Jane Eyre in Jane Eyre).
- **Age band:** 18 of 20 Characters on the samples have one; the two "unknown" are Watson and Jane Eyre, added by the narrator rule. No Character without lines is left (Mr. Morris-style silent entries are dropped; unit test).
- **Card memory** (sampled every 2 s over twelve analyses): before loading 715 to 1,177 MiB, peak 3,973 MiB of 4,096; added 2,796 to 3,208 MiB, so up to 3.2 GB, as expected. The card is back to idle after every job.
- **Kill and resume:** Alice re-analysed, the worker container killed during attribution chunk 3 of 3 (2 saved; the card was free at once), started again and asked again: the new job began at attribution chunk 3, ran no Character pass, and finished.
- **Network cut:** the stack restarted on an `internal` Docker network (no route out; `huggingface.co` unresolvable from the worker), and Crime and Punishment analysed in full.
- **Tests:** `tests/test_analysis.py` (alias rules, merging, the narrator rule, chunks, the stage end to end with a stand-in model, resume after a crash, starting over, the job and its failures, the API); `Lines.test.tsx` and `WorkPage.test.tsx` for Speakers and the Characters list.

Left for later:

- **The killed job's row** stays "running" until Celery hands it out again an hour later and it finishes as done with nothing to do; resuming jobs by themselves after a crash is ticket 15.
- **A Narrating Character added by the rule** has gender and age unknown, which auto-casting (ticket 12) will match on age band only.
- **Quotations nobody says aloud** (Holmes' note and watermark letters) went to Unknown rather than the Narrator.
- **Emotion** was not checked against anything; the spec already calls it untuned.
