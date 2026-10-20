# Voicing stage

Type: task (AFK, needs the GTX 1050 Ti)
Status: resolved
Blocked by: 10, 12

## What to build

Chatterbox 500M as a job on the `gpu` queue, run straight after analysis, writing one FLAC file per line.

- One child process per voicing job, FP32, with the model's two halves loaded in turn: T3 over a batch of lines (a chapter), off the card, then S3Gen over the same batch. The working code is in `.scratch/chorus/prototypes/chatterbox-fit/fit.py`. The voice model sits behind an engine interface.
- Queued automatically when a Work's analysis and casting finish: in M1 every Work goes straight from analysis to voicing.
- Reading order, chapter by chapter, so a chapter is complete before the next starts.
- **Per line:** the Speaker's Voice and its neutral reference clip; a Character line's Emotion and intensity looked up in the pack's Emotion settings; the Narrator always neutral (0.5 / 0.5); thoughts never strong; letters neutral; nothing above `exaggeration` 0.9.
- **Seed:** each line gets a seed when first voiced and stores it.
- **Long lines:** split into sentences with the pack's sentence rules, each voiced with the line's Voice, settings and seed, joined with 0.3 s between them into the line's one file.
- Chatterbox's watermark stays on.
- Lines that are not voiced are skipped.
- Every voiced line is saved at once, so the stage continues where it stopped.
- Line audio is 24 kHz FLAC on the data volume; each line records the Voice, Emotion, intensity, text and seed its take was made with.

## Acceptance criteria

- The six sample passages are voiced in the container with no spill into system memory, with a desktop on the card. Card peak and speed are recorded here (expect about 2.5 GB added and about 2.2 times real time).
- Voicing the same line twice with its stored seed gives the same take.
- A long narration paragraph is voiced as several sentences in one file.
- Killing the worker mid-chapter and starting again voices only the missing lines.
- Chatterbox is loaded with `ChatterboxTTS.from_local(chorus.firstrun.chatterbox_dir(), ...)`, never `from_pretrained`; with the network cut after first run, voicing still starts (ticket 10's third criterion).

## Spec

`docs/spec/03-pipeline.md` (Voicing), `docs/spec/02-architecture.md` (GPU turn-taking), `docs/spec/04-models-and-libraries.md` (Voice model, Emotion settings, Measurements).

## Answer

Built on 2026-10-20: `backend/chorus/voicing.py` (the stage and its job), `backend/chorus/voice_model.py` (the engine interface and `Chatterbox`), `backend/chorus/pauses.json` (the pause settings; ticket 14 uses the rest), migration 0007 (each line's seed and current take), `POST /api/works/<id>/voicing`, and `GET /api/works/<id>/lines/<position>/audio`.

- **When:** queued at the end of every analysis job, after casting (`CHORUS_VOICE_AFTER_ANALYSIS`, on; off in the unit tests). Work states: analysed, voicing, voiced (until assembly, ticket 14), failed with the reason. `POST /voicing` starts it by hand and continues a stopped one.
- **Child process:** `python -m chorus.voicing <job id>` loads Chatterbox with `ChatterboxTTS.from_local(firstrun.chatterbox_dir(), "cpu")`. Per batch, T3 goes onto the card and runs over every sentence of the batch, goes back to the CPU, then S3Gen goes on for the same sentences. Each sentence is seeded before each half. The sampling settings are `generate()`'s (temperature 0.8, repetition penalty 1.2, min_p 0.05, top_p 1.0). Reference clips are prepared once per Voice, on the CPU. The watermark stays on.
- **Batches and order:** reading order; a batch is a chapter (or the front or back matter), so a chapter is complete before the next starts.
- **Per line** (`plan_line`): a Character's line in the Character's Voice; narration in the chapter's narration Voice (the Narrating Character's in a first-person chapter, `casting.narration_voice`); a quotation by Unknown in the Narrator's Voice with its Emotion. The Narrator and letters are neutral (0.5 / 0.5); thoughts never strong; `exaggeration` capped at 0.9.
- **Seed:** given when a line is first voiced and kept. **Long lines:** the pack's sentence rules split them; the sentences are joined with `between_sentences` (0.3 s) into the line's one file. A line with no letters or digits ("* * *") is 0.25 s of silence, since Chatterbox given no words says a sentence of its own.
- **Saved as it goes:** each line's FLAC (24 kHz, 16-bit) is written to `data/works/<id>/lines/<line id>.flac` and its take (file, Voice, Emotion, intensity, text, seed, length) committed as soon as its audio is done. A line needs voicing while it has no take or its take was made with other values, so a stopped job, started again, voices only what is missing. A new analysis, which cuts the Script again, deletes the Work's line audio.
- **Memory:** the child sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` before CUDA starts. S3Gen's buffers grow with the length of a sentence, and with the default allocator a 35 s sentence left 3.85 GB reserved for 2.4 GB in use.
- **Dependencies:** numpy and soundfile (already in the GPU stack, same pins) are now in `pyproject.toml`, so line audio can be written and tested outside it. Changing `pyproject.toml` rebuilds the image's dependency layer, which took 70 minutes here because the uv cache was empty.

Acceptance, in the container on the GTX 1050 Ti with a desktop on the card:

- **Six sample passages voiced:** 541 lines, 3,889 s (65 min) of audio, in 7,834 s of job time including loading the model each time: **2.0 times real time** (per batch 1.7 to 2.1). Every take is 0.27 to 0.64 s per word (median 0.36), with none outside 0.15 to 1.0 s, so there are no runaway or cut-off generations by length. **Not listened to.**
- **Card memory**, sampled every 2 s with Windows' shared-memory counter: with the allocator setting, Pride and Prejudice peaked at **3,518 MiB on the card, 3,100 MiB added** (before: 418 MiB), in T3's phase; shared memory at most 124 MiB, so **no spill** (ticket 24 saw 123 to 192 MiB throughout on runs that fit). The first run of all six, without the setting, peaked at 3,979 MiB (about 100 MiB free) in S3Gen's phase, with shared memory at most 158 MiB. Both are above the 2.5 GB expected: ticket 25 measured eight short lines; whole passages hold longer sentences, and T3 alone is 2.1 GB in FP32.
- **Same seed, same take:** Pride and Prejudice's 96 takes were forgotten and voiced again with their stored seeds: every file the same length, 0.1% of samples one 16-bit step apart (GPU rounding), none further.
- **Long line:** a 5-sentence narration paragraph of Pride and Prejudice is one 31 s file with exactly 4 silences of 0.3 s.
- **Kill and resume:** Crime and Punishment's takes forgotten and voicing started; the worker container killed with 10 of 26 lines saved, partway through the chapter; started again and asked again, the new job voiced exactly the 16 missing lines.
- **Network cut:** that resumed job ran with the stack on an `internal` network (`huggingface.co` unresolvable from the worker). Ticket 10's third criterion is now met for both analysis (ticket 11) and voicing.
- **Unit tests** (`tests/test_voicing.py`, with a stand-in model): each line's Voice and settings, FLAC files chapter by chapter, sentences joined with the pause, the same take from the stored seed, a stopped run voicing only what is missing, a changed Emotion voiced again, audio discarded by a new analysis, the job, and analysis queueing voicing.

Left for later:

- **Progress during T3's phase:** lines are saved only after S3Gen, so a chapter shows no progress for the first half of its time (about 11 minutes for Crime and Punishment's one chapter), and a job stopped then loses that chapter's T3 work. Ticket 15's pause and progress should look at this.
- **The killed jobs' rows** stay "running" until Celery hands them out again an hour later, when they find nothing to voice (ticket 15).
- **`docker compose up --build` hung** twice with no build step started (web and worker build the same image); `docker compose build --progress plain worker` worked. Not investigated.
