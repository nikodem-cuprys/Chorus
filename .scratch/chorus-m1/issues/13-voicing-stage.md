# Voicing stage

Type: task (AFK, needs the GTX 1050 Ti)
Status: ready-for-agent
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
