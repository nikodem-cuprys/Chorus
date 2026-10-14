import { Spans } from "./Blocks";
import { t, type MessageKey } from "./i18n";
import type { Line } from "./works";

/** A part's Script, line by line, with each line's kind, for checking the split. A line that
 * starts a new paragraph gets space above it; lines that are not voiced are greyed out. */
export function Lines({ lines }: { lines: Line[] }) {
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
