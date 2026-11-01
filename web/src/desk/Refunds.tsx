import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useApi } from '../App';
import { ApiError, type DeskPolicy, type Refund, type RefundDecision } from '../api/types';
import { useI18n } from '../i18n/context';
import { formatDateTime, formatQar, formatTime } from '../lib/format';
import { checkDecision, decidedOnly, MIN_REJECT_NOTE, nextFocusAfter, sortQueue } from '../lib/refunds';
import { Icon } from '../ui/Icon';
import { useDesk } from './Desk';

type Action = RefundDecision['action'];

function DecisionDialog({
  refund,
  action,
  onClose,
  onDone,
}: {
  refund: Refund;
  action: Action;
  onClose: () => void;
  onDone: (refund: Refund) => void;
}) {
  const api = useApi();
  const { t, locale } = useI18n();
  const { reloadRefunds, handleAuth } = useDesk();
  const ref = useRef<HTMLDialogElement>(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const approving = action === 'approve';

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (checkDecision(action, note) === 'note_required') {
      setError(t('dialog.noteError', { n: MIN_REJECT_NOTE }));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onDone(await api.decideRefund(refund.id, { action, note, version: refund.version }));
    } catch (caught) {
      if (handleAuth(caught)) return;
      if (caught instanceof ApiError && caught.code === 'refund_already_decided') {
        setError(t('dialog.conflict'));
        await reloadRefunds();
      } else {
        setError(caught instanceof ApiError ? caught.message : t('desk.error'));
      }
      setBusy(false);
    }
  };

  return (
    <dialog ref={ref} className="dialog" aria-labelledby="decision-title" onClose={onClose}>
      <form onSubmit={(event) => void submit(event)} noValidate>
        <h2 id="decision-title">{t(approving ? 'dialog.approveTitle' : 'dialog.rejectTitle')}</h2>
        <p>
          {t('dialog.summary', {
            amount: formatQar(refund.amountQar, locale),
            customer: refund.customer,
            order: refund.orderId,
          })}
        </p>
        <label className="field">
          <span className="field__label">
            {t(approving ? 'dialog.noteOptional' : 'dialog.noteRequired')}
          </span>
          <textarea
            className="field__input"
            dir="auto"
            rows={3}
            value={note}
            required={!approving}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'decision-error' : undefined}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        {error && (
          <p className="field__error" id="decision-error" role="alert">
            <Icon name="alert" size={18} />
            <span>{error}</span>
          </p>
        )}
        <div className="dialog__actions">
          <button type="button" className="btn" onClick={() => ref.current?.close()}>
            {t('dialog.cancel')}
          </button>
          <button
            type="submit"
            className={approving ? 'btn btn--primary' : 'btn btn--danger'}
            disabled={busy}
          >
            {t(approving ? 'dialog.confirmApprove' : 'dialog.confirmReject')}
          </button>
        </div>
      </form>
    </dialog>
  );
}

function Docket({ refund, onDecide }: { refund: Refund; onDecide: (refund: Refund, action: Action) => void }) {
  const { t, locale } = useI18n();
  return (
    <li className="ticket">
      <div className="ticket__main">
        <p className="ticket__ref">
          <bdi className="mono">{refund.id}</bdi>
          <span className="tag">{t(`queue.reason.${refund.reason}`)}</span>
          <span className={`tag tag--suggest-${refund.recommendation}`}>
            {t(`queue.suggest.${refund.recommendation}`)}
          </span>
        </p>
        <h2 id={`refund-${refund.id}`} tabIndex={-1} dir="auto">
          {refund.customer}, <span className="ticket__store">{refund.store}</span>
        </h2>
        <p className="ticket__summary">{refund.summary}</p>
        {refund.risks.length > 0 && (
          <ul className="ticket__risks" aria-label={t('queue.flags')}>
            {refund.risks.map((risk) => (
              <li key={risk} className="tag tag--bad">
                <Icon name="flag" size={14} />
                {risk}
              </li>
            ))}
          </ul>
        )}
        <div className="ticket__facts">
          {refund.evidence.length > 0 && (
            <div>
              <h3 className="eyebrow">{t('queue.checked')}</h3>
              <dl>
                {refund.evidence.map((item) => (
                  <div key={item.label}>
                    <dt>{item.label}</dt>
                    <dd>
                      {item.simulated && <span className="tag">{t('queue.simulated')}</span>} {item.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
          <div>
            <h3 className="eyebrow">{t('queue.policy')}</h3>
            <p>{refund.policy.title}</p>
            <p className="muted">{refund.policy.section}</p>
          </div>
        </div>
      </div>
      <div className="ticket__side">
        <p className="ticket__amount">
          <bdi>{formatQar(refund.amountQar, locale)}</bdi>
        </p>
        <p className="muted">
          <bdi className="mono">{refund.orderId}</bdi>
        </p>
        <p className="muted">{t('queue.requested', { time: formatTime(refund.requestedAt, locale) })}</p>
        {refund.canDecide ? (
          <div className="ticket__actions">
            <button type="button" className="btn btn--primary" onClick={() => onDecide(refund, 'approve')}>
              <Icon name="check" size={18} />
              {t('queue.approve', { amount: formatQar(refund.amountQar, locale) })}
            </button>
            <button type="button" className="btn" onClick={() => onDecide(refund, 'reject')}>
              {t('queue.reject')}
            </button>
          </div>
        ) : (
          // The backend decides who may act. The UI only reports it.
          <p className="ticket__role">
            <Icon name="shield" size={18} />
            <span>{t('queue.needsRole', { role: t(`role.${refund.requiredRole}`) })}</span>
          </p>
        )}
      </div>
    </li>
  );
}

export function RefundsSection() {
  const { t, locale } = useI18n();
  const { refunds, putRefund } = useDesk();
  const api = useApi();
  const [policy, setPolicy] = useState<DeskPolicy | null>(null);
  const [deciding, setDeciding] = useState<{ refund: Refund; action: Action } | null>(null);
  const [status, setStatus] = useState('');
  const [focusNext, setFocusNext] = useState<string | null>(null);

  const queue = useMemo(() => sortQueue(refunds), [refunds]);
  const decided = useMemo(() => decidedOnly(refunds), [refunds]);

  useEffect(() => {
    if (!focusNext) return;
    document.getElementById(focusNext)?.focus();
    setFocusNext(null);
  }, [focusNext, queue]);

  useEffect(() => {
    let active = true;
    void api.getDeskPolicy().then((value) => {
      if (active) setPolicy(value);
    });
    return () => {
      active = false;
    };
  }, [api]);

  const limit = policy?.refund.automatedLimitQar;
  const newLimit = policy?.refund.newAccountAutomatedLimitQar;

  const done = (refund: Refund) => {
    const next = nextFocusAfter(queue, refund.id);
    putRefund(refund);
    setDeciding(null);
    setStatus(t(refund.status === 'approved' ? 'queue.doneApproved' : 'queue.doneRejected', { id: refund.id }));
    // The button that opened the dialog is gone, so focus moves to the next refund.
    setFocusNext(next ? `refund-${next}` : 'page-title');
  };

  return (
    <div className="refunds">
      <p className="section-intro">
        {limit != null && newLimit != null
          ? t('queue.intro', { limit: formatQar(limit, locale), newLimit: formatQar(newLimit, locale) })
          : t('queue.introPlain')}
      </p>
      <p className="toast" role="status">
        {status}
      </p>
      {queue.length === 0 ? (
        <p className="empty">{t('queue.empty')}</p>
      ) : (
        <ol className="tickets">
          {queue.map((refund) => (
            <Docket key={refund.id} refund={refund} onDecide={(r, action) => setDeciding({ refund: r, action })} />
          ))}
        </ol>
      )}
      <section className="decided" aria-labelledby="decided-title">
        <h2 id="decided-title" className="section-title">
          {t('queue.decided')}
        </h2>
        {decided.length === 0 ? (
          <p className="muted">{t('queue.noneDecided')}</p>
        ) : (
          <ul>
            {decided.map((refund) => (
              <li key={refund.id}>
                <span className={`stamp stamp--${refund.status}`}>{t(`stamp.${refund.status}`)}</span>
                <span className="decided__main">
                  <strong>
                    <bdi className="mono">{refund.id}</bdi> <span dir="auto">{refund.customer}</span>
                  </strong>
                  {refund.note && (
                    <span className="muted" dir="auto">
                      {refund.note}
                    </span>
                  )}
                </span>
                <bdi className="mono decided__amount">{formatQar(refund.amountQar, locale)}</bdi>
                <span className="muted decided__by">
                  {t('queue.by', {
                    name: refund.decidedBy ?? '',
                    time: refund.decidedAt ? formatDateTime(refund.decidedAt, locale) : '',
                  })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {deciding && (
        <DecisionDialog
          key={`${deciding.refund.id}-${deciding.action}`}
          refund={deciding.refund}
          action={deciding.action}
          onClose={() => setDeciding(null)}
          onDone={done}
        />
      )}
    </div>
  );
}
