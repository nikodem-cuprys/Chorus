import { useState } from "react";
import { Blocks } from "./Blocks";
import { languageName, t, tMessage, type MessageKey } from "./i18n";
import type { Job } from "./jobs";
import { Lines } from "./Lines";
import { Shell } from "./Shell";
import { authorsText } from "./WorkList";
import {
  changeLanguage,
  startAnalysis,
  useChapter,
  useLanguages,
  useWork,
  type Character,
  type Work,
} from "./works";

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

function Characters({ work }: { work: Work }) {
  if (work.characters.length === 0) return <p className="muted">{t("work.no_characters")}</p>;
  return (
    <ul className="characters">
      {work.narrator_voice && (
        <li>
          <strong>{t("line.speaker.narrator")}</strong>{" "}
          <span className="muted small">{t("work.voice", { voice: work.narrator_voice })}</span>
        </li>
      )}
      {work.characters.map((c) => {
        const narrated = work.chapters
          .filter((chapter) => chapter.narrating_character_id === c.id)
          .map((chapter) => chapter.index);
        return (
          <li key={c.id}>
            <strong>{c.name}</strong>{" "}
            <span className="muted small">
              {t(`character.gender.${c.gender}`)}, {t(`character.age.${c.age}`)} ·{" "}
              {t("work.character_lines", { count: c.lines })}
              {c.aliases.length > 0 &&
                ` · ${t("work.character_aliases", { aliases: c.aliases.join(", ") })}`}
              {narrated.length > 0 && ` · ${t("work.narrates", { chapters: narrated.join(", ") })}`}
              {c.voice &&
                ` · ${t(c.voice_auto ? "work.voice_auto" : "work.voice", { voice: c.voice })}`}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function Reader({
  workId,
  part,
  characters,
}: {
  workId: number;
  part: string;
  characters: Character[];
}) {
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
        <Lines lines={chapter.lines ?? []} characters={characters} />
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
          {(work.state === "analysed" || (work.state === "failed" && work.chapters.length > 0)) && (
            <button
              type="button"
              onClick={() => startAnalysis(work.id).then(() => setVersion((v) => v + 1))}
            >
              {t("work.analyse")}
            </button>
          )}
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
          <h2>{t("work.characters")}</h2>
          <Characters work={work} />
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
            {part !== null && (
              <Reader key={part} workId={work.id} part={part} characters={work.characters} />
            )}
          </div>
        </>
      )}
    </Shell>
  );
}
