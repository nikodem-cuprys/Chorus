import { render } from "@testing-library/react";
import { Lines } from "./Lines";
import type { Character, Line } from "./works";

const line = (overrides: Partial<Line>): Line => ({
  position: 0,
  paragraph: 0,
  last_paragraph: 0,
  spans: [{ text: "It began." }],
  kind: "narration",
  passage: "narration",
  voiced: true,
  speaker: null,
  character_id: null,
  emotion: null,
  intensity: null,
  seed: null,
  audio_seconds: null,
  ...overrides,
});

describe("Lines", () => {
  it("shows each line with its kind, and greys out what is not voiced", () => {
    const { container } = render(
      <Lines
        lines={[
          line({ position: 0, paragraph: null, last_paragraph: null, passage: "chapter_title" }),
          line({ position: 1, kind: "quote", spans: [{ text: "“My dear,”" }] }),
          line({ position: 2, spans: [{ text: "said his lady." }] }),
          line({ position: 3, paragraph: 1, last_paragraph: 1, passage: "footnote", voiced: false }),
        ]}
      />,
    );
    const rows = [...container.querySelectorAll("li")];
    expect(rows.map((row) => row.querySelector(".line-tags")?.textContent)).toEqual([
      "narration · chapter title",
      "quotation",
      "narration",
      "narration · footnote · not voiced",
    ]);
    expect(rows[1].className).toContain("line-quote");
    expect(rows[1].className).toContain("line-paragraph");
    expect(rows[2].className).not.toContain("line-paragraph");
    expect(rows[3].className).toContain("line-not-voiced");
  });

  it("shows who says each analysed quotation, and how", () => {
    const characters: Character[] = [
      {
        id: 3,
        name: "Mrs. Bennet",
        aliases: [],
        gender: "female",
        age: "adult",
        lines: 2,
        voice_id: null,
        voice: null,
        voice_auto: false,
      },
    ];
    const { container } = render(
      <Lines
        characters={characters}
        lines={[
          line({ position: 0, speaker: "narrator" }),
          line({
            position: 1,
            kind: "speech",
            speaker: "character",
            character_id: 3,
            emotion: "excited",
            intensity: "strong",
          }),
          line({
            position: 2,
            kind: "thought",
            speaker: "unknown",
            emotion: "sad",
            intensity: "normal",
          }),
          line({ position: 3, kind: "speech", speaker: "narrator" }),
        ]}
      />,
    );
    expect([...container.querySelectorAll(".line-tags")].map((tag) => tag.textContent)).toEqual([
      "narration",
      "speech · Mrs. Bennet · excited, strong",
      "thought · Unknown · sad",
      "speech · Narrator",
    ]);
  });

  it("says when there are no lines", () => {
    const { getByText } = render(<Lines lines={[]} />);
    expect(getByText("No lines yet.")).toBeTruthy();
  });
});
