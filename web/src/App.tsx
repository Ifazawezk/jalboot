import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import type { SupportApi } from './api/client';
import { ChatProvider, useChat } from './chat/ChatProvider';
import { ChatScreen } from './chat/ChatScreen';
import { Desk } from './desk/Desk';
import { I18nProvider, useI18n } from './i18n/context';
import { brandFor } from './i18n/translate';
import { bannerFor } from './lib/mode';
import { BrandMark, Icon } from './ui/Icon';
import { useRoute } from './ui/hooks';

const ApiContext = createContext<SupportApi | null>(null);

export function useApi(): SupportApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error('useApi needs a provider');
  return api;
}

export function App({ api }: { api: SupportApi }) {
  const onLocale = useMemo(() => api.setLocale.bind(api), [api]);
  return (
    <ApiContext.Provider value={api}>
      <I18nProvider onChange={onLocale}>
        <ChatProvider>
          <Shell />
        </ChatProvider>
      </I18nProvider>
    </ApiContext.Provider>
  );
}

function readTheme(): 'light' | 'dark' {
  const set = document.documentElement.dataset.theme;
  if (set === 'light' || set === 'dark') return set;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function ThemeButton() {
  const { t } = useI18n();
  const [theme, setTheme] = useState(readTheme);
  const next = theme === 'dark' ? 'light' : 'dark';
  const toggle = () => {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem('support.theme', next);
    } catch {
      // Blocked storage only means the choice is not remembered.
    }
    setTheme(next);
  };
  return (
    <button
      type="button"
      className="tool"
      onClick={toggle}
      aria-label={t(theme === 'dark' ? 'app.theme.toLight' : 'app.theme.toDark')}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  );
}

function ModeBanner() {
  const api = useApi();
  const { assistant, recordings } = useChat();
  const { t } = useI18n();
  const banner = bannerFor(api.mode, assistant);
  if (!banner) return null;
  const recorded = banner === 'demo' && recordings.some((recording) => recording.source);
  return (
    <p className={banner === 'mock' ? 'mode' : `mode mode--${banner}`}>
      <strong>
        {banner === 'demo' && <span className="rec-dot" aria-hidden="true" />}
        {t(recorded ? 'mode.recorded.title' : `mode.${banner}.title`)}
      </strong>{' '}
      <span>{t(recorded ? 'mode.recorded.body' : `mode.${banner}.body`)}</span>
    </p>
  );
}

function Shell() {
  const { t, locale, setLocale } = useI18n();
  const route = useRoute();
  const onDesk = route.page === 'desk';
  const section = onDesk ? route.section : null;
  const first = useRef(true);

  useEffect(() => {
    document.title = t(onDesk ? 'app.pageTitle.desk' : 'app.pageTitle.chat');
  }, [onDesk, t]);

  // A hash change is a new page to a screen reader, so focus moves to its heading.
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    document.getElementById('page-title')?.focus({ preventScroll: true });
  }, [onDesk, section]);

  const skip = (event: MouseEvent) => {
    event.preventDefault();
    document.getElementById('main')?.focus();
  };

  return (
    <div className={onDesk ? 'app app--desk' : 'app app--chat'}>
      <a className="skip" href="#main" onClick={skip}>
        {t('app.skip')}
      </a>
      <header>
        <ModeBanner />
        <div className="mast">
          <a className="wordmark" href="#/chat">
            <BrandMark />
            <span>{brandFor(locale)}</span>
          </a>
          <nav className="mast__nav" aria-label={t('app.nav')}>
            <a href="#/chat" aria-current={onDesk ? undefined : 'page'}>
              {t('app.nav.chat')}
            </a>
            <a href="#/desk/live" aria-current={onDesk ? 'page' : undefined}>
              {t('app.nav.desk')}
            </a>
          </nav>
          <div className="mast__tools">
            {/* The language names itself, so it reads correctly in either language. */}
            <button
              type="button"
              className="tool tool--lang"
              lang={locale === 'ar' ? 'en' : 'ar'}
              onClick={() => setLocale(locale === 'ar' ? 'en' : 'ar')}
            >
              {t('app.lang.switch')}
            </button>
            <ThemeButton />
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {route.page === 'desk' ? <Desk route={route} /> : <ChatScreen />}
      </main>
    </div>
  );
}
