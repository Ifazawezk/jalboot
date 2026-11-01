import { BRAND_NAME, BRAND_NAME_AR } from '../brand';
import type { Locale } from '../api/types';
import { isolate } from '../lib/format';
import { ar } from './ar';
import { en, type MessageKey } from './en';

const DICTS: Record<Locale, Record<MessageKey, string>> = { en, ar };

export type Vars = Record<string, string | number>;

export function brandFor(locale: Locale): string {
  return locale === 'ar' ? BRAND_NAME_AR : BRAND_NAME;
}

/**
 * Looks up a message and fills its {slots}. In Arabic every value is wrapped in bidi
 * isolates, so a Latin name or an order number cannot reorder the sentence around it.
 */
export function translate(locale: Locale, key: MessageKey, vars?: Vars): string {
  const template = DICTS[locale][key];
  const all: Vars = { brand: brandFor(locale), ...vars };
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = all[name];
    if (value === undefined) return whole;
    return locale === 'ar' ? isolate(String(value)) : String(value);
  });
}

type PluralForms = Partial<Record<Intl.LDMLPluralRule, string>> & { other: string };

const MINUTES: Record<Locale, PluralForms> = {
  en: { one: '{n} minute', other: '{n} minutes' },
  ar: {
    zero: 'أقل من دقيقة',
    one: 'دقيقة واحدة',
    two: 'دقيقتان',
    few: '{n} دقائق',
    many: '{n} دقيقة',
    other: '{n} دقيقة',
  },
};

const DAYS: Record<Locale, PluralForms> = {
  en: { one: '{n} day', other: '{n} days' },
  ar: {
    one: 'يوم واحد',
    two: 'يومان',
    few: '{n} أيام',
    many: '{n} يومًا',
    other: '{n} يوم',
  },
};

function plural(table: Record<Locale, PluralForms>, locale: Locale, n: number): string {
  const rule = new Intl.PluralRules(locale === 'ar' ? 'ar' : 'en').select(n);
  const forms = table[locale];
  return (forms[rule] ?? forms.other).replace('{n}', String(n));
}

/** Arabic needs all six plural forms, so counted nouns cannot be plain templates. */
export function formatMinutes(locale: Locale, n: number): string {
  return plural(MINUTES, locale, n);
}

export function formatDays(locale: Locale, n: number): string {
  return plural(DAYS, locale, n);
}

export function hasMessage(locale: Locale, key: string): boolean {
  return key in DICTS[locale];
}

export function messageKeys(locale: Locale): string[] {
  return Object.keys(DICTS[locale]);
}

export function rawMessage(locale: Locale, key: MessageKey): string {
  return DICTS[locale][key];
}
