import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useApi } from '../App';
import {
  ApiError,
  type DeskAgent,
  type DeskEvent,
  type DeskSummary,
  type LiveConversation,
  type Refund,
  type WindowDays,
} from '../api/types';
import { useI18n } from '../i18n/context';
import { formatNumber, formatTime } from '../lib/format';
import { upsertById } from '../lib/live';
import type { DeskSection, Route } from '../lib/route';
import { Icon, type IconName } from '../ui/Icon';
import { useNow } from '../ui/hooks';
import { AuditSection } from './Audit';
import { IssuesSection, QualitySection } from './Insights';
import { LiveSection } from './Live';
import { RefundsSection } from './Refunds';

interface DeskData {
  agent: DeskAgent;
  summary: DeskSummary | null;
  conversations: LiveConversation[];
  refunds: Refund[];
  windowDays: WindowDays;
  setWindowDays: (days: WindowDays) => void;
  putConversation: (conversation: LiveConversation) => void;
  putRefund: (refund: Refund) => void;
  reloadRefunds: () => Promise<void>;
  listen: (listener: (event: DeskEvent) => void) => () => void;
  /** Sends a 401 back to the sign-in form. Returns true if it handled the error. */
  handleAuth: (error: unknown) => boolean;
}

const DeskContext = createContext<DeskData | null>(null);

export function useDesk(): DeskData {
  const value = useContext(DeskContext);
  if (!value) throw new Error('useDesk needs the desk workspace');
  return value;
}

const NAV: { section: DeskSection; icon: IconName }[] = [
  { section: 'live', icon: 'chat' },
  { section: 'refunds', icon: 'receipt' },
  { section: 'audit', icon: 'list' },
  { section: 'issues', icon: 'bars' },
  { section: 'quality', icon: 'pulse' },
];

function DohaClock() {
  const { t, locale } = useI18n();
  const now = useNow(30_000);
  return (
    <p className="desk__clock">
      {t('desk.doha')} <bdi className="mono">{formatTime(new Date(now).toISOString(), locale)}</bdi>
    </p>
  );
}

function ShiftStrip({ summary }: { summary: DeskSummary | null }) {
  const { t, locale } = useI18n();
  const cells = [
    { key: 'desk.sum.live', value: summary?.live, hot: false },
    { key: 'desk.sum.waiting', value: summary?.waiting, hot: (summary?.waiting ?? 0) > 0 },
    { key: 'desk.sum.refunds', value: summary?.refundsPending, hot: false },
    { key: 'desk.sum.resolved', value: summary?.resolvedToday, hot: false },
  ] as const;
  return (
    <dl className="shift" aria-label={t('desk.shift')}>
      {cells.map((cell) => (
        <div key={cell.key} className={cell.hot ? 'shift__cell is-hot' : 'shift__cell'}>
          <dt>{t(cell.key)}</dt>
          <dd>{cell.value === undefined ? '-' : formatNumber(cell.value, locale)}</dd>
        </div>
      ))}
    </dl>
  );
}

function SignIn({ onSignedIn }: { onSignedIn: (agent: DeskAgent) => void }) {
  const api = useApi();
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const sample = api.mode !== 'live';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(false);
    try {
      onSignedIn(await api.signInToDesk(email, password));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="signin">
      <h1 id="page-title" tabIndex={-1}>
        {t('signin.heading')}
      </h1>
      <form onSubmit={(event) => void submit(event)}>
        {sample ? (
          // The sample desk never asks for a password, so nobody types a real one here.
          <p>{t('signin.sample')}</p>
        ) : (
          <>
            <label className="field">
              <span className="field__label">{t('signin.email')}</span>
              <input
                className="field__input field__input--ltr"
                type="email"
                dir="ltr"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">{t('signin.password')}</span>
              <input
                className="field__input field__input--ltr"
                type="password"
                dir="ltr"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
          </>
        )}
        {error && (
          <p className="field__error" role="alert">
            <Icon name="alert" size={18} />
            <span>{t('signin.error')}</span>
          </p>
        )}
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {t(sample ? 'signin.sampleButton' : 'signin.submit')}
        </button>
      </form>
    </div>
  );
}

function Workspace({
  agent,
  section,
  id,
  onSignedOut,
}: {
  agent: DeskAgent;
  section: DeskSection;
  id: string | null;
  onSignedOut: () => void;
}) {
  const api = useApi();
  const { t, locale } = useI18n();
  const [summary, setSummary] = useState<DeskSummary | null>(null);
  const [conversations, setConversations] = useState<LiveConversation[]>([]);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [windowDays, setWindowDays] = useState<WindowDays>(7);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const listeners = useRef(new Set<(event: DeskEvent) => void>());

  // Stable on purpose. A conversation page depends on this, so a new one on every desk
  // event would rebuild the page, reply box included, under someone typing.
  const listen = useCallback((listener: (event: DeskEvent) => void) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const handleAuth = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        onSignedOut();
        return true;
      }
      return false;
    },
    [onSignedOut],
  );

  const reloadRefunds = useCallback(async () => {
    setRefunds(await api.listRefunds());
  }, [api]);

  useEffect(() => {
    let live = true;
    setFailed(false);
    void Promise.all([api.getDeskSummary(), api.listConversations(), api.listRefunds()])
      .then(([nextSummary, nextConversations, nextRefunds]) => {
        if (!live) return;
        setSummary(nextSummary);
        setConversations(nextConversations);
        setRefunds(nextRefunds);
      })
      .catch((error: unknown) => {
        if (live && !handleAuth(error)) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [api, handleAuth, locale, attempt]);

  useEffect(
    () =>
      api.subscribeDesk((event) => {
        switch (event.type) {
          case 'summary.updated':
            setSummary(event.summary);
            break;
          case 'conversation.updated':
            setConversations((list) => upsertById(list, event.conversation));
            break;
          case 'refund.created':
          case 'refund.updated':
            setRefunds((list) => upsertById(list, event.refund));
            break;
          default:
            break;
        }
        for (const listener of listeners.current) listener(event);
      }),
    [api],
  );

  const signOut = async () => {
    try {
      await api.signOutOfDesk();
    } finally {
      onSignedOut();
    }
  };

  const value = useMemo<DeskData>(
    () => ({
      agent,
      summary,
      conversations,
      refunds,
      windowDays,
      setWindowDays,
      putConversation: (conversation) => setConversations((list) => upsertById(list, conversation)),
      putRefund: (refund) => setRefunds((list) => upsertById(list, refund)),
      reloadRefunds,
      listen,
      handleAuth,
    }),
    [agent, summary, conversations, refunds, windowDays, reloadRefunds, listen, handleAuth],
  );

  const pending = summary?.refundsPending ?? 0;

  return (
    <DeskContext.Provider value={value}>
      <div className="desk">
        <div className="desk__head">
          <h1 id="page-title" tabIndex={-1}>
            {t(`desk.title.${section}`)}
          </h1>
          <div className="desk__who">
            <DohaClock />
            <p className="desk__agent">{t('desk.signedInAs', { name: agent.name })}</p>
            <button type="button" className="link" onClick={() => void signOut()}>
              <Icon name="signOut" size={18} flip />
              {t('desk.signOut')}
            </button>
          </div>
        </div>
        <ShiftStrip summary={summary} />
        <nav className="desk__nav" aria-label={t('desk.sections')}>
          {NAV.map((item) => (
            <a
              key={item.section}
              href={`#/desk/${item.section}`}
              aria-current={item.section === section ? 'page' : undefined}
            >
              <Icon name={item.icon} />
              <span>{t(`desk.${item.section}`)}</span>
              {item.section === 'refunds' && pending > 0 && (
                <span className="desk__count">{formatNumber(pending, locale)}</span>
              )}
            </a>
          ))}
        </nav>
        {failed ? (
          <p className="load-error" role="alert">
            <Icon name="alert" />
            <span>{t('desk.error')}</span>
            <button type="button" className="link" onClick={() => setAttempt((n) => n + 1)}>
              {t('desk.retry')}
            </button>
          </p>
        ) : (
          <SectionView section={section} id={id} />
        )}
        <p className="fine desk__foot">{t('app.fictional')}</p>
      </div>
    </DeskContext.Provider>
  );
}

function SectionView({ section, id }: { section: DeskSection; id: string | null }): ReactNode {
  switch (section) {
    case 'live':
      return <LiveSection id={id} />;
    case 'refunds':
      return <RefundsSection />;
    case 'audit':
      return <AuditSection />;
    case 'issues':
      return <IssuesSection />;
    case 'quality':
      return <QualitySection />;
  }
}

export function Desk({ route }: { route: Extract<Route, { page: 'desk' }> }) {
  const api = useApi();
  const { t } = useI18n();
  const [agent, setAgent] = useState<DeskAgent | null | undefined>(undefined);
  // The heading only exists once the session has loaded, so a link that brought someone
  // here hands focus over at that point. A fresh page load leaves the skip link first.
  const [focusHeading, setFocusHeading] = useState(() => document.activeElement !== document.body);

  useEffect(() => {
    if (agent === undefined || !focusHeading) return;
    document.getElementById('page-title')?.focus({ preventScroll: true });
    setFocusHeading(false);
  }, [agent, focusHeading]);

  // A refresh restores the session from the cookie.
  useEffect(() => {
    let live = true;
    void api
      .getDeskAgent()
      .then((value) => {
        if (live) setAgent(value);
      })
      .catch(() => {
        if (live) setAgent(null);
      });
    return () => {
      live = false;
    };
  }, [api]);

  const changeAgent = useCallback((next: DeskAgent | null) => {
    setAgent(next);
    setFocusHeading(true);
  }, []);
  const signedOut = useCallback(() => changeAgent(null), [changeAgent]);

  if (agent === undefined) return <p className="loading">{t('desk.loading')}</p>;
  if (agent === null) return <SignIn onSignedIn={changeAgent} />;
  return <Workspace agent={agent} section={route.section} id={route.id} onSignedOut={signedOut} />;
}
