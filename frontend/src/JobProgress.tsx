import { t, tMessage, type MessageKey } from "./i18n";
import type { Job } from "./jobs";

export const ACTIVE_STATES = ["queued", "running", "paused"] as const;

/** The Work's job still to finish (queued, running or paused), newest first. */
export function activeJob(jobs: Job[], workId: number): Job | null {
  return (
    jobs.find(
      (job) =>
        job.work_id === workId && (ACTIVE_STATES as readonly string[]).includes(job.state),
    ) ?? null
  );
}

/** "about 1 h 20 min left", "about 4 min left", "less than a minute left". */
export function timeLeftText(seconds: number): string {
  if (seconds < 60) return t("job.left.under_minute");
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return t("job.left.minutes", { minutes });
  return t("job.left.hours", { hours: Math.floor(minutes / 60), minutes: minutes % 60 });
}

/** What the job is doing, in one line: stage, chapter x of y, lines done of total, time left. */
export function progressText(job: Job): string {
  const p = job.progress;
  const pieces: string[] = [];
  if (typeof p.stage === "string") {
    pieces.push(tMessage({ key: `job.stage.${p.stage}` }));
  }
  if (job.kind === "voicing" && typeof p.part === "number" && typeof p.parts === "number") {
    pieces.push(t("job.part_of", { part: p.part, parts: p.parts }));
  }
  if (typeof p.done === "number" && typeof p.total === "number") {
    const key = job.kind === "voicing" ? "job.lines_of" : "job.steps_of";
    pieces.push(t(key, { done: p.done, total: p.total }));
  }
  pieces.push(t("jobs.progress", { percent: p.percent ?? 0 }));
  if (job.state === "running" && typeof p.seconds_left === "number") {
    pieces.push(timeLeftText(p.seconds_left));
  }
  return pieces.join(" · ");
}

/** The job's state, with "pausing…" or "cancelling…" while a request waits for the next step. */
export function stateText(job: Job): string {
  if (job.state === "running" && job.request) return t(`job.request.${job.request}`);
  return t(`job.state.${job.state}` as MessageKey);
}
