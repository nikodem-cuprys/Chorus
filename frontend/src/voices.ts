import { useEffect, useState } from "react";

export interface Voice {
  id: number;
  name: string;
  language: string;
  gender: "female" | "male" | "neutral";
  age: "child" | "young_adult" | "adult" | "elderly";
  accent: string;
  timbre: string[];
  narrator_ok: boolean;
  built_in: boolean;
  default_narrator: boolean;
  credit: string | null;
  clip_url: string;
}

/** Every Voice; the built-in ones come from the Language packs. */
export function useVoices(): Voice[] {
  const [voices, setVoices] = useState<Voice[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/voices")
      .then((response) => response.json() as Promise<Voice[]>)
      .then((list) => {
        if (!cancelled) setVoices(list);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return voices;
}
