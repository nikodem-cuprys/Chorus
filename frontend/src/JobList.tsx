import { t, tMessage, type MessageKey } from "./i18n";
import type { Job } from "./jobs";

function kindLabel(kind: string): string {
  return tMessage({ key: `job.kind.${kind}` });
}

export function JobList({ jobs }: { jobs: Job[] }) {
  if (jobs.length === 0) {
    return <p className="muted">{t("jobs.empty")}</p>;
  }
  return (
    <ul className="jobs">
      {jobs.map((job) => {
        const percent = job.progress.percent ?? (job.state === "done" ? 100 : 0);
        return (
          <li key={job.id} className={`job job-${job.state}`}>
            <div className="job-head">
              <span>{kindLabel(job.kind)}</span>
              <span className="muted">{t(`job.state.${job.state}` as MessageKey)}</span>
            </div>
            <div
              className="bar"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent}
            >
              <div className="bar-fill" style={{ width: `${percent}%` }} />
            </div>
            <div className="muted small">{t("jobs.progress", { percent })}</div>
            {job.error && <div className="error">{tMessage(job.error)}</div>}
          </li>
        );
      })}
    </ul>
  );
}
