export type TextPart = { kind: 'text'; text: string } | { kind: 'cite'; n: number };

const MARKER = /\[(\d{1,2})\]/g;

/**
 * Splits reply text into plain runs and citation markers. A marker whose citation
 * has not arrived stays as text. While streaming, a half-written marker at the very
 * end is held back so "[" never flashes on screen.
 */
export function parseCitedText(
  text: string,
  known: ReadonlySet<number>,
  streaming: boolean,
): TextPart[] {
  const source = streaming ? text.replace(/\[\d{0,2}$/, '') : text;
  const parts: TextPart[] = [];
  let last = 0;
  for (const match of source.matchAll(MARKER)) {
    const n = Number(match[1]);
    if (!known.has(n)) continue;
    const at = match.index;
    if (at > last) parts.push({ kind: 'text', text: source.slice(last, at) });
    parts.push({ kind: 'cite', n });
    last = at + match[0].length;
  }
  if (last < source.length) parts.push({ kind: 'text', text: source.slice(last) });
  return parts;
}

/** For places that list sources separately, or read text aloud, where a marker would be noise. */
export function stripMarkers(text: string): string {
  return text.replace(/\s*\[\d{1,2}\]/g, '');
}

/** Two passages from one page have one title, and it is only worth reading once. */
export function uniqueSources(titles: string[]): string[] {
  return [...new Set(titles.filter(Boolean))];
}

/** Splits text on blank lines. Reply text is plain text, never HTML or Markdown. */
export function splitParagraphs(text: string): string[] {
  return text.split(/\n{2,}/).filter((p) => p.length > 0);
}
