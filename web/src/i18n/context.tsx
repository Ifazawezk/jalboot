import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { Locale } from '../api/types';
import type { MessageKey } from './en';
import { translate, type Vars } from './translate';

interface I18n {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, vars?: Vars) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function readInitialLocale(): Locale {
  return document.documentElement.lang === 'ar' ? 'ar' : 'en';
}

export function I18nProvider({
  children,
  onChange,
}: {
  children: ReactNode;
  /** Runs before the re-render, so data loaded for the new language uses it. */
  onChange: (locale: Locale) => void;
}) {
  const [locale, setLocaleState] = useState<Locale>(readInitialLocale);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = locale;
    root.dir = locale === 'ar' ? 'rtl' : 'ltr';
  }, [locale]);

  const setLocale = useCallback(
    (next: Locale) => {
      try {
        localStorage.setItem('support.lang', next);
      } catch {
        // Blocked storage only means the choice is not remembered.
      }
      onChange(next);
      setLocaleState(next);
    },
    [onChange],
  );

  const value = useMemo<I18n>(
    () => ({ locale, setLocale, t: (key, vars) => translate(locale, key, vars) }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n needs I18nProvider');
  return value;
}
