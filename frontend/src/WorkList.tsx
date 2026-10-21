import { t, tMessage, type MessageKey } from "./i18n";
import { activeJob, progressText, stateText } from "./JobProgress";
import type { Job } from "./jobs";
import { Link } from "./router";
import type { WorkSummary } from "./works";

function WorkJob({ job }: { job: Job | null }) {
  if (job === null) return null;
  return (
    <span className="muted small">
      {stateText(job)} · {progressText(job)}
    </span>
  );
}

export function authorsText(authors: string[]): string {
  return authors.length ? authors.join(", ") : t("work.no_author");
}

/** Milestone 1's Library: a plain list with title, author, state and the running job's progress. */
export function WorkList({ works, jobs = [] }: { works: WorkSummary[]; jobs?: Job[] }) {
  if (works.length === 0) {
    return <p className="muted">{t("library.empty")}</p>;
  }
  return (
    <ul className="works">
      {works.map((work) => (
        <li key={work.id} className={`work work-${work.state}`}>
          <Link to={`/works/${work.id}`} className="work-title">
            {work.title || t("work.untitled")}
          </Link>
          <span className="muted">{authorsText(work.authors)}</span>
          <span className="muted small">{t(`work.state.${work.state}` as MessageKey)}</span>
          <WorkJob job={activeJob(jobs, work.id)} />
          {work.error && <span className="error small">{tMessage(work.error)}</span>}
        </li>
      ))}
    </ul>
  );
}
