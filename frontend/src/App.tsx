import { Import } from "./Import";
import { useJobs } from "./jobs";
import { Library } from "./Library";
import { usePath } from "./router";
import { SystemProblem, useHealth } from "./SystemProblem";
import { WorkPage } from "./WorkPage";

export function App() {
  const health = useHealth();
  const path = usePath();
  const { jobs, connected } = useJobs();
  if (health?.ok === false) {
    return <SystemProblem health={health} />;
  }
  if (path === "/import") {
    return <Import />;
  }
  const work = /^\/works\/(\d+)\/?$/.exec(path);
  if (work) {
    return <WorkPage key={work[1]} id={Number(work[1])} jobs={jobs} />;
  }
  return <Library jobs={jobs} connected={connected} />;
}
