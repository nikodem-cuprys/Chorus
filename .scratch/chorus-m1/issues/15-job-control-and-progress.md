# Job control and progress

Type: task (AFK)
Status: resolved
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

## Answer

Built on 2026-10-21: pause, resume and cancel in `backend/chorus/jobs.py` for every job, checks in the three long stages, recovery at worker start, migration 0010 (each job's arguments, current Celery message and pending request), `POST /api/jobs/<id>/pause|resume|cancel`, `POST /api/works/<id>/discard-audio`, and the job panel on the Work page with progress in the Library list.

- **How a job stops:** pause and cancel of a running job are saved as `request` on its row; the job calls `JobContext.check()` between steps and raises `Stopped`, which the runner turns into "paused" or "cancelled" (with its finish time). A queued or paused job is paused or cancelled at once. A GPU stage's child process exits with `STOPPED_EXIT` (3); the parent reads the request and stops the same way, so the card is freed when the child ends.
- **Where the steps are:** voicing checks before each sentence in each half of the model (`Chatterbox.speak` takes a `step` hook), so it stops within one sentence; T3 work of the unfinished part of a chapter is lost and redone on resume (with the same seeds, so the same takes). Analysis checks before each chunk. Export checks on each ffmpeg progress line and kills ffmpeg; a paused export starts its files over, and the previous export stays as it was.
- **Resume** puts the job on its queue again (`send`), at the back. Every stage continues from what it saved: voicing voices only lines without a current take, analysis continues at its next chunk.
- **Cancel** keeps everything finished. A cancelled voicing leaves the Work "analysed" (the Work page then offers **Voice**, which voices what is missing); a cancelled analysis leaves it "imported" (**Analyse** continues from the saved chunks). A paused job leaves the Work in its stage ("voicing…"), and the job shows as paused.
- **Discard audio**, separately and explicitly: "Discard audio…" on the Work page, then a confirmation naming the number of voiced lines. It deletes every line's take and seed, the line files and the assembled parts, and puts the Work back to "analysed"; refused (409 `work.error.audio_busy`) while a voicing, assembly or export job is queued, running or paused. The Work detail's `voiced_lines` counts lines with a take (a cleared take is JSON `null`, not SQL NULL, so the count casts it).
- **After a crash, reboot or restart:** each job keeps its arguments (`kwargs`) and the id of the Celery message that may run it (`task_id`); any other message for it is ignored. When the worker starts (`chorus.worker`), `recover` sends again every job that was queued or running, and turns one that was asked to pause or cancel into paused or cancelled. A paused job is left alone. This also settles ticket 13's stale "running" rows: on the first start two such voicing jobs from ticket 13 were sent again and finished in under a minute with nothing to voice.
- **Progress** (over the existing SSE stream), for voicing: stage, "part x of y" counted over the whole Work (also after a resume), lines done of total, a percentage by words, and `seconds_left`. Each sentence's words count 0.65 in T3 and 0.35 in S3Gen (`T3_SHARE`, measured below), so the percentage moves during T3 too (ticket 13's gap) and never goes back. Analysis: stage, chunks done of total, percentage, `seconds_left`. Export: percentage of the length written, `seconds_left`. The time left (`Pace`) comes from the speed measured since the first step of this run, so model loading and earlier runs do not count.
- **Interface:** the Work page shows the Work's queued, running or paused job beside its head: kind, state ("Pausing after the current step…" while a request waits), a bar, "Voicing · part 2 of 2 · 12 of 44 lines · 52% · about 9 min left", and Pause, Resume, Cancel. The Library list shows the same line under each Work with a job.

Acceptance, in the container on the GTX 1050 Ti with the desktop on the card, voicing Metamorphosis (Work 16, 44 lines) with its takes forgotten and its seeds kept:

- **Pause frees the card:** paused while S3Gen was saving lines (9 of 44 done): the job was "paused" **6.9 s** after the click, the voicing process was gone, and `nvidia-smi` went from 2,983 MiB to **755 MiB**, the desktop alone. **Resume** continued with the first line without audio (positions 0 to 7 voiced before, 8 and 9 next).
- **Paused across a restart:** `docker compose restart worker` with the job paused: still paused, nothing sent again, the card at 755 MiB.
- **Running across a restart:** restarted with the job running (11 lines done): the worker logged "job 86 (voicing) sent again" and the job ran on from where it was.
- **Cancel and start again:** cancelled with 12 takes saved: the Work went back to "analysed", the 12 takes stayed, the card was freed; **Voice** (`POST /voicing`) started job 90, which voiced exactly the **32** missing lines ("32 lines, 417.5 s of audio"). The chapter re-assembled to **595.525 s**, the same as ticket 14 to the millisecond, so pausing, restarting and cancelling changed no take.
- **Time left:** job 90 showed T3 taking **500 s of 771 s** (65%), not half, and with half-and-half the estimate was 1.5 times too long (677 s at 50% for 459 s). With `T3_SHARE = 0.65`, a clean run of all 44 lines (job 93, 1,151 s, 1.89× real time):

  | Progress | Estimate | Actual time left |
  |---|---|---|
  | 10% | 1,555 s | 987 s |
  | 25% | 914 s | 831 s |
  | 50% | 563 s | 593 s |
  | 75% | 267 s | 307 s |
  | 90% | 113 s | 144 s |

  Within about 20% from a quarter on; high early, while the front matter's slow first sentence (reference clips, warm-up) dominates the measured speed. Analysis and export estimates were not measured on the stack.
- **Unit tests** (`tests/test_job_control.py`): a running job pausing after its step and resuming from there, cancelling, a queued job paused and cancelled at once (its message then ignored), an old message ignored, the API and its refusals, recovery (running and queued sent again, paused and pausing left paused), the time-left arithmetic, voicing stopping within a sentence and resuming at the next line with "part 2 of 3", voicing progress moving during T3 and never going back, a cancelled voicing leaving the Work analysed and queuing no assembly, a paused one leaving it voicing, discard audio (refused while busy, then takes, seeds, files and parts gone), analysis stopping after a chunk and continuing, a cancelled analysis leaving the Work imported, a stopped export leaving the previous one. Frontend: the job panel with its progress line and controls, resume and "Pausing…", Voice and the discard confirmation, the Library's progress line.

Left for later:

- **The job panel was not looked at in a browser** (the browser extension was not connected); its tests render it.
- **Redis restarts:** a job whose message was lost with Redis is sent again only when the worker starts.
