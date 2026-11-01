import { useMemo, useState } from 'react';
import { flushSync } from 'react-dom';
import type { Citation, Handoff, Locale, Order, Policy, RefundSummary } from '../api/types';
import type { MessageKey } from '../i18n/en';
import { useI18n } from '../i18n/context';
import { formatMinutes } from '../i18n/translate';
import type { BotItem, ChatItem, NoticeItem, ToolActivity } from '../lib/chatState';
import { parseCitedText, splitParagraphs } from '../lib/citations';
import { formatDay, formatQar, formatTime } from '../lib/format';
import { ORDER_STEPS, orderPlace, orderStep } from '../lib/orders';
import { refundBodyKey } from '../lib/refunds';
import { Icon } from '../ui/Icon';
import { useChat } from './ChatProvider';

function ToolTrail({ tools }: { tools: ToolActivity[] }) {
  if (tools.length === 0) return null;
  return (
    <ol className="trail">
      {tools.map((tool) => (
        <li key={tool.id} className={`trail__stop is-${tool.status}`}>
          <span className="trail__mark" aria-hidden="true">
            {tool.status === 'ok' && <Icon name="check" size={12} />}
            {tool.status === 'error' && <Icon name="x" size={12} />}
          </span>
          {/* The label comes from the server, in plain language. */}
          <span dir="auto">{tool.label}</span>
        </li>
      ))}
    </ol>
  );
}

function CitedParagraph({
  text,
  known,
  streaming,
  citations,
  onCite,
}: {
  text: string;
  known: ReadonlySet<number>;
  streaming: boolean;
  citations: Citation[];
  onCite: (n: number) => void;
}) {
  const { t } = useI18n();
  const parts = parseCitedText(text, known, streaming);
  return (
    <p dir="auto">
      {parts.map((part, index) =>
        part.kind === 'text' ? (
          <span key={index}>{part.text}</span>
        ) : (
          <button
            key={index}
            type="button"
            className="cite"
            aria-label={t('chat.citeLabel', {
              n: part.n,
              title: citations.find((c) => c.n === part.n)?.title ?? '',
            })}
            onClick={() => onCite(part.n)}
          >
            {part.n}
          </button>
        ),
      )}
    </p>
  );
}

function Sources({
  messageId,
  citations,
  openSource,
  onOpen,
  locale,
}: {
  messageId: string;
  citations: Citation[];
  openSource: number | null;
  onOpen: (n: number | null) => void;
  locale: Locale;
}) {
  const { t } = useI18n();
  if (citations.length === 0) return null;
  return (
    <div className="sources">
      <h2 className="eyebrow">{t('chat.sources')}</h2>
      <ol>
        {citations.map((citation) => (
          <li key={citation.n}>
            <details
              id={`src-${messageId}-${citation.n}`}
              open={openSource === citation.n}
              onToggle={(event) => {
                const open = event.currentTarget.open;
                if (open && openSource !== citation.n) onOpen(citation.n);
                if (!open && openSource === citation.n) onOpen(null);
              }}
            >
              <summary>
                <span className="sources__n">{citation.n}</span>
                <span className="sources__title" dir="auto">
                  {citation.title}
                  <small>{citation.section}</small>
                </span>
              </summary>
              <blockquote dir="auto">{citation.excerpt}</blockquote>
              <p className="fine">
                {t('chat.sourceUpdated', { date: formatDay(citation.updatedAt, locale) })}
              </p>
            </details>
          </li>
        ))}
      </ol>
    </div>
  );
}

const STOPPED: Record<string, MessageKey> = {
  cancelled: 'stage.cancelled',
  failed_customer: 'stage.failed_customer',
};

export function OrderRoute({ status }: { status: string }) {
  const { t } = useI18n();
  const step = orderStep(status);
  const current = step ? ORDER_STEPS.indexOf(step) : -1;
  if (current === -1) return null;
  return (
    <ol className="route" aria-label={t('order.progress')}>
      {ORDER_STEPS.map((name, index) => {
        const state = index < current ? 'done' : index === current ? 'now' : 'next';
        return (
          <li key={name} className={`route__stop is-${state}`} aria-current={state === 'now' ? 'step' : undefined}>
            <span className="route__dot" aria-hidden="true" />
            <span className="route__label">{t(`stage.${name}`)}</span>
          </li>
        );
      })}
    </ol>
  );
}

function statusLabel(status: string, t: (key: MessageKey) => string): string {
  const stopped = STOPPED[status];
  if (stopped) return t(stopped);
  const step = orderStep(status);
  return step ? t(`stage.${step}`) : status;
}

export function OrderCard({ order }: { order: Order }) {
  const { t, locale } = useI18n();
  const arrived = order.deliveredAt;
  return (
    <article className="docket" aria-label={`${t('order.heading')} ${order.id}`}>
      <header className="docket__head">
        <p>
          <span className="eyebrow">{t('order.heading')}</span>
          <bdi className="mono docket__id">{order.id}</bdi>
        </p>
        <p className="tag">{statusLabel(order.status, t)}</p>
      </header>

      <div className="docket__where">
        <div>
          <p className="docket__store" dir="auto">
            {order.store}
          </p>
          <p className="muted" dir="auto">
            {orderPlace([order.area, order.rider && `${t('order.rider')} ${order.rider}`], locale)}
          </p>
        </div>
        {(arrived ?? order.etaAt) && (
          <p className="docket__time">
            <span className="eyebrow">{t(arrived ? 'order.deliveredAt' : 'order.eta')}</span>
            <bdi className="mono">{formatTime(arrived ?? order.etaAt ?? '', locale)}</bdi>
          </p>
        )}
      </div>

      <OrderRoute status={order.status} />

      <div className="docket__tear" aria-hidden="true" />

      <ul className="docket__items">
        {order.items.map((item) => (
          <li key={item.name}>
            <span className="docket__qty mono" aria-hidden="true">
              {item.qty}
            </span>
            <span className="docket__name" dir="auto">
              <span className="sr-only">{item.qty} </span>
              {item.name}
              {item.flag && (
                <span className="tag tag--bad">
                  <Icon name="alert" size={14} />
                  {t(item.flag === 'missing' ? 'flag.missing' : 'flag.wrong')}
                </span>
              )}
            </span>
            <bdi className="mono">{formatQar(item.qty * item.priceQar, locale)}</bdi>
          </li>
        ))}
      </ul>
      <dl className="docket__sum">
        <div>
          <dt>{t('order.fees')}</dt>
          <dd>
            <bdi className="mono">{formatQar(order.feesQar, locale)}</bdi>
          </dd>
        </div>
        <div className="docket__total">
          <dt>{t('order.total')}</dt>
          <dd>
            <bdi className="mono">{formatQar(order.totalQar, locale)}</bdi>
          </dd>
        </div>
      </dl>
    </article>
  );
}

function refundBody(refund: RefundSummary, policy: Policy | null, t: ReturnType<typeof useI18n>['t']) {
  const days = policy?.refund.cardBusinessDays;
  const minutes = policy?.refund.creditMinutes;
  // Timings are only stated when the backend supplied them.
  const timed = days != null && minutes != null;
  return t(refundBodyKey(refund, timed), timed ? { days, minutes } : undefined);
}

const REFUND_ICON = { pending: 'clock', approved: 'check', auto_approved: 'check', rejected: 'x' } as const;

export function RefundCard({ refund }: { refund: RefundSummary }) {
  const { t, locale } = useI18n();
  const { policy } = useChat();
  return (
    <article className={`refundslip is-${refund.status}`} aria-label={`${t('refund.heading')} ${refund.id}`}>
      <header>
        <p>
          <span className="eyebrow">{t('refund.heading')}</span>
          <bdi className="mono">{refund.id}</bdi>
        </p>
        <p className={`tag tag--${refund.status}`}>
          <Icon name={REFUND_ICON[refund.status]} size={14} />
          {t(`refund.status.${refund.status}`)}
        </p>
      </header>
      <p className="refundslip__amount">
        <bdi>{formatQar(refund.amountQar, locale)}</bdi>
      </p>
      <p>{refundBody(refund, policy, t)}</p>
      {refund.note && (
        <p className="refundslip__note" dir="auto">
          {refund.note}
        </p>
      )}
    </article>
  );
}

function BotMessage({ item }: { item: BotItem }) {
  const { t, locale } = useI18n();
  const { retry } = useChat();
  const [openSource, setOpenSource] = useState<number | null>(null);
  const known = useMemo(() => new Set(item.citations.map((c) => c.n)), [item.citations]);
  const streaming = item.status === 'streaming';
  const paragraphs = splitParagraphs(item.text);

  const openCitation = (n: number) => {
    flushSync(() => setOpenSource(n));
    document.getElementById(`src-${item.id}-${n}`)?.querySelector('summary')?.focus();
  };

  return (
    <article className="msg msg--bot" aria-label={t('chat.bot')}>
      <p className="msg__who">{t('chat.bot')}</p>
      <ToolTrail tools={item.tools} />
      {paragraphs.length > 0 && (
        <div className="msg__body">
          {paragraphs.map((paragraph, index) => (
            <CitedParagraph
              key={index}
              text={paragraph}
              known={known}
              streaming={streaming && index === paragraphs.length - 1}
              citations={item.citations}
              onCite={openCitation}
            />
          ))}
        </div>
      )}
      {streaming && item.tools.every((tool) => tool.status !== 'running') && (
        <p className="writing">
          <span className="sr-only">{t('chat.writing')}</span>
          <span className="writing__dot" aria-hidden="true" />
        </p>
      )}
      {item.orders.map((order) => (
        <OrderCard key={order.id} order={order} />
      ))}
      {item.refunds.map((refund) => (
        <RefundCard key={refund.id} refund={refund} />
      ))}
      <Sources
        messageId={item.id}
        citations={item.citations}
        openSource={openSource}
        onOpen={setOpenSource}
        locale={locale}
      />
      {item.status === 'stopped' && <p className="msg__state">{t('chat.stopped')}</p>}
      {item.status === 'failed' && (
        <div className="msg__state msg__state--bad" role="alert">
          <Icon name="alert" size={18} />
          <span>{item.errorMessage ?? t('chat.failed')}</span>
          {item.retryable && (
            <button type="button" className="link" onClick={retry}>
              {t('chat.retry')}
            </button>
          )}
        </div>
      )}
    </article>
  );
}

function noticeText(item: NoticeItem, refund: RefundSummary | undefined, t: ReturnType<typeof useI18n>['t']) {
  const name = item.agentName ?? '';
  switch (item.notice) {
    case 'handoff_queued':
      return t('notice.handoff_queued');
    case 'handoff_joined':
      return t('notice.handoff_joined', { name });
    case 'handoff_failed':
      return t('notice.handoff_failed');
    case 'closed':
      return t('notice.closed');
    case 'identity_verified':
      return t('notice.identity_verified');
    case 'identity_cancelled':
      return t('notice.identity_cancelled');
    case 'refund_decided':
      return t(refund?.status === 'rejected' ? 'notice.refund_rejected' : 'notice.refund_approved', { name });
  }
}

export function ChatLine({ item, items }: { item: ChatItem; items: ChatItem[] }) {
  const { t } = useI18n();
  switch (item.kind) {
    case 'customer':
      return (
        <div className="msg msg--customer">
          <p dir="auto">
            <span className="sr-only">{t('chat.you')}: </span>
            {item.text}
          </p>
        </div>
      );
    case 'agent':
      return (
        <article className="msg msg--agent" aria-label={item.agentName}>
          <p className="msg__who">
            <Icon name="person" size={18} />
            <span dir="auto">{item.agentName}</span>
            <span className="tag tag--person">{t('chat.humanTag')}</span>
          </p>
          <p dir="auto">{item.text}</p>
        </article>
      );
    case 'notice': {
      const refund = items
        .flatMap((other) => (other.kind === 'bot' ? other.refunds : []))
        .find((r) => r.id === item.refundId);
      return (
        <p className="notice" role={item.notice === 'handoff_failed' ? 'alert' : undefined}>
          {noticeText(item, refund, t)}
        </p>
      );
    }
    case 'bot':
      return <BotMessage item={item} />;
  }
}

export function HandoffBanner({ handoff }: { handoff: Handoff }) {
  const { t, locale } = useI18n();
  if (handoff.status === 'closed') return null;
  const joined = handoff.status === 'joined';
  const title = joined
    ? t('handoff.joined', { name: handoff.agentName ?? '' })
    : t(handoff.status === 'queued' ? 'handoff.queued' : 'handoff.requested');
  const queued =
    handoff.status === 'queued' && handoff.etaMinutes !== null && handoff.position !== null;
  return (
    <div className={joined ? 'handoff is-joined' : 'handoff'}>
      <Icon name={joined ? 'person' : 'clock'} />
      <div>
        <p className="handoff__title">{title}</p>
        {joined && <p>{t('handoff.joinedDetail')}</p>}
        {queued && (
          <p>
            {t('handoff.queuedDetail', {
              wait: formatMinutes(locale, handoff.etaMinutes ?? 0),
              position: handoff.position ?? 0,
            })}
          </p>
        )}
      </div>
    </div>
  );
}
