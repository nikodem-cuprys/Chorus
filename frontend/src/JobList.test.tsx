import { render, screen } from "@testing-library/react";
import { tMessage } from "./i18n";
import { JobList } from "./JobList";
import type { Job } from "./jobs";

const job = (overrides: Partial<Job>): Job => ({
  id: 1,
  work_id: null,
  kind: "dev.gpu",
  queue: "gpu",
  state: "running",
  progress: { percent: 40, done: 2, total: 5 },
  error: null,
  request: null,
  created_at: null,
  started_at: null,
  finished_at: null,
  ...overrides,
});

describe("JobList", () => {
  it("shows a job's kind, state and progress from the catalogue", () => {
    render(<JobList jobs={[job({})]} />);
    expect(screen.getByText("Test job (GPU queue)")).toBeTruthy();
    expect(screen.getByText("Running")).toBeTruthy();
    expect(screen.getByText("40%")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("40");
  });

  it("shows a failed job's error message with its parameters", () => {
    const error = { key: "job.error.unexpected", params: { detail: "boom" } };
    render(<JobList jobs={[job({ state: "failed", error })]} />);
    expect(screen.getByText("Something went wrong: boom")).toBeTruthy();
  });

  it("says so when there are no jobs", () => {
    render(<JobList jobs={[]} />);
    expect(screen.getByText("No jobs have run.")).toBeTruthy();
  });
});

describe("tMessage", () => {
  it("shows an unknown key as itself", () => {
    expect(tMessage({ key: "no.such.key" })).toBe("no.such.key");
  });
});
