import { render, screen } from "@testing-library/react";
import type { Job } from "./jobs";
import { WorkList } from "./WorkList";

const job: Job = {
  id: 4,
  work_id: 12,
  kind: "analysis",
  queue: "gpu",
  state: "running",
  progress: { stage: "characters", done: 30, total: 167, percent: 6, seconds_left: 1500 },
  error: null,
  request: null,
  created_at: null,
  started_at: null,
  finished_at: null,
};

describe("WorkList", () => {
  it("shows the progress of each Work's running job", () => {
    render(
      <WorkList
        works={[
          {
            id: 12,
            title: "Pride and Prejudice",
            authors: ["Jane Austen"],
            state: "analysing",
            error: null,
            language: "en",
            created_at: null,
          },
        ]}
        jobs={[job, { ...job, id: 5, work_id: 99 }]}
      />,
    );
    expect(
      screen.getByText("Running · Finding the Characters · 30 of 167 · 6% · about 25 min left"),
    ).toBeTruthy();
  });
});
