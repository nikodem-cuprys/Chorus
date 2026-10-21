import { fireEvent, render, screen } from "@testing-library/react";
import type { Job } from "./jobs";
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
  exports: [],
  voiced_lines: 0,
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

  it("lists exports and offers new ones once the Work is ready", async () => {
    serve(
      work({
        state: "ready",
        exports: [
          {
            id: 3,
            kind: "mp3",
            folder: "The Morning After (7)",
            files: ["01 - Front matter.mp3", "02 - Chapter 1.mp3"],
            seconds: 125,
            created_at: "2026-10-21T13:30:00+00:00",
            download_url: "/api/exports/3/download",
          },
        ],
      }),
    );
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText("MP3")).toBeTruthy();
    expect(screen.getByText("2:05 · 2 files · in the exports folder, The Morning After (7)", { exact: false })).toBeTruthy();
    expect(screen.getByText("Download").getAttribute("href")).toBe("/api/exports/3/download");
    expect((screen.getByText("Export M4B") as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText("Delete")).toBeTruthy();
  });

  it("offers no export until every chapter is ready", async () => {
    serve(work({ state: "voicing" }));
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText("Export MP3")).toBeTruthy();
    expect((screen.getByText("Export MP3") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/can be exported once every chapter is ready/)).toBeTruthy();
    expect(screen.getByText("No exports yet.")).toBeTruthy();
  });

  it("shows the running job with its progress, time left and controls", async () => {
    serve(work({ state: "voicing" }));
    const voicing: Job = {
      id: 31,
      work_id: 7,
      kind: "voicing",
      queue: "gpu",
      state: "running",
      progress: {
        stage: "voicing", part: 2, parts: 5, done: 120, total: 541, percent: 23,
        seconds_left: 4980,
      },
      error: null,
      request: null,
      created_at: null,
      started_at: null,
      finished_at: null,
    };
    render(<WorkPage id={7} jobs={[voicing]} />);
    expect(
      await screen.findByText("Voicing · part 2 of 5 · 120 of 541 lines · 23% · about 1 h 23 min left"),
    ).toBeTruthy();
    expect(screen.getByText("Pause")).toBeTruthy();
    expect(screen.getByText("Cancel")).toBeTruthy();
    expect(screen.queryByText("Resume")).toBeNull();
  });

  it("offers resume for a paused job and says when a pause is waiting", async () => {
    serve(work({ state: "voicing" }));
    const base: Job = {
      id: 31, work_id: 7, kind: "voicing", queue: "gpu", state: "paused",
      progress: { percent: 23 }, error: null, request: null,
      created_at: null, started_at: null, finished_at: null,
    };
    const { rerender } = render(<WorkPage id={7} jobs={[base]} />);
    expect(await screen.findByText("Resume")).toBeTruthy();
    expect(screen.getByText("Paused")).toBeTruthy();
    rerender(<WorkPage id={7} jobs={[{ ...base, state: "running", request: "pause" }]} />);
    expect(await screen.findByText("Pausing after the current step…")).toBeTruthy();
    expect((screen.getByText("Pause") as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers to voice an analysed Work and to discard its audio, with a confirmation", async () => {
    serve(work({ state: "analysed", voiced_lines: 214 }));
    render(<WorkPage id={7} jobs={[]} />);
    expect(await screen.findByText("Voice")).toBeTruthy();
    fireEvent.click(screen.getByText("Discard audio…"));
    expect(screen.getByText(/deletes the audio of all 214 voiced lines/)).toBeTruthy();
    fireEvent.click(screen.getByText("Keep it"));
    expect(screen.queryByText(/deletes the audio/)).toBeNull();
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
