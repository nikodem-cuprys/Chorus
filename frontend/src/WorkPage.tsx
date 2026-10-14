import { useState } from "react";
import { Blocks } from "./Blocks";
import { languageName, t, tMessage, type MessageKey } from "./i18n";
import type { Job } from "./jobs";
import { Lines } from "./Lines";
import { Shell } from "./Shell";
import { authorsText } from "./WorkList";
import { changeLanguage, useChapter, useLanguages, useWork, type Work } from "./works";

function LanguageField({ work, onChanged }: { work: Work; onChanged: () => void }) {
  const languages = useLanguages();
  const codes = languages.map((l) => l.code);
  if (work.language && !codes.includes(work.language)) codes.unshift(work.language);
  const options = codes
    .map((code) => ({ code, name: languageName(code) }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="language">
      <label>
        {t("work.language")}{" "}
        <select
          value={work.language ?? ""}
          onChange={(event) => changeLanguage(work.id, event.target.value).then(onChanged)}
        >
          {work.language === null && <option value="">{t("work.language_unknown")}</option>}
          {options.map((option) => (
            <option key={option.code} value={option.code}>
              {option.name}
            </option>
          ))}
        </select>
      </label>
      {!work.has_language_pack && (
        <p className="notice">
          {t("work.no_language_pack", {
            language: work.language ? languageName(work.language) : t("work.language_unknown"),
          })}
        </p>
      )}
    </div>
  );
}

type View = "text" | "lines";

function Reader({ workId, part }: { workId: number; part: string }) {
  const chapter = useChapter(workId, part);
  const [view, setView] = useState<View>("text");
  if (chapter === null) return <p className="muted">{t("work.loading")}</p>;
  return (
    <section className="reader">
      <div className="view-switch" role="group">
        {(["text", "lines"] as const).map((v) => (
          <button
            key={v}
            type="button"
            aria-pressed={view === v}
            className={view === v ? "selected" : ""}
            onClick={() => setView(v)}
          >
            {t(`work.view.${v}`)}
          </button>
        ))}
      </div>
      {view === "lines" ? (
        <Lines lines={chapter.lines ?? []} />
      ) : (
        <>
          {chapter.notes_before?.length > 0 && <Blocks blocks={chapter.notes_before} />}
          <Blocks blocks={chapter.blocks} />
          {chapter.notes_after?.length > 0 && <Blocks blocks={chapter.notes_after} />}
        </>
      )}
    </section>
  );
}

export function WorkPage({ id, jobs }: { id: number; jobs: Job[] }) {
  const [version, setVersion] = useState(0);
  const work = useWork(id, jobs, version);
  const [part, setPart] = useState<string | null>(null);

  if (work === null) {
    return (
      <Shell>
        <p className="muted">{t("work.loading")}</p>
      </Shell>
    );
  }

  const parts: { key: string; label: string; detail: string }[] = [];
  if (work.front_matter_blocks > 0) {
    parts.push({ key: "front", label: t("work.front_matter"), detail: "" });
  }
  for (const chapter of work.chapters) {
    parts.push({
      key: String(chapter.index),
      label: chapter.title ?? t("work.chapter_number", { index: chapter.index }),
      detail: t("work.words", { count: chapter.words }),
    });
  }
  if (work.back_matter_blocks > 0) {
    parts.push({ key: "back", label: t("work.back_matter"), detail: "" });
  }

  return (
    <Shell>
      <div className="work-head">
        {work.cover_url && <img className="cover" src={work.cover_url} alt={t("work.cover")} />}
        <div>
          <h1>{work.title || t("work.untitled")}</h1>
          <p>{authorsText(work.authors)}</p>
          <p className="muted small">
            {t(`work.state.${work.state}` as MessageKey)} · {work.source.name}
          </p>
          <LanguageField work={work} onChanged={() => setVersion((v) => v + 1)} />
        </div>
      </div>

      {work.error && <p className="error">{tMessage(work.error)}</p>}
      {work.warnings.length > 0 && (
        <>
          <h2>{t("work.warnings")}</h2>
          <ul>
            {work.warnings.map((warning, n) => (
              <li key={n}>{tMessage(warning)}</li>
            ))}
          </ul>
        </>
      )}

      {parts.length > 0 && (
        <>
          <h2>{t("work.chapters")}</h2>
          <div className="chapters">
            <ol className="chapter-list">
              {parts.map((p) => (
                <li key={p.key}>
                  <button
                    type="button"
                    className={p.key === part ? "chapter selected" : "chapter"}
                    onClick={() => setPart(p.key)}
                  >
                    <span>{p.label}</span>
                    <span className="muted small">{p.detail}</span>
                  </button>
                </li>
              ))}
            </ol>
            {part !== null && <Reader key={part} workId={work.id} part={part} />}
          </div>
        </>
      )}
    </Shell>
  );
}
