import { useEffect, useState } from "react";
import type { Message } from "./i18n";

export type JobState = "queued" | "running" | "paused" | "cancelled" | "failed" | "done";

export interface Job {
  id: number;
  work_id: number | null;
  kind: string;
  queue: "gpu" | "other";
  state: JobState;
  progress: { percent?: number; done?: number; total?: number; [name: string]: unknown };
  error: Message | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

/** The latest jobs, kept up to date from the server-sent events stream. */
export function useJobs(): { jobs: Job[]; connected: boolean } {
  const [jobs, setJobs] = useState<Map<number, Job>>(new Map());
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/jobs")
      .then((response) => response.json() as Promise<Job[]>)
      .then((list) => {
        if (cancelled) return;
        // Events that arrived while loading are newer than the list; keep them.
        setJobs((current) => new Map([...list.map((j) => [j.id, j] as const), ...current]));
      })
      .catch(() => undefined);

    const source = new EventSource("/api/events");
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("job", (event) => {
      const job = JSON.parse((event as MessageEvent<string>).data) as Job;
      setJobs((current) => new Map(current).set(job.id, job));
    });
    return () => {
      cancelled = true;
      source.close();
    };
  }, []);

  return { jobs: [...jobs.values()].sort((a, b) => b.id - a.id), connected };
}
