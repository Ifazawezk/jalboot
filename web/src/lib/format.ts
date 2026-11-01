import type { Locale } from '../api/types';

// Western digits in both languages, so order numbers, prices and times match what
// customers see on receipts. Times always show Doha time, wherever the viewer is.
const TAGS: Record<Locale, string> = { en: 'en-QA', ar: 'ar-QA-u-nu-latn' };
const ZONE = 'Asia/Qatar';

export function localeTag(locale: Locale): string {
  return TAGS[locale];
}

export function formatQar(amount: number, locale: Locale): string {
  return new Intl.NumberFormat(TAGS[locale], {
    style: 'currency',
    currency: 'QAR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(value: number, locale: Locale, digits = 0): string {
  return new Intl.NumberFormat(TAGS[locale], {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatTime(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(TAGS[locale], {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: ZONE,
  }).format(new Date(iso));
}

export function formatDay(iso: string, locale: Locale): string {
  return new Intl.DateTimeFormat(TAGS[locale], {
    day: 'numeric',
    month: 'short',
    timeZone: ZONE,
  }).format(new Date(iso));
}

export function formatDateTime(iso: string, locale: Locale): string {
  return `${formatDay(iso, locale)}, ${formatTime(iso, locale)}`;
}

/** Elapsed time as m:ss or h:mm:ss. The caller wraps it in bdi so it reads left to right. */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, '0');
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}:${ss}`;
  return `${minutes}:${ss}`;
}

/**
 * Forces a run left to right. A masked phone or a signed number has no letters, so an
 * auto-detecting isolate cannot tell its direction and Arabic text would reverse it.
 */
export function forceLtr(value: string): string {
  return `\u2066${value}\u2069`;
}

/** Wraps a value in Unicode isolates so Latin names and numbers keep their place in Arabic text. */
export function isolate(value: string): string {
  return `\u2068${value}\u2069`;
}
