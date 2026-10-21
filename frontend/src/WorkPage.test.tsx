import { render, screen } from "@testing-library/react";
import { WorkPage } from "./WorkPage";
import type { Work } from "./works";

const work = (overrides: Partial<Work>): Work => ({
  id: 7,
  title: "The Morning After",
  authors: ["test_author"],
  state: "imported",
  error: null,
  language: "en",
  created_at: null,
  language_source: "metadata",
  has_language_pack: true,
  source: { kind: "epub", name: "ao3.epub", hash: null, imported_at: null },
  is_ao3: true,
  metadata: {},
  warnings: [],
  cover_url: null,
  front_matter_blocks: 3,
  back_matter_blocks: 0,
  front_matter_audio_seconds: null,
  back_matter_audio_seconds: null,
  chapters: [
    {
      index: 1,
      title: "Chapter 1: Transformed",
      words: 500,
      narrating_character_id: null,
      audio_seconds: null,
    },
    {
      index: 2,
      title: "Chapter 2: The Door",
      words: 1100,
      narrating_character_id: 4,
      audio_seconds: null,
    },
  ],
  characters: [],
  narrator_voice: null,
  ...overrides,
});

function serve(data: Work) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            url === "/api/languages"
              ? [
                  { code: "en", has_pack: true },
                  { code: "pl", has_pack: false },
                ]
              : data,
          ),
      }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("WorkPage", () => {
  it("shows the chapters and no notice for a language with a pack", async () => {
    serve(work({}));
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText("Chapter 2: The Door")).toBeTruthy();
    expect(screen.getByText("Front matter")).toBeTruthy();
    expect(screen.getByText("1100 words")).toBeTruthy();
    expect(screen.queryByText(/no Language pack/)).toBeNull();
  });

  it("lists the Characters found by analysis", async () => {
    serve(
      work({
        state: "analysed",
        narrator_voice: "af_bella",
        characters: [
          {
            id: 4,
            name: "Watson",
            aliases: ["Dr. Watson"],
            gender: "male",
            age: "adult",
            lines: 14,
            voice_id: 8,
            voice: "am_eric",
            voice_auto: true,
          },
          {
            id: 5,
            name: "Irene",
            aliases: [],
            gender: "female",
            age: "unknown",
            lines: 1,
            voice_id: null,
            voice: null,
            voice_auto: false,
          },
        ],
      }),
    );
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText("Watson")).toBeTruthy();
    expect(
      screen.getByText(
        "male, adult · 14 lines · also called Dr. Watson · narrates chapter 2 · Voice am_eric (auto-cast)",
      ),
    ).toBeTruthy();
    expect(screen.getByText("female, age unknown · 1 lines")).toBeTruthy();
    expect(screen.getByText("Voice af_bella")).toBeTruthy(); // the Narrator's
    expect(screen.getByText("Analyse again")).toBeTruthy();
  });

  it("plays each ready part and shows the others as not ready", async () => {
    const base = work({});
    serve(
      work({
        state: "voicing",
        front_matter_blocks: 0,
        front_matter_audio_seconds: 4.2,
        chapters: [{ ...base.chapters[0], audio_seconds: 754.4 }, base.chapters[1]],
      }),
    );
    render(<WorkPage id={7} jobs={[]} />);
    const player = await screen.findByLabelText("Play Chapter 1: Transformed");
    expect(player.getAttribute("src")).toBe("/api/works/7/audio/1");
    expect(screen.getByText("500 words · 12:34")).toBeTruthy();
    // The front matter holds only the Work title, and plays.
    expect(screen.getByLabelText("Play Front matter").getAttribute("src")).toBe(
      "/api/works/7/audio/front",
    );
    expect(screen.getByText("0:04")).toBeTruthy();
    expect(screen.getAllByText("Not ready yet")).toHaveLength(1); // chapter 2
  });

  it("says when a Work is ready to listen", async () => {
    serve(work({ state: "ready" }));
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText(/Ready to listen/)).toBeTruthy();
  });

  it("offers no player before voicing", async () => {
    serve(work({ state: "analysed" }));
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText("Chapter 2: The Door")).toBeTruthy();
    expect(screen.queryByText("Not ready yet")).toBeNull();
  });

  it("says the English pack is used for a language without one", async () => {
    serve(work({ language: "pl", language_source: "user", has_language_pack: false }));
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText(/Chorus has no Language pack for Polish/)).toBeTruthy();
  });

  it("shows why an import failed", async () => {
    serve(
      work({
        state: "failed",
        error: { key: "import.error.drm", params: {} },
        chapters: [],
        front_matter_blocks: 0,
      }),
    );
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText(/protected with DRM/)).toBeTruthy();
  });
});
