import type { ReactNode } from "react";
import type { Block, Mark, Span } from "./works";

const WRAPPERS: Record<Mark, (children: ReactNode) => ReactNode> = {
  italic: (c) => <em>{c}</em>,
  bold: (c) => <strong>{c}</strong>,
  underline: (c) => <u>{c}</u>,
  strike: (c) => <s>{c}</s>,
  small_caps: (c) => <span className="small-caps">{c}</span>,
  superscript: (c) => <sup>{c}</sup>,
};

function withBreaks(text: string): ReactNode {
  const lines = text.split("\n");
  return lines.map((line, n) => (
    <span key={n}>
      {n > 0 && <br />}
      {line}
    </span>
  ));
}

function SpanText({ span }: { span: Span }) {
  let node: ReactNode = withBreaks(span.text);
  for (const mark of span.marks ?? []) node = WRAPPERS[mark](node);
  return <>{node}</>;
}

function Spans({ spans }: { spans: Span[] }) {
  return (
    <>
      {spans.map((span, n) => (
        <SpanText key={n} span={span} />
      ))}
    </>
  );
}

/** A chapter's text as imported: plain text with marks, by kind of block. */
export function Blocks({ blocks }: { blocks: Block[] }) {
  return (
    <div className="text">
      {blocks.map((block, n) => {
        const spans = <Spans spans={block.spans} />;
        switch (block.type) {
          case "heading":
            return (
              <div key={n} className={`block-heading level-${block.level ?? 2}`}>
                {spans}
              </div>
            );
          case "section_break":
            return <hr key={n} className="section-break" />;
          case "quote":
            return (
              <blockquote key={n} className="block-quote">
                {spans}
              </blockquote>
            );
          case "list_item":
            return (
              <p key={n} className="block-list-item">
                {spans}
              </p>
            );
          default:
            return (
              <p key={n} className={`block-${block.type}`}>
                {spans}
              </p>
            );
        }
      })}
    </div>
  );
}
