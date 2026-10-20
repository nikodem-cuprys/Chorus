import { useEffect, useState } from "react";
import { locale, t, tMessage, type Message, type MessageKey } from "./i18n";

export interface ModelProgress {
  id: string;
  size: number;
  done: number;
  state: "waiting" | "downloading" | "verifying" | "done";
}

export interface Models {
  ready: boolean;
  models: ModelProgress[];
  error: Message | null;
}

/** The First run's downloads, from /api/system/models and then the `models` events. */
export function useModels(): Models | null {
  const [models, setModels] = useState<Models | null>(null);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    // Listening starts before the first load, so no update falls between the two.
    const source = new EventSource("/api/events");
    const show = (result: Models) => {
      if (stopped) return;
      setModels(result);
      if (result.ready) source.close();
    };
    source.addEventListener("models", (event) => {
      show(JSON.parse((event as MessageEvent<string>).data) as Models);
    });
    const load = () => {
      fetch("/api/system/models")
        .then((response) => response.json() as Promise<Models>)
        .then(show)
        .catch(() => {
          if (!stopped) timer = setTimeout(load, 3000);
        });
    };
    load();
    return () => {
      stopped = true;
      clearTimeout(timer);
      source.close();
    };
  }, []);
  return models;
}

function gigabytes(bytes: number): string {
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "gigabyte",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(bytes / 1e9);
}

/** Shown instead of the app until both models are downloaded. */
export function FirstRun({ models }: { models: Models }) {
  return (
    <div className="page">
      <header className="top">
        <span className="brand">{t("app.name")}</span>
      </header>
      <main>
        <h1>{t("first_run.title")}</h1>
        <p>{t("first_run.intro")}</p>
        {models.error && <p className="error">{tMessage(models.error)}</p>}
        <ul className="jobs">
          {models.models.map((model) => {
            const percent = model.size ? Math.floor((100 * model.done) / model.size) : 0;
            return (
              <li key={model.id} className="job">
                <div className="job-head">
                  <span>{t(`first_run.model.${model.id}` as MessageKey)}</span>
                  <span className="muted">{t(`first_run.state.${model.state}` as MessageKey)}</span>
                </div>
                <div
                  className="bar"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent}
                >
                  <div className="bar-fill" style={{ width: `${percent}%` }} />
                </div>
                <div className="muted small">
                  {t("first_run.progress", {
                    done: gigabytes(model.done),
                    size: gigabytes(model.size),
                    percent,
                  })}
                </div>
              </li>
            );
          })}
        </ul>
        <p className="muted">{t("first_run.after")}</p>
      </main>
    </div>
  );
}
