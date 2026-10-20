import { Spans } from "./Blocks";
import { t, type MessageKey } from "./i18n";
import type { Character, Line } from "./works";

/** Who says a quoted line and how, once analysis has labelled it: "Mrs. Bennet · excited, strong". */
function speakerTag(line: Line, characters: Character[]): string {
  if (line.kind === "narration" || line.speaker === null || line.speaker === undefined) return "";
  const name =
    line.speaker === "character"
      ? (characters.find((c) => c.id === line.character_id)?.name ?? t("line.speaker.unknown"))
      : t(`line.speaker.${line.speaker}`);
  if (line.emotion === null) return ` · ${name}`;
  const strong = line.intensity === "strong" ? `, ${t("line.intensity.strong")}` : "";
  return ` · ${name} · ${t(`emotion.${line.emotion}`)}${strong}`;
}

/** A part's Script, line by line, with each line's kind and, once analysed, each quotation's
 * Speaker and Emotion. A line that starts a new paragraph gets space above it; lines that are
 * not voiced are greyed out. */
export function Lines({ lines, characters = [] }: { lines: Line[]; characters?: Character[] }) {
  if (lines.length === 0) return <p className="muted">{t("work.no_lines")}</p>;
  return (
    <ol className="lines">
      {lines.map((line, n) => {
        const previous = n > 0 ? lines[n - 1] : null;
        const classes = ["line", `line-${line.kind}`];
        if (!line.voiced) classes.push("line-not-voiced");
        if (previous && line.paragraph !== previous.last_paragraph) classes.push("line-paragraph");
        return (
          <li key={line.position} className={classes.join(" ")}>
            <span className="line-tags small">
              {t(`line.kind.${line.kind}` as MessageKey)}
              {line.passage !== "narration" &&
                ` · ${t(`line.passage.${line.passage}` as MessageKey)}`}
              {!line.voiced && line.passage !== "never_voiced" && ` · ${t("line.not_voiced")}`}
              {speakerTag(line, characters)}
            </span>
            <span className="line-text">
              <Spans spans={line.spans} />
            </span>
          </li>
        );
      })}
    </ol>
  );
}
