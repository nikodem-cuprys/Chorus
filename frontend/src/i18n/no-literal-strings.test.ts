// @vitest-environment node
// Every string the interface shows must come from the message catalogue. This test parses
// each .tsx file and fails on text written straight into JSX.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import en from "./en.json";

const SRC = fileURLToPath(new URL("..", import.meta.url));

// Attributes whose value a user reads or hears.
const TEXT_ATTRIBUTES = new Set(["title", "placeholder", "alt", "aria-label", "label"]);
const HAS_LETTERS = /\p{L}/u;

function tsxFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return tsxFiles(path);
    return entry.name.endsWith(".tsx") && !entry.name.endsWith(".test.tsx") ? [path] : [];
  });
}

export function literalStrings(source: string, fileName = "file.tsx"): string[] {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found: string[] = [];
  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && HAS_LETTERS.test(node.text)) {
      found.push(node.text.trim());
    } else if (
      ts.isJsxAttribute(node) &&
      TEXT_ATTRIBUTES.has(node.name.getText(file)) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer) &&
      HAS_LETTERS.test(node.initializer.text)
    ) {
      found.push(node.initializer.text);
    } else if (
      ts.isJsxExpression(node) &&
      node.expression &&
      (ts.isStringLiteral(node.expression) || ts.isNoSubstitutionTemplateLiteral(node.expression)) &&
      ts.isJsxElement(node.parent) &&
      HAS_LETTERS.test(node.expression.text)
    ) {
      found.push(node.expression.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return found;
}

describe("interface text", () => {
  it("is never written straight into JSX", () => {
    const offenders = tsxFiles(SRC).flatMap((path) =>
      literalStrings(readFileSync(path, "utf8"), path).map((text) => `${path}: "${text}"`),
    );
    expect(offenders).toEqual([]);
  });

  it("catches the kinds of literal it is meant to", () => {
    const source = `
      const a = <p>Hello there</p>;
      const b = <input placeholder="Search" />;
      const c = <span>{"Inline"}</span>;
      const fine = <p className="muted">{t("x")} · 100%</p>;
    `;
    expect(literalStrings(source)).toEqual(["Hello there", "Search", "Inline"]);
  });

  it("has no empty messages", () => {
    const empty = Object.entries(en).filter(([, text]) => text.trim() === "");
    expect(empty).toEqual([]);
  });
});
