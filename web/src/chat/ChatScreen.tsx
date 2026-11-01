import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { useApi } from '../App';
import { recordedModel, type Recording } from '../data/recordings';
import type { MessageKey } from '../i18n/en';
import { useI18n } from '../i18n/context';
import {
  collectOrders,
  collectSources,
  identityOpen,
  lastSpokenText,
} from '../lib/chatState';
import { formatClock } from '../lib/format';
import { Icon } from '../ui/Icon';
import { useChat } from './ChatProvider';
import { IdentityPanel, RecordedIdentity } from './Identity';
import { ChatLine, HandoffBanner } from './Parts';

const STARTERS: MessageKey[] = [
  'chat.starter.track',
  'chat.starter.missing',
  'chat.starter.cancel',
  'chat.starter.person',
];

function Intro() {
  const { t } = useI18n();
  const { send } = useChat();
  return (
    <div className="intro">
      <h1 id="page-title" tabIndex={-1}>
        {t('chat.heading')} <mark>{t('chat.headingMark')}</mark>
      </h1>
      <p className="intro__lead">{t('chat.disclosure')}</p>
      <h2 className="eyebrow">{t('chat.startersLabel')}</h2>
      <ul className="rows">
        {STARTERS.map((key) => (
          <li key={key}>
            <button type="button" onClick={() => send(t(key))}>
              <span>{t(key)}</span>
              <Icon name="chevron" flip />
            </button>
          </li>
        ))}
      </ul>
      <p className="fine">{t('app.fictional')}</p>
    </div>
  );
}

function recordingLabel(recording: Recording, t: ReturnType<typeof useI18n>['t']): string {
  if (!recording.source) return t('rec.label');
  return t('rec.recordedBody', { model: recordedModel(recording), date: recording.recordedAt.slice(0, 10) });
}

function RecordingPicker() {
  const { t } = useI18n();
  const { recordings, play } = useChat();
  const mixed = recordings.some((recording) => recording.source);
  return (
    <div className="intro">
      <h1 id="page-title" tabIndex={-1}>
        {t(mixed ? 'rec.headingMixed' : 'rec.heading')} <mark>{t('rec.pick')}</mark>
      </h1>
      <p className="intro__lead">{t(mixed ? 'rec.pickBodyMixed' : 'rec.pickBody')}</p>
      <ul className="rows">
        {recordings.map((recording) => {
          const seconds = recording.steps.reduce((sum, step) => sum + step.waitMs, 0) / 1000;
          return (
            <li key={recording.id} data-kind={recording.source ? 'recorded' : 'scripted'}>
              <button type="button" onClick={() => play(recording.id)}>
                <span>
                  <strong>{recording.title}</strong>
                  <small>{recording.summary}</small>
                  <small>{recordingLabel(recording, t)}</small>
                </span>
                <bdi className="mono rows__meta">{formatClock(seconds)}</bdi>
                <Icon name="play" />
              </button>
            </li>
          );
        })}
      </ul>
      <p className="fine">{t('app.fictional')}</p>
    </div>
  );
}

function PlaybackBar() {
  const { t } = useI18n();
  const { playback, skip, play, closeRecording } = useChat();
  const { recording, status, step } = playback;
  if (!recording) return null;
  const total = recording.steps.length;
  return (
    <div className="playback">
      <div className="playback__status">
        <p>
          <span className="tag tag--rec">
            <span className="rec-dot" aria-hidden="true" />
            {t(recording.source ? 'rec.recorded' : 'rec.label')}
          </span>
          <strong>{recording.title}</strong>
          {recording.source && <small className="muted">{recordingLabel(recording, t)}</small>}
          <span className="muted">{t(status === 'finished' ? 'rec.finished' : 'rec.playing')}</span>
        </p>
        <progress value={step} max={total} aria-label={t('rec.progress')} />
      </div>
      <div className="playback__actions">
        {status === 'playing' ? (
          <button type="button" className="btn btn--primary" onClick={skip}>
            <Icon name="skip" flip />
            {t('rec.skip')}
          </button>
        ) : (
          <button type="button" className="btn btn--primary" onClick={() => play(recording.id)}>
            <Icon name="play" />
            {t('rec.replay')}
          </button>
        )}
        <button type="button" className="btn" onClick={closeRecording}>
          {t('rec.another')}
        </button>
      </div>
    </div>
  );
}

function Composer() {
  const { t } = useI18n();
  const { state, send, stop, requestPerson, reset } = useChat();
  const [text, setText] = useState('');
  const ref = useRef<HTMLTextAreaElement>(null);
  const locked = identityOpen(state.identity);
  const agent = state.handoff?.status === 'joined' ? state.handoff.agentName : null;

  useLayoutEffect(() => {
    const box = ref.current;
    if (!box) return;
    box.style.height = 'auto';
    box.style.height = `${Math.min(box.scrollHeight, 160)}px`;
  }, [text]);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || state.streaming || locked || state.closed) return;
    send(trimmed);
    setText('');
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  return (
    <form className="composer" onSubmit={onSubmit}>
      <div className="composer__row">
        <label className="sr-only" htmlFor="composer-input">
          {t('chat.inputLabel')}
        </label>
        <textarea
          id="composer-input"
          ref={ref}
          rows={1}
          dir="auto"
          value={text}
          disabled={locked || state.closed}
          placeholder={
            agent ? t('chat.inputPlaceholderAgent', { name: agent }) : t('chat.inputPlaceholder')
          }
          aria-describedby={locked ? 'composer-locked' : undefined}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
        />
        {state.streaming ? (
          <button type="button" className="send send--stop" onClick={stop} aria-label={t('chat.stop')}>
            <Icon name="stop" />
          </button>
        ) : (
          <button type="submit" className="send" aria-label={t('chat.send')} disabled={locked || !text.trim()}>
            <Icon name="send" flip />
          </button>
        )}
      </div>
      <div className="composer__foot">
        {state.closed ? (
          <p className="composer__hint">
            {t('chat.closed')}{' '}
            <button type="button" className="link" onClick={reset}>
              {t('chat.newChat')}
            </button>
          </p>
        ) : locked ? (
          <p id="composer-locked" className="composer__hint">
            {t('identity.locked')}
          </p>
        ) : (
          <p className="composer__hint composer__hint--wide">{t('chat.hint')}</p>
        )}
        {!state.handoff && !state.closed && (
          <button type="button" className="link" onClick={requestPerson}>
            <Icon name="person" size={18} />
            {t('chat.person')}
          </button>
        )}
      </div>
    </form>
  );
}

function CaseFile() {
  const { t } = useI18n();
  const { state } = useChat();
  const orders = useMemo(() => collectOrders(state.items), [state.items]);
  const sources = useMemo(() => collectSources(state.items), [state.items]);
  const joined = state.handoff?.status === 'joined';
  const waiting = state.handoff && !joined;
  const status = state.closed
    ? t('case.statusClosed')
    : joined
      ? t('case.statusAgent', { name: state.handoff?.agentName ?? '' })
      : waiting
        ? t('case.statusQueued')
        : t('case.statusBot');

  return (
    <aside className="case" aria-label={t('case.heading')}>
      <h2 className="case__title">{t('case.heading')}</h2>
      <dl>
        <div>
          <dt className="eyebrow">{t('case.status')}</dt>
          <dd className="case__status">{status}</dd>
        </div>
        <div>
          <dt className="eyebrow">{t('case.orders')}</dt>
          <dd>
            {orders.length === 0 ? (
              <span className="muted">{t('case.none')}</span>
            ) : (
              orders.map((order) => (
                <p key={order.id}>
                  <bdi className="mono">{order.id}</bdi>
                  <span className="muted" dir="auto">
                    {order.store}
                  </span>
                </p>
              ))
            )}
          </dd>
        </div>
        <div>
          <dt className="eyebrow">{t('case.sources')}</dt>
          <dd>
            {sources.length === 0 ? (
              <span className="muted">{t('case.none')}</span>
            ) : (
              sources.map((source) => (
                // The title leads, because a section can start with a Latin code like LAT-01,
                // which would otherwise set the direction of a whole Arabic line.
                <p key={source.sourceId} dir="auto">
                  {source.title}
                  <small className="case__section">{source.section}</small>
                </p>
              ))
            )}
          </dd>
        </div>
      </dl>
      <p className="fine">{t('case.rule')}</p>
    </aside>
  );
}

export function ChatScreen() {
  const api = useApi();
  const { t } = useI18n();
  const { state, playback } = useChat();
  const demo = api.mode === 'demo';
  const logRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [showJump, setShowJump] = useState(false);
  const empty = state.items.length === 0;

  const scrollToEnd = () => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  };

  // Follows new text, but stops as soon as the reader scrolls up to read something earlier.
  const onScroll = () => {
    const log = logRef.current;
    if (!log) return;
    const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
    pinned.current = atEnd;
    setShowJump(!atEnd);
  };

  useLayoutEffect(() => {
    if (pinned.current) scrollToEnd();
  }, [state.items, state.identity]);

  const [announcement, setAnnouncement] = useState('');
  useEffect(() => {
    // Screen readers hear finished replies and tool steps, never each streamed word.
    const last = state.items[state.items.length - 1];
    const running = last?.kind === 'bot' ? last.tools.find((tool) => tool.status === 'running') : undefined;
    const spoken = running?.label ?? lastSpokenText(state.items);
    if (spoken) setAnnouncement(spoken);
  }, [state.items]);

  return (
    <div className="chat">
      <div className="chat__main">
        <div
          className="chat__log"
          ref={logRef}
          onScroll={onScroll}
          role="region"
          aria-label={t('chat.logLabel')}
          tabIndex={0}
        >
          <div className="chat__column">
            {empty ? (
              demo ? (
                <RecordingPicker />
              ) : (
                <Intro />
              )
            ) : (
              <>
                <h1 id="page-title" className="sr-only" tabIndex={-1}>
                  {t('chat.logLabel')}
                </h1>
                {state.items.map((item) => (
                  <ChatLine key={item.id} item={item} items={state.items} />
                ))}
              </>
            )}
            {identityOpen(state.identity) && (demo ? <RecordedIdentity /> : <IdentityPanel />)}
          </div>
        </div>
        {showJump && (
          <button
            type="button"
            className="jump"
            onClick={() => {
              pinned.current = true;
              setShowJump(false);
              scrollToEnd();
            }}
          >
            <Icon name="down" size={18} />
            {t('chat.jump')}
          </button>
        )}
        <div className="chat__dock">
          <div className="chat__column">
            {state.handoff && <HandoffBanner handoff={state.handoff} />}
            {demo ? playback.recording && <PlaybackBar /> : <Composer />}
          </div>
        </div>
      </div>
      <CaseFile />
      <p className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}
