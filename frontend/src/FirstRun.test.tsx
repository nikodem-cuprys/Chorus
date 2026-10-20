import { render, screen } from "@testing-library/react";
import { FirstRun, type Models } from "./FirstRun";

const models: Models = {
  ready: false,
  models: [
    { id: "qwen", size: 2_740_937_888, done: 1_370_468_944, state: "downloading" },
    { id: "chatterbox", size: 3_191_966_992, done: 0, state: "waiting" },
  ],
  error: { key: "first_run.error.download", params: { detail: "timed out" } },
};

describe("FirstRun", () => {
  it("shows each model with its size and progress, in words from the catalogue", () => {
    render(<FirstRun models={models} />);
    expect(screen.getByText(/Qwen3\.5-4B, which reads the Work/)).toBeTruthy();
    expect(screen.getByText(/Chatterbox, which speaks the lines/)).toBeTruthy();
    expect(screen.getByText(/1\.37 GB of 2\.74 GB \(50%\)/)).toBeTruthy();
    expect(screen.getByText(/0\.00 GB of 3\.19 GB \(0%\)/)).toBeTruthy();
    const bars = screen.getAllByRole("progressbar");
    expect(bars.map((bar) => bar.getAttribute("aria-valuenow"))).toEqual(["50", "0"]);
    expect(screen.getByText(/The download stopped: timed out\./)).toBeTruthy();
  });
});
