# Job control and progress

Type: task (AFK)
Status: ready-for-agent
Blocked by: 11, 13

## What to build

Full control over the long-running jobs (analysis, voicing, export), because a novel takes about a day.

- **Pause:** stops after the current line or chunk and frees the GPU (the child process exits).
- **Resume:** continues where it stopped.
- **Cancel:** stops and keeps every finished line or chunk, so starting again does only what is missing. Throwing audio away is a separate, explicit action ("discard audio"), with a confirmation.
- **After a crash or reboot:** a running job resumes by itself when Chorus is back up; a paused job stays paused.
- **Progress over SSE:** the stage, chapter x of y, lines done of total, a percentage, and a time-left estimate from the measured speed. Shown on the Work page and in the list of Works.
- **Work states:** importing, analysing, voicing, ready to listen, failed (with the reason); a paused job shows as paused.
- The controls sit on the Work page beside the job.

## Acceptance criteria

- Pausing a voicing job frees the card within one line (checked with `nvidia-smi`); resuming continues at the next line.
- Cancelling and starting again voices only the lines without audio.
- Restarting the `worker` container mid-job resumes it; a paused job stays paused across the restart.
- The time-left estimate is within a reasonable range of the real time on the sample passages (record both here).

## Spec

`docs/spec/02-architecture.md` (Jobs), `docs/spec/05-data-model.md` (Job, Work states), `docs/spec/06-screens.md` (Work page).
