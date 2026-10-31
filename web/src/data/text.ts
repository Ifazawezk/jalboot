import type { Locale } from '../api/types';

/** Sample text in both languages, resolved when the data is read. */
export interface L {
  en: string;
  ar: string;
}

export function pick(text: L | string, locale: Locale): string {
  return typeof text === 'string' ? text : text[locale];
}
