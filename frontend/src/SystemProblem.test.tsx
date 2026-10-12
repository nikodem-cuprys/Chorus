import { render, screen } from "@testing-library/react";
import { SystemProblem, type Health } from "./SystemProblem";

const health: Health = {
  checked_at: "2026-10-12T00:00:00",
  ok: false,
  checks: [
    {
      name: "torch",
      ok: false,
      message: { key: "health.torch.no_kernel", params: { version: "2.14.0+cu128" } },
      detail: "CUDA error: no kernel image is available for execution on the device",
    },
    {
      name: "ffmpeg",
      ok: true,
      message: { key: "health.program.ok", params: { program: "ffmpeg" } },
      detail: "ffmpeg version 6.1.1",
    },
  ],
};

describe("SystemProblem", () => {
  it("lists only the failed checks, in words from the catalogue", () => {
    render(<SystemProblem health={health} />);
    expect(screen.getByText(/PyTorch 2\.14\.0\+cu128 has no code for this graphics card/)).toBeTruthy();
    expect(screen.queryByText("ffmpeg works.")).toBeNull();
    expect(screen.getByText(/no kernel image is available for execution/)).toBeTruthy();
  });
});
