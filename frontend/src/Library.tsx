import { t } from "./i18n";
import { JobList } from "./JobList";
import type { Job } from "./jobs";
import { Link } from "./router";
import { Shell } from "./Shell";
import { VoiceList } from "./VoiceList";
import { useVoices } from "./voices";
import { WorkList } from "./WorkList";
import { useWorks } from "./works";

export function Library({ jobs, connected }: { jobs: Job[]; connected: boolean }) {
  const works = useWorks(jobs);
  const voices = useVoices();
  return (
    <Shell>
      <div className="title-row">
        <h1>{t("library.title")}</h1>
        <Link to="/import" className="button">
          {t("nav.import")}
        </Link>
      </div>
      {works && <WorkList works={works} jobs={jobs} />}

      <h2>{t("jobs.title")}</h2>
      {!connected && <p className="notice">{t("jobs.connection_lost")}</p>}
      <JobList jobs={jobs} />

      <h2>{t("voices.title")}</h2>
      <VoiceList voices={voices} />
    </Shell>
  );
}
