import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { useApi } from '../App';
import type { ConversationDetail, LiveConversation, TranscriptEntry } from '../api/types';
import { useI18n } from '../i18n/context';
import { stripMarkers, uniqueSources } from '../lib/citations';
import { formatClock, formatTime } from '../lib/format';
import { sortLive } from '../lib/live';
import { Icon } from '../ui/Icon';
import { useNow } from '../ui/hooks';
import { useDesk } from './Desk';

function WaitClock({ since }: { since: string }) {
  const { t } = useI18n();
  const now = useNow(1000);
  const seconds = (now - Date.parse(since)) / 1000;
  return <span className="waitclock">{t('live.waitingFor', { clock: formatClock(seconds) })}</span>;
}

function StateTag({ conversation }: { conversation: LiveConversation }) {
  const { t } = useI18n();
  const { state, agentName } = conversation;
  if (state === 'agent') {
    return <span className="tag tag--person">{t('live.state.agent', { name: agentName ?? '' })}</span>;
  }
  return <span className={`tag tag--${state}`}>{t(`live.state.${state}`)}</span>;
}

function Row({ conversation, selected }: { conversation: LiveConversation; selected: boolean }) {
  const { t } = useI18n();
  return (
    <li>
      <a
        className={conversation.priority === 'high' ? 'liverow is-urgent' : 'liverow'}
        href={`#/desk/live/${encodeURIComponent(conversation.id)}`}
        aria-current={selected ? 'true' : undefined}
      >
        <span className="liverow__top">
          <strong dir="auto">{conversation.customer}</strong>
          <StateTag conversation={conversation} />
        </span>
        <span className="liverow__summary">{conversation.summary}</span>
        <span className="liverow__meta">
          {conversation.priority === 'high' && (
            <span className="tag tag--bad">
              <Icon name="alert" size={14} />
              {t('live.urgent')}
            </span>
          )}
          {conversation.waitingSince && <WaitClock since={conversation.waitingSince} />}
          {conversation.orderId && <bdi className="mono">{conversation.orderId}</bdi>}
        </span>
      </a>
    </li>
  );
}

function Entry({ entry, locale }: { entry: TranscriptEntry; locale: string }) {
  const { t, locale: deskLocale } = useI18n();
  const sources = uniqueSources(entry.sources);
  return (
    <li className={`line line--${entry.author}`}>
      <p className="line__who">
        <span dir="auto">{entry.name ?? t(`author.${entry.author}`)}</span>
        <bdi className="mono">{formatTime(entry.at, deskLocale)}</bdi>
      </p>
      <p className="line__text" lang={locale} dir="auto">
        {stripMarkers(entry.text)}
      </p>
      {entry.tools.length > 0 && (
        <p className="line__extra">
          <span>{t('live.tools')}</span> {entry.tools.join(', ')}
        </p>
      )}
      {sources.length > 0 && (
        <p className="line__extra">
          <span>{t('live.sources')}</span> {sources.join(deskLocale === 'ar' ? '، ' : ', ')}
        </p>
      )}
    </li>
  );
}

function Detail({ id }: { id: string }) {
  const api = useApi();
  const { t, locale } = useI18n();
  const { agent, conversations, putConversation, listen, handleAuth } = useDesk();
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState(false);
  const live = conversations.find((c) => c.id === id) ?? detail;

  useEffect(() => {
    let active = true;
    setDetail(null);
    setFailed(false);
    void api
      .getConversationDetail(id)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch((error: unknown) => {
        if (active && !handleAuth(error)) setFailed(true);
      });
    const stop = listen((event) => {
      if (event.type !== 'conversation.message' || event.conversationId !== id) return;
      setDetail((current) => {
        if (!current || current.transcript.some((e) => e.id === event.entry.id)) return current;
        return { ...current, transcript: [...current.transcript, event.entry] };
      });
    });
    return () => {
      active = false;
      stop();
    };
  }, [api, handleAuth, id, listen, locale]);

  if (failed) return <p className="load-error">{t('desk.error')}</p>;
  if (!detail || !live) return <p className="loading">{t('desk.loading')}</p>;

  const mine = live.state === 'agent' && live.agentName === agent.name;

  const takeOver = async () => {
    setBusy(true);
    try {
      putConversation(await api.claimConversation(id));
    } catch (error) {
      handleAuth(error);
    } finally {
      setBusy(false);
    }
  };

  const close = async () => {
    setBusy(true);
    try {
      putConversation(await api.closeConversation(id));
    } catch (error) {
      handleAuth(error);
    } finally {
      setBusy(false);
    }
  };

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const text = reply.trim();
    if (!text) return;
    setBusy(true);
    try {
      await api.replyToConversation(id, text);
      setReply('');
    } catch (error) {
      handleAuth(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="convo">
      <a className="convo__back" href="#/desk/live">
        <Icon name="back" flip size={18} />
        {t('live.back')}
      </a>
      <header className="convo__head">
        <div>
          <h2 dir="auto">{live.customer}</h2>
          <p className="muted">{live.summary}</p>
          <p className="convo__facts">
            <StateTag conversation={live} />
            <span className={live.verified ? 'tag tag--approved' : 'tag'}>
              <Icon name={live.verified ? 'shield' : 'alert'} size={14} />
              {t(live.verified ? 'live.verified' : 'live.unverified')}
            </span>
            <span className="tag">{t(live.locale === 'ar' ? 'live.langAr' : 'live.langEn')}</span>
            {live.orderId && (
              <span className="tag">{t('live.orderRef', { id: live.orderId })}</span>
            )}
          </p>
        </div>
        {live.state !== 'closed' && (
          <div className="convo__actions">
            {live.state !== 'agent' && (
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void takeOver()}>
                <Icon name="person" size={18} />
                {t('live.takeOver')}
              </button>
            )}
            <button type="button" className="btn" disabled={busy} onClick={() => void close()}>
              {t('live.close')}
            </button>
          </div>
        )}
      </header>
      <ol className="transcript">
        {detail.transcript.map((entry) => (
          <Entry key={entry.id} entry={entry} locale={live.locale} />
        ))}
      </ol>
      {mine ? (
        <form className="reply" onSubmit={(event) => void send(event)}>
          <label className="field">
            <span className="field__label">{t('live.replyLabel', { name: live.customer })}</span>
            <textarea
              className="field__input"
              dir="auto"
              rows={2}
              value={reply}
              placeholder={t('live.replyPlaceholder')}
              onChange={(event) => setReply(event.target.value)}
            />
          </label>
          <button type="submit" className="btn btn--primary" disabled={busy || !reply.trim()}>
            {t('live.replySend')}
          </button>
        </form>
      ) : (
        <p className="convo__note">
          {t(live.state === 'waiting' ? 'live.waitingNote' : 'live.readOnly')}
        </p>
      )}
    </div>
  );
}

export function LiveSection({ id }: { id: string | null }) {
  const { t } = useI18n();
  const { conversations } = useDesk();
  const sorted = useMemo(
    () => sortLive(conversations.filter((c) => c.state !== 'closed')),
    [conversations],
  );
  return (
    <div className={id ? 'live has-detail' : 'live'}>
      <section className="live__list" aria-label={t('live.listLabel')}>
        {sorted.length === 0 ? (
          <p className="muted">{t('live.empty')}</p>
        ) : (
          <ul>
            {sorted.map((conversation) => (
              <Row key={conversation.id} conversation={conversation} selected={conversation.id === id} />
            ))}
          </ul>
        )}
      </section>
      <section className="live__detail" aria-label={t('desk.title.live')}>
        {id ? <Detail key={id} id={id} /> : <p className="live__pick">{t('live.pick')}</p>}
      </section>
    </div>
  );
}
