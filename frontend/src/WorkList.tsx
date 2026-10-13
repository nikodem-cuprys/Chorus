import { t, tMessage, type MessageKey } from "./i18n";
import { Link } from "./router";
import type { WorkSummary } from "./works";

export function authorsText(authors: string[]): string {
  return authors.length ? authors.join(", ") : t("work.no_author");
}

/** Milestone 1's Library: a plain list with title, author and state. */
export function WorkList({ works }: { works: WorkSummary[] }) {
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
          {work.error && <span className="error small">{tMessage(work.error)}</span>}
        </li>
      ))}
    </ul>
  );
}
