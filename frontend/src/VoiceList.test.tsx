import { render, screen } from "@testing-library/react";
import { VoiceList, voiceLabels } from "./VoiceList";
import type { Voice } from "./voices";

const voice = (overrides: Partial<Voice>): Voice => ({
  id: 1,
  name: "am_fenrir",
  language: "en",
  gender: "male",
  age: "young_adult",
  accent: "american",
  timbre: ["high"],
  narrator_ok: true,
  built_in: true,
  default_narrator: false,
  credit: "Kokoro-82M voice am_fenrir (Apache-2.0)",
  clip_url: "/api/voices/1/clip",
  ...overrides,
});

describe("VoiceList", () => {
  it("shows a Voice's labels from the catalogue", () => {
    expect(voiceLabels(voice({}))).toBe("Male · young adult · American · high");
  });

  it("marks the default Narrator", () => {
    render(
      <VoiceList
        voices={[
          voice({ id: 1, name: "af_bella", default_narrator: true }),
          voice({ id: 2, name: "bm_lewis", narrator_ok: false }),
        ]}
      />,
    );
    expect(screen.getByText("af_bella")).toBeTruthy();
    expect(screen.getByText("Default Narrator")).toBeTruthy();
    expect(screen.queryByText("Suits the Narrator")).toBeNull();
  });
});
