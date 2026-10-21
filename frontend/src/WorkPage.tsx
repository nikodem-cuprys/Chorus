import { useState } from "react";
import { Blocks } from "./Blocks";
import { languageName, locale, t, tMessage, type Message, type MessageKey } from "./i18n";
import type { Job } from "./jobs";
import { Lines } from "./Lines";
import { Shell } from "./Shell";
import { authorsText } from "./WorkList";
import {
  changeLanguage,
  deleteExport,
  partAudioUrl,
  startExport,
  startAnalysis,
  useChapter,
  useLanguages,
  useWork,
  type Character,
  type ExportKind,
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

function dateText(iso: string | null): string {
  if (iso === null) return "";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );
}

/** Buttons to export the Work, and its exports with their dates, downloads and delete. */
function Exports({ work, onChanged }: { work: Work; onChanged: () => void }) {
  const [error, setError] = useState<Message | null>(null);
  const ready = work.state === "ready";
  const start = (kind: ExportKind) => {
    setError(null);
    startExport(work.id, kind).then(onChanged, (message: Message) => setError(message));
  };
  return (
    <>
      <h2>{t("work.exports")}</h2>
      <div className="export-buttons">
        {(["m4b", "mp3"] as const).map((kind) => (
          <button key={kind} type="button" disabled={!ready} onClick={() => start(kind)}>
            {t(`work.export.${kind}`)}
          </button>
        ))}
      </div>
      {!ready && <p className="muted small">{t("work.export_not_ready")}</p>}
      {error && <p className="error">{tMessage(error)}</p>}
      {work.exports.length === 0 ? (
        <p className="muted">{t("work.no_exports")}</p>
      ) : (
        <ul className="exports">
          {work.exports.map((e) => (
            <li key={e.id}>
              <strong>{t(`export.kind.${e.kind}`)}</strong>{" "}
              <span className="muted small">
                {dateText(e.created_at)} · {lengthText(e.seconds)}
                {e.kind === "mp3" && ` · ${t("export.files", { count: e.files.length })}`} ·{" "}
                {t("export.where", { folder: e.folder })}
              </span>{" "}
              <a href={e.download_url} download>
                {t("export.download")}
              </a>{" "}
              <button type="button" onClick={() => deleteExport(e.id).then(onChanged)}>
                {t("export.delete")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function lengthText(seconds: number): string {
  const whole = Math.round(seconds);
  return t("work.length", {
    minutes: Math.floor(whole / 60),
    seconds: String(whole % 60).padStart(2, "0"),
  });
}

/** A part's plain player, or a note that it is not ready to play yet. */
function PartAudio({
  workId,
  part,
  label,
  seconds,
}: {
  workId: number;
  part: string;
  label: string;
  seconds: number | null;
}) {
  if (seconds === null) return <span className="muted small">{t("work.not_ready")}</span>;
  return (
    <audio
      className="part-audio"
      controls
      preload="none"
      src={partAudioUrl(workId, part)}
      aria-label={t("work.play", { part: label })}
    />
  );
}

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

  const parts: { key: string; label: string; detail: string; seconds: number | null }[] = [];
  const withLength = (detail: string, seconds: number | null) =>
    seconds === null ? detail : [detail, lengthText(seconds)].filter(Boolean).join(" · ");
  // The front matter holds the Work title and author, so it plays even with no blocks.
  if (work.front_matter_blocks > 0 || work.front_matter_audio_seconds !== null) {
    const seconds = work.front_matter_audio_seconds;
    const label = t("work.front_matter");
    parts.push({ key: "front", label, detail: withLength("", seconds), seconds });
  }
  for (const chapter of work.chapters) {
    parts.push({
      key: String(chapter.index),
      label: chapter.title ?? t("work.chapter_number", { index: chapter.index }),
      detail: withLength(t("work.words", { count: chapter.words }), chapter.audio_seconds),
      seconds: chapter.audio_seconds,
    });
  }
  if (work.back_matter_blocks > 0 || work.back_matter_audio_seconds !== null) {
    const seconds = work.back_matter_audio_seconds;
    const label = t("work.back_matter");
    parts.push({ key: "back", label, detail: withLength("", seconds), seconds });
  }
  // Parts play from voicing on; before it, none can be ready.
  const playable = ["voicing", "voiced", "ready", "failed"].includes(work.state);

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
                  {playable && (
                    <PartAudio workId={work.id} part={p.key} label={p.label} seconds={p.seconds} />
                  )}
                </li>
              ))}
            </ol>
            {part !== null && (
              <Reader key={part} workId={work.id} part={part} characters={work.characters} />
            )}
          </div>
          <Exports work={work} onChanged={() => setVersion((v) => v + 1)} />
        </>
      )}
    </Shell>
  );
}
