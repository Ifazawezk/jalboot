import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError } from '../api/types';
import { useI18n } from '../i18n/context';
import { forceLtr, formatClock } from '../lib/format';
import { normalizeCode, normalizePhone } from '../lib/identity';
import { Icon } from '../ui/Icon';
import { useNow } from '../ui/hooks';
import { useChat } from './ChatProvider';

function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <section className="identity" aria-labelledby="identity-title">
      <h2 id="identity-title" className="identity__title">
        <Icon name="shield" />
        {t('identity.heading')}
      </h2>
      {children}
    </section>
  );
}

function ResendButton({ availableAt, busy, onResend }: { availableAt: number; busy: boolean; onResend: () => void }) {
  const { t } = useI18n();
  const now = useNow(1000);
  const left = Math.ceil((availableAt - now) / 1000);
  if (left > 0) {
    return <span className="identity__wait">{t('identity.resendIn', { clock: formatClock(left) })}</span>;
  }
  return (
    <button type="button" className="link" onClick={onResend} disabled={busy}>
      {t('identity.resend')}
    </button>
  );
}

/**
 * The phone number and the code live in this component's own state and leave it only through
 * the verify calls. Neither touches chat state, so neither can reach the conversation.
 */
export function IdentityPanel() {
  const { state, startVerification, confirmVerification, cancelVerification, changeNumber } = useChat();
  const { t } = useI18n();
  const phase = state.identity;

  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [simulatedCode, setSimulatedCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attemptsLeft, setAttemptsLeft] = useState<number | null>(null);
  const [locked, setLocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resendAt, setResendAt] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [phase]);

  const showError = (caught: unknown) => {
    if (caught instanceof ApiError) {
      setError(caught.message);
      setAttemptsLeft(caught.attemptsLeft);
      if (caught.code === 'too_many_attempts') setLocked(true);
    } else {
      setError(t('chat.networkError'));
    }
  };

  const sendCode = async (normalized: string) => {
    setBusy(true);
    setError(null);
    setAttemptsLeft(null);
    try {
      const result = await startVerification(normalized);
      setSimulatedCode(result.simulatedCode ?? null);
      setResendAt(Date.now() + result.resendInSeconds * 1000);
    } catch (caught) {
      showError(caught);
    } finally {
      setBusy(false);
    }
  };

  const submitPhone = (event: FormEvent) => {
    event.preventDefault();
    const normalized = normalizePhone(phone);
    if (!normalized) {
      setError(t('identity.phoneInvalid'));
      return;
    }
    void sendCode(normalized);
  };

  const submitCode = async (event: FormEvent) => {
    event.preventDefault();
    const digits = normalizeCode(code);
    if (!digits) {
      setError(t('identity.codeEmpty'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await confirmVerification(digits);
    } catch (caught) {
      setCode('');
      showError(caught);
    } finally {
      setBusy(false);
    }
  };

  const useDifferentNumber = () => {
    setCode('');
    setSimulatedCode(null);
    setError(null);
    setAttemptsLeft(null);
    changeNumber();
  };

  const errorBlock = error && (
    <p className="field__error" id="identity-error" role="alert">
      <Icon name="alert" size={18} />
      <span>
        {error}
        {attemptsLeft !== null && ` ${t('identity.attemptsLeft', { n: attemptsLeft })}`}
      </span>
    </p>
  );

  if (phase === 'phone') {
    return (
      <Shell>
        <p className="identity__why">{t('identity.why')}</p>
        <form onSubmit={submitPhone} noValidate>
          <label className="field">
            <span className="field__label">{t('identity.phoneLabel')}</span>
            <input
              ref={inputRef}
              className="field__input field__input--ltr"
              type="tel"
              dir="ltr"
              inputMode="tel"
              autoComplete="tel-national"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? 'identity-error' : 'identity-phone-help'}
            />
            <span className="field__help" id="identity-phone-help">
              {t('identity.phoneHelp')}
            </span>
          </label>
          {errorBlock}
          <div className="identity__actions">
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {t('identity.sendCode')}
            </button>
            <button type="button" className="btn" onClick={cancelVerification}>
              {t('identity.cancel')}
            </button>
          </div>
        </form>
        <p className="fine">{t('identity.outsideChat')}</p>
      </Shell>
    );
  }

  return (
    <Shell>
      {simulatedCode && (
        <aside className="simsms" aria-label={t('identity.simTitle')}>
          <p className="simsms__title">{t('identity.simTitle')}</p>
          <p className="simsms__message">{t('identity.simMessage', { code: simulatedCode })}</p>
          <p className="simsms__note">{t('identity.simBody')}</p>
        </aside>
      )}
      <form onSubmit={(event) => void submitCode(event)} noValidate>
        <label className="field">
          <span className="field__label">{t('identity.codeSentTo', { phone: forceLtr(state.maskedPhone ?? '') })}</span>
          <input
            ref={inputRef}
            className="field__input field__input--ltr field__input--code"
            type="text"
            dir="ltr"
            inputMode="numeric"
            autoComplete="one-time-code"
            spellCheck={false}
            aria-label={t('identity.codeLabel')}
            value={code}
            disabled={locked}
            onChange={(event) => setCode(event.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'identity-error' : undefined}
          />
        </label>
        {errorBlock}
        <div className="identity__actions">
          <button type="submit" className="btn btn--primary" disabled={busy || locked}>
            {t('identity.confirm')}
          </button>
          <button type="button" className="btn" onClick={cancelVerification}>
            {t('identity.cancel')}
          </button>
        </div>
      </form>
      {!locked && (
        <p className="identity__links">
          <button type="button" className="link" onClick={useDifferentNumber}>
            {t('identity.changeNumber')}
          </button>
          <ResendButton
            availableAt={resendAt}
            busy={busy}
            onResend={() => {
              const normalized = normalizePhone(phone);
              if (normalized) void sendCode(normalized);
            }}
          />
        </p>
      )}
    </Shell>
  );
}

/** What a recording shows instead of the forms. It holds no number and no code. */
export function RecordedIdentity() {
  const { state } = useChat();
  const { t } = useI18n();
  return (
    <Shell>
      <p className="identity__why">
        {state.maskedPhone
          ? t('identity.recordedCode', { phone: forceLtr(state.maskedPhone) })
          : t('identity.recordedPhone')}
      </p>
    </Shell>
  );
}
