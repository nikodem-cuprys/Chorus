// The message catalogue. Every string the interface shows comes from here, by key;
// the backend sends keys with parameters, never display text. English only until
// milestone 5 adds Polish and a test that both catalogues have the same keys.
import en from "./en.json";

export type MessageKey = keyof typeof en;
export type Params = Record<string, string | number>;

/** A message as the backend sends it: a catalogue key and its parameters. */
export interface Message {
  key: string;
  params?: Params;
}

const catalogue: Record<string, string> = en;

function fill(template: string, params: Params = {}): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}

export function t(key: MessageKey, params?: Params): string {
  return fill(catalogue[key], params);
}

/** A key that comes from the backend; an unknown key shows as itself rather than failing. */
export function tMessage(message: Message): string {
  const template = catalogue[message.key];
  return template === undefined ? message.key : fill(template, message.params);
}

/** The interface language; English until milestone 5. */
export const locale = "en";

/** A language's name in the interface language, from the browser's own list. */
export function languageName(code: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}
