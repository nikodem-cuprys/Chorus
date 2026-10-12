import { t } from "./i18n";
import { JobList } from "./JobList";
import { useJobs } from "./jobs";

/** The Library, still empty: Works arrive with import (ticket 05). */
export function Library() {
  const { jobs, connected } = useJobs();
  return (
    <div className="page">
      <header className="top">
        <span className="brand">{t("app.name")}</span>
      </header>
      <main>
        <h1>{t("library.title")}</h1>
        <p className="muted">{t("library.empty")}</p>

        <h2>{t("jobs.title")}</h2>
        {!connected && <p className="notice">{t("jobs.connection_lost")}</p>}
        <JobList jobs={jobs} />
      </main>
    </div>
  );
}
