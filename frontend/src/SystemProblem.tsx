import { useEffect, useState } from "react";
import { t, tMessage, type Message } from "./i18n";

export interface Check {
  name: string;
  ok: boolean;
  message: Message;
  detail: string;
}

export interface Health {
  checked_at: string | null;
  ok: boolean | null;
  checks: Check[];
}

/** The worker's startup check; `ok` stays null until the worker has run it. */
export function useHealth(): Health | null {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = () => {
      fetch("/api/system/health")
        .then((response) => response.json() as Promise<Health>)
        .then((result) => {
          if (stopped) return;
          setHealth(result);
          if (result.ok === null) timer = setTimeout(poll, 3000);
        })
        .catch(() => {
          if (!stopped) timer = setTimeout(poll, 3000);
        });
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);
  return health;
}

/** Shown instead of the app when the startup check failed. */
export function SystemProblem({ health }: { health: Health }) {
  const failed = health.checks.filter((check) => !check.ok);
  return (
    <div className="page">
      <header className="top">
        <span className="brand">{t("app.name")}</span>
      </header>
      <main>
        <h1>{t("health.title")}</h1>
        <p>{t("health.intro")}</p>
        <ul className="checks">
          {failed.map((check) => (
            <li key={check.name} className="check-failed">
              <div>{tMessage(check.message)}</div>
              {check.detail && (
                <details>
                  <summary>{t("health.details")}</summary>
                  <pre>{check.detail}</pre>
                </details>
              )}
            </li>
          ))}
        </ul>
        <p className="muted">{t("health.after_fixing")}</p>
      </main>
    </div>
  );
}
