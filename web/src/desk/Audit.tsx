import { useEffect, useState } from 'react';
import { useApi } from '../App';
import type { AuditEntry, AuditFilter } from '../api/types';
import type { MessageKey } from '../i18n/en';
import { useI18n } from '../i18n/context';
import { hasMessage } from '../i18n/translate';
import { formatDateTime } from '../lib/format';
import { useDesk } from './Desk';

const FILTERS: AuditFilter[] = ['all', 'bot', 'agent', 'guardrail'];

function matches(entry: AuditEntry, filter: AuditFilter): boolean {
  if (filter === 'bot') return entry.actorKind === 'bot' && entry.action !== 'guardrail.blocked';
  if (filter === 'agent') return entry.actorKind === 'agent';
  if (filter === 'guardrail') return entry.action === 'guardrail.blocked';
  return true;
}

export function AuditSection() {
  const api = useApi();
  const { t, locale } = useI18n();
  const { listen, handleAuth } = useDesk();
  const [filter, setFilter] = useState<AuditFilter>('all');
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    setLoaded(false);
    void api
      .listAudit(filter, null)
      .then((page) => {
        if (!active) return;
        setEntries(page.entries);
        setCursor(page.nextCursor);
        setLoaded(true);
      })
      .catch((error: unknown) => {
        handleAuth(error);
      });
    const stop = listen((event) => {
      if (event.type !== 'audit.appended' || !matches(event.entry, filter)) return;
      setEntries((list) => (list.some((e) => e.id === event.entry.id) ? list : [event.entry, ...list]));
    });
    return () => {
      active = false;
      stop();
    };
  }, [api, filter, handleAuth, listen, locale]);

  const loadMore = async () => {
    const page = await api.listAudit(filter, cursor);
    setEntries((list) => [...list, ...page.entries]);
    setCursor(page.nextCursor);
  };

  const actionLabel = (action: string) => {
    const key = `audit.act.${action}`;
    return hasMessage(locale, key) ? t(key as MessageKey) : action;
  };

  return (
    <div className="audit">
      <p className="section-intro">{t('audit.intro')}</p>
      <div className="filters" role="group" aria-label={t('audit.filterLabel')}>
        {FILTERS.map((name) => (
          <button key={name} type="button" aria-pressed={filter === name} onClick={() => setFilter(name)}>
            {t(`audit.filter.${name}`)}
          </button>
        ))}
      </div>
      {loaded && entries.length === 0 ? (
        <p className="empty">{t('audit.empty')}</p>
      ) : (
        <table className="ledger" aria-label={t('desk.title.audit')}>
          <thead>
            <tr>
              <th scope="col">{t('audit.time')}</th>
              <th scope="col">{t('audit.who')}</th>
              <th scope="col">{t('audit.action')}</th>
              <th scope="col">{t('audit.target')}</th>
              <th scope="col">{t('audit.detail')}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id} className={entry.action === 'guardrail.blocked' ? 'is-blocked' : undefined}>
                <td data-label={t('audit.time')}>
                  <bdi className="mono">{formatDateTime(entry.at, locale)}</bdi>
                </td>
                <td data-label={t('audit.who')}>
                  <span dir="auto">{entry.actorName}</span>
                </td>
                <td data-label={t('audit.action')}>{actionLabel(entry.action)}</td>
                <td data-label={t('audit.target')}>
                  <bdi className="mono">{entry.target}</bdi>
                </td>
                <td data-label={t('audit.detail')}>
                  <span dir="auto">{entry.detail}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {cursor ? (
        <button type="button" className="btn audit__more" onClick={() => void loadMore()}>
          {t('audit.more')}
        </button>
      ) : (
        loaded && entries.length > 0 && <p className="fine">{t('audit.end')}</p>
      )}
    </div>
  );
}
