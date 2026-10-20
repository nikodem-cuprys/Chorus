import { useEffect, useState } from "react";
import type { Message } from "./i18n";
import type { Job } from "./jobs";

export type WorkState = "importing" | "imported" | "analysing" | "analysed" | "failed";

export interface WorkSummary {
  id: number;
  title: string;
  authors: string[];
  state: WorkState;
  error: Message | null;
  language: string | null;
  created_at: string | null;
}

export interface Work extends WorkSummary {
  language_source: "metadata" | "detector" | "user" | null;
  has_language_pack: boolean;
  source: { kind: string; name: string; hash: string | null; imported_at: string | null };
  is_ao3: boolean;
  metadata: Record<string, unknown>;
  warnings: Message[];
  cover_url: string | null;
  front_matter_blocks: number;
  back_matter_blocks: number;
  chapters: {
    index: number;
    title: string | null;
    words: number;
    /** The Character telling a first-person chapter. */
    narrating_character_id: number | null;
  }[];
  /** Most lines first. */
  characters: Character[];
  /** The Narrator's Voice, by its id ("af_bella"); null before casting. */
  narrator_voice: string | null;
}

export type Age = "child" | "young_adult" | "adult" | "elderly" | "unknown";

export interface Character {
  id: number;
  name: string;
  aliases: string[];
  gender: "female" | "male" | "unknown";
  age: Age;
  lines: number;
  voice_id: number | null;
  /** The Voice's id ("am_michael"); null before casting. */
  voice: string | null;
  /** Auto-cast, rather than chosen by the user. */
  voice_auto: boolean;
}

export type Emotion =
  "neutral" | "happy" | "excited" | "amused" | "angry" | "sad" | "afraid" | "anxious" | "surprised";

export type Mark = "italic" | "bold" | "underline" | "strike" | "small_caps" | "superscript";

export interface Span {
  text: string;
  marks?: Mark[];
}

export interface Block {
  type:
    | "paragraph"
    | "heading"
    | "section_break"
    | "quote"
    | "letter"
    | "list_item"
    | "footnote"
    | "epigraph"
    | "verse";
  spans: Span[];
  level?: number;
  /** Added by the Source's publisher (Project Gutenberg's header and licence); never voiced. */
  boilerplate?: boolean;
}

export type Passage =
  | "narration"
  | "chapter_title"
  | "work_title"
  | "epigraph"
  | "letter"
  | "verse"
  | "footnote"
  | "list"
  | "ao3_note"
  | "never_voiced";

/** One line of the Script. */
export interface Line {
  position: number;
  /** The block it starts in; null for a line Chorus made, such as the Work title. */
  paragraph: number | null;
  last_paragraph: number | null;
  spans: Span[];
  kind: "narration" | "quote" | "speech" | "thought" | "written";
  passage: Passage;
  voiced: boolean;
  /** From analysis; null before it, and for lines that are not voiced. */
  speaker: "narrator" | "character" | "unknown" | null;
  character_id: number | null;
  emotion: Emotion | null;
  intensity: "normal" | "strong" | null;
}

export interface Chapter {
  index: number;
  title: string | null;
  notes_before: Block[];
  blocks: Block[];
  notes_after: Block[];
  lines: Line[];
}

/** A signature of the jobs' states, so a list can reload when any job moves on. */
function jobsKey(jobs: Job[], workId?: number): string {
  return jobs
    .filter((job) => workId === undefined || job.work_id === workId)
    .map((job) => `${job.id}:${job.state}`)
    .join(",");
}

function useJson<T>(url: string | null, reloadKey: string): T | null {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    if (url === null) return;
    let cancelled = false;
    fetch(url)
      .then((response) => (response.ok ? (response.json() as Promise<T>) : null))
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [url, reloadKey]);
  return data;
}

/** The Library's Works, reloaded whenever a job changes state. */
export function useWorks(jobs: Job[]): WorkSummary[] | null {
  return useJson<WorkSummary[]>("/api/works", jobsKey(jobs));
}

/** One Work, reloaded when one of its jobs changes state or `version` changes. */
export function useWork(id: number, jobs: Job[], version: number): Work | null {
  return useJson<Work>(`/api/works/${id}`, `${jobsKey(jobs, id)}|${version}`);
}

export function useChapter(workId: number, part: string | null): Chapter | null {
  const url =
    part === null
      ? null
      : part === "front" || part === "back"
        ? `/api/works/${workId}/matter/${part}`
        : `/api/works/${workId}/chapters/${part}`;
  return useJson<Chapter>(url, "");
}

export interface Language {
  code: string;
  has_pack: boolean;
}

export function useLanguages(): Language[] {
  return useJson<Language[]>("/api/languages", "") ?? [];
}

export async function uploadWork(file: File): Promise<WorkSummary> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/works", { method: "POST", body });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as { detail?: Message } | null;
    throw detail?.detail ?? { key: "import.error.upload_failed" };
  }
  return (await response.json()) as WorkSummary;
}

export async function startAnalysis(id: number): Promise<void> {
  await fetch(`/api/works/${id}/analysis`, { method: "POST" });
}

export async function changeLanguage(id: number, language: string): Promise<void> {
  await fetch(`/api/works/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
}
