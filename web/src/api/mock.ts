import type { SupportApi, Unsubscribe } from './client';
import {
  ApiError,
  type ApiMode,
  type AuditEntry,
  type AuditFilter,
  type Conversation,
  type ConversationDetail,
  type ConversationEvent,
  type DeskAgent,
  type DeskEvent,
  type DeskSummary,
  type Handoff,
  type LiveConversation,
  type Locale,
  type Order,
  type QualityReport,
  type Refund,
  type RefundDecision,
  type RefundSummary,
  type SendMessageInput,
  type StreamEvent,
  type TopIssue,
  type TranscriptEntry,
  type WindowDays,
} from './types';
import {
  AUDIT_SEEDS,
  CONVERSATIONS,
  QUALITY_BASE,
  REFUND_SEEDS,
  issuesFor,
  trendFor,
  type RawAudit,
  type RawConversation,
  type RawEntry,
  type RawRefund,
} from '../data/desk';
import { MOCK_DESK_POLICY, MOCK_POLICY, MOCK_RULES } from '../data/mockRules';
import { recordingsFor } from '../data/recordings';
import {
  AGENT_NOOR,
  expandScenario,
  refusedTurn,
  scenarioFor,
  type Scenario,
} from '../data/scenarios';
import { pick, type L } from '../data/text';
import { classifyIntent } from '../lib/intent';
import { applyDecision } from '../lib/refunds';

export interface MockOptions {
  mode?: Extract<ApiMode, 'mock' | 'demo'>;
  /** Multiplies every delay. Tests pass 0. */
  speed?: number;
  now?: () => number;
  /** Scripted arrivals on the live desk. Tests turn this off. */
  liveTicks?: boolean;
  /** Tests pass a fixed code. */
  makeCode?: () => string;
}

const PAGE_SIZE = 10;
const CODE_LIFETIME_SECONDS = 300;
const RESEND_SECONDS = 30;
const BOT_NAME: L = { en: 'Automated support', ar: 'الدعم الآلي' };
const SYSTEM_NAME: L = { en: 'System', ar: 'النظام' };

interface StoredEntry extends Omit<RawEntry, 'minutesAgo'> {
  at: number;
}

/** Conversation with times stored as epoch milliseconds. */
interface StoredConversation extends Omit<RawConversation, 'transcript'> {
  startedAt: number;
  updatedAt: number;
  waitingSince: number | null;
  transcript: StoredEntry[];
}

interface StoredRefund extends Omit<RawRefund, 'requestedMinutesAgo' | 'decidedMinutesAgo'> {
  requestedAt: number;
  decidedAt: number | null;
  version: number;
}

interface StoredAudit extends Omit<RawAudit, 'minutesAgo'> {
  at: number;
}

interface PendingCode {
  code: string;
  expiresAt: number;
}

interface IdentityRecord {
  pending: PendingCode | null;
  failures: number;
  lockedUntil: number;
}

type TurnState = 'held' | 'done' | 'failed';

const iso = (ms: number) => new Date(ms).toISOString();
const same = (text: string): L => ({ en: text, ar: text });

function randomCode(): string {
  return String(Math.floor(100_000 + Math.random() * 900_000));
}

export function createMockApi(options: MockOptions = {}): SupportApi {
  const mode = options.mode ?? 'mock';
  const speed = options.speed ?? 1;
  const now = options.now ?? Date.now;
  const liveTicks = options.liveTicks ?? true;
  const makeCode = options.makeCode ?? randomCode;
  const minute = (n: number) => now() - n * 60_000;

  let locale: Locale = 'en';
  let idCounter = 0;
  let refundCounter = 3000;
  let resolvedToday = 86;
  let signedIn = true;
  const nextId = (prefix: string) => {
    idCounter += 1;
    return `${prefix}-${idCounter}`;
  };

  const conversations = new Map<string, StoredConversation>(
    CONVERSATIONS.map((c) => [
      c.id,
      {
        ...c,
        startedAt: minute(c.startedMinutesAgo),
        updatedAt: minute(c.updatedMinutesAgo),
        waitingSince: c.waitingMinutes === null ? null : minute(c.waitingMinutes),
        transcript: c.transcript.map(({ minutesAgo, ...rest }) => ({ ...rest, at: minute(minutesAgo) })),
      },
    ]),
  );
  const refunds = new Map<string, StoredRefund>(
    REFUND_SEEDS.map((r) => [
      r.id,
      {
        ...r,
        requestedAt: minute(r.requestedMinutesAgo),
        decidedAt: r.decidedMinutesAgo === null ? null : minute(r.decidedMinutesAgo),
        version: 1,
      },
    ]),
  );
  const auditLog: StoredAudit[] = AUDIT_SEEDS.map(({ minutesAgo, ...rest }) => ({
    ...rest,
    at: minute(minutesAgo),
  }));

  const identities = new Map<string, IdentityRecord>();
  const turns = new Map<string, TurnState>();
  const conversationSubs = new Map<string, Set<(e: ConversationEvent) => void>>();
  const deskSubs = new Set<(e: DeskEvent) => void>();
  const joinTimers = new Map<string, ReturnType<typeof setTimeout>>();
  let tickTimers: ReturnType<typeof setTimeout>[] = [];

  const wait = (ms: number, signal?: AbortSignal) =>
    new Promise<void>((resolve, reject) => {
      if (signal?.aborted) {
        reject(new DOMException('Aborted', 'AbortError'));
        return;
      }
      const onAbort = () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      };
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', onAbort);
        resolve();
      }, ms * speed);
      signal?.addEventListener('abort', onAbort, { once: true });
    });

  const later = (ms: number, run: () => void) => setTimeout(run, ms * speed);

  const viewEntry = (e: StoredEntry): TranscriptEntry => ({
    id: e.id,
    at: iso(e.at),
    author: e.author,
    name: e.name ? pick(e.name, locale) : null,
    text: e.text,
    tools: e.tools.map((tool) => pick(tool, locale)),
    sources: e.sources.map((s) => pick(s, locale)),
  });

  const viewConversation = (c: StoredConversation): LiveConversation => ({
    id: c.id,
    customer: pick(c.customer, locale),
    locale: c.locale,
    state: c.state,
    priority: c.priority,
    verified: c.verified,
    summary: pick(c.summary, locale),
    orderId: c.orderId,
    agentName: c.agentName ? pick(c.agentName, locale) : null,
    startedAt: iso(c.startedAt),
    updatedAt: iso(c.updatedAt),
    waitingSince: c.waitingSince === null ? null : iso(c.waitingSince),
  });

  const viewRefund = (r: StoredRefund): Refund => {
    const withinAgentLimit = r.amountQar <= MOCK_RULES.refundAgentLimitQar;
    return {
      id: r.id,
      orderId: r.orderId,
      amountQar: r.amountQar,
      status: r.status,
      decidedBy: r.decidedBy ? pick(r.decidedBy, locale) : null,
      note: r.note ? pick(r.note, locale) : null,
      conversationId: r.conversationId,
      customer: pick(r.customer, locale),
      store: pick(r.store, locale),
      reason: r.reason,
      summary: pick(r.summary, locale),
      requestedAt: iso(r.requestedAt),
      decidedAt: r.decidedAt === null ? null : iso(r.decidedAt),
      recommendation: r.recommendation,
      evidence: r.evidence.map((e) => ({ label: pick(e.label, locale), value: pick(e.value, locale) })),
      policy: { title: pick(r.policy.title, locale), section: pick(r.policy.section, locale) },
      risks: r.risks.map((risk) => pick(risk, locale)),
      version: r.version,
      canDecide: withinAgentLimit,
      requiredRole: withinAgentLimit ? 'agent' : 'supervisor',
    };
  };

  const viewAudit = (a: StoredAudit): AuditEntry => ({
    id: a.id,
    at: iso(a.at),
    actorKind: a.actorKind,
    actorName: pick(a.actorName, locale),
    action: a.action,
    target: a.target,
    detail: pick(a.detail, locale),
  });

  const summary = (): DeskSummary => {
    const open = [...conversations.values()].filter((c) => c.state !== 'closed');
    return {
      live: open.length,
      waiting: open.filter((c) => c.state === 'waiting').length,
      refundsPending: [...refunds.values()].filter((r) => r.status === 'pending').length,
      resolvedToday,
    };
  };

  const deskAgent = (): DeskAgent => ({
    id: 'agent-noor',
    name: pick(AGENT_NOOR, locale),
    role: 'agent',
  });

  const emitDesk = (event: DeskEvent) => {
    for (const listener of deskSubs) listener(event);
  };
  const emitConversation = (id: string, event: ConversationEvent) => {
    for (const listener of conversationSubs.get(id) ?? []) listener(event);
  };
  const emitSummary = () => emitDesk({ type: 'summary.updated', summary: summary() });
  const touch = (c: StoredConversation) => {
    c.updatedAt = now();
    emitDesk({ type: 'conversation.updated', conversation: viewConversation(c) });
    emitSummary();
  };

  const addAudit = (entry: Omit<StoredAudit, 'id' | 'at'>) => {
    const stored: StoredAudit = { ...entry, id: nextId('au'), at: now() };
    auditLog.unshift(stored);
    emitDesk({ type: 'audit.appended', entry: viewAudit(stored) });
  };

  const addEntry = (c: StoredConversation, entry: Omit<StoredEntry, 'id' | 'at'>) => {
    const stored: StoredEntry = { ...entry, id: nextId('msg'), at: now() };
    c.transcript.push(stored);
    emitDesk({ type: 'conversation.message', conversationId: c.id, entry: viewEntry(stored) });
    return stored;
  };

  const need = <T,>(value: T | undefined, what: string): T => {
    if (value === undefined) {
      throw new ApiError(404, { code: 'not_found', message: `${what} not found`, retryable: false });
    }
    return value;
  };

  const joinAgent = (c: StoredConversation, agent: L) => {
    const pending = joinTimers.get(c.id);
    if (pending) clearTimeout(pending);
    joinTimers.delete(c.id);
    c.state = 'agent';
    c.agentName = agent;
    c.waitingSince = null;
    const handoff: Handoff = {
      status: 'joined',
      agentName: pick(agent, c.locale),
      etaMinutes: null,
      position: null,
    };
    emitConversation(c.id, { type: 'handoff.update', handoff });
    addAudit({
      actorKind: 'agent',
      actorName: agent,
      action: 'handoff.joined',
      target: c.id,
      detail: { en: 'Took over from automated support', ar: 'تولى المحادثة من الدعم الآلي' },
    });
    touch(c);
  };

  const agentSays = (c: StoredConversation, agent: L, text: string) => {
    const stored = addEntry(c, { author: 'agent', name: agent, text, tools: [], sources: [] });
    emitConversation(c.id, {
      type: 'agent.message',
      messageId: stored.id,
      agentName: pick(agent, c.locale),
      text,
      at: iso(stored.at),
    });
    touch(c);
  };

  const enterQueue = (c: StoredConversation, joins: Scenario['personJoins']) => {
    c.state = 'waiting';
    c.waitingSince = now();
    addAudit({
      actorKind: 'bot',
      actorName: BOT_NAME,
      action: 'handoff.requested',
      target: c.id,
      detail: { en: 'The customer needs a person', ar: 'يحتاج العميل إلى موظف' },
    });
    touch(c);
    if (!joins) return;
    // A simulated colleague picks it up unless someone takes it on the desk first.
    joinTimers.set(
      c.id,
      later(3200, () => {
        joinAgent(c, joins.name);
        later(900, () => agentSays(c, joins.name, pick(joins.text, c.locale)));
      }),
    );
  };

  const fileRefund = (c: StoredConversation, refund: RefundSummary, order: Order | null) => {
    const stored: StoredRefund = {
      id: refund.id,
      orderId: refund.orderId,
      conversationId: c.id,
      customer: c.customer,
      store: same(order?.store ?? ''),
      amountQar: refund.amountQar,
      status: refund.status,
      reason: 'missing_item',
      summary: {
        en: 'Khalas dates missing. The store scanned one of two bags, which fits the report.',
        ar: 'تمر الخلاص ناقص. مسح المتجر كيسًا واحدًا من كيسين، وهذا يتفق مع البلاغ.',
      },
      requestedAt: now(),
      decidedAt: null,
      decidedBy: null,
      note: null,
      recommendation: 'approve',
      evidence: [
        {
          label: { en: 'Order value', ar: 'قيمة الطلب' },
          value: {
            en: `QAR ${(order?.totalQar ?? 0).toFixed(2)}`,
            ar: `${(order?.totalQar ?? 0).toFixed(2)} ر.ق`,
          },
        },
        {
          label: { en: 'Store record', ar: 'سجل المتجر' },
          value: { en: 'One of two bags scanned', ar: 'مسح كيس واحد من كيسين' },
        },
      ],
      policy: {
        title: { en: 'Refunds and credits', ar: 'الاسترداد والرصيد' },
        section: {
          en: 'REF-05, Approval limits and repeat claims',
          ar: 'REF-05، حدود الموافقة والمطالبات المتكررة',
        },
      },
      risks: [],
      version: 1,
    };
    refunds.set(stored.id, stored);
    emitDesk({ type: 'refund.created', refund: viewRefund(stored) });
    addAudit({
      actorKind: 'bot',
      actorName: BOT_NAME,
      action: 'refund.proposed',
      target: stored.id,
      detail: {
        en: `QAR ${stored.amountQar.toFixed(2)} for order ${stored.orderId}`,
        ar: `${stored.amountQar.toFixed(2)} ريالًا للطلب ${stored.orderId}`,
      },
    });
    emitSummary();
  };

  const startTicks = () => {
    if (!liveTicks || tickTimers.length > 0) return;
    const started = now();
    const newcomer: StoredConversation = {
      id: 'cv-1049',
      customer: { en: 'Layla', ar: 'ليلى' },
      locale: 'ar',
      state: 'bot',
      priority: 'normal',
      verified: false,
      summary: { en: 'Wants to change the delivery address', ar: 'تريد تغيير عنوان التوصيل' },
      orderId: null,
      agentName: null,
      startedMinutesAgo: 0,
      updatedMinutesAgo: 0,
      waitingMinutes: null,
      startedAt: started,
      updatedAt: started,
      waitingSince: null,
      transcript: [],
    };
    tickTimers = [
      setTimeout(() => {
        conversations.set(newcomer.id, newcomer);
        addEntry(newcomer, {
          author: 'customer',
          name: null,
          text: 'هل يمكنني تغيير عنوان التوصيل؟ كتبت رقم البرج خطأ.',
          tools: [],
          sources: [],
        });
        touch(newcomer);
      }, 7_000),
      setTimeout(() => {
        addEntry(newcomer, {
          author: 'bot',
          name: null,
          text: 'يمكنني مساعدتك في ذلك، لكن عليّ أولًا التأكد من هويتك.',
          tools: [],
          sources: [],
        });
        touch(newcomer);
      }, 11_000),
      setTimeout(() => {
        resolvedToday += 1;
        emitSummary();
      }, 16_000),
    ];
  };

  const identityOf = (id: string): IdentityRecord => {
    const record = identities.get(id) ?? { pending: null, failures: 0, lockedUntil: 0 };
    identities.set(id, record);
    return record;
  };

  const tooManyAttempts = (record: IdentityRecord) =>
    new ApiError(429, {
      code: 'too_many_attempts',
      message:
        locale === 'ar'
          ? 'محاولات كثيرة جدًا. حاول مرة أخرى لاحقًا أو تحدث مع موظف.'
          : 'Too many attempts. Try again later or talk to a person.',
      retryable: false,
      retryAfterSeconds: Math.ceil((record.lockedUntil - now()) / 1000),
    });

  return {
    mode,

    setLocale(next) {
      locale = next;
    },

    async getDeskPolicy() {
      return MOCK_DESK_POLICY;
    },
    async getPolicy() {
      return MOCK_POLICY;
    },

    ...(mode === 'demo' ? { listRecordings: recordingsFor } : {}),

    async createConversation(chosen) {
      const id = nextId('cv');
      const started = now();
      conversations.set(id, {
        id,
        customer: { en: 'Sara', ar: 'سارة' },
        locale: chosen,
        state: 'bot',
        priority: 'normal',
        verified: false,
        summary: { en: 'New conversation from this browser', ar: 'محادثة جديدة من هذا المتصفح' },
        orderId: null,
        agentName: null,
        startedMinutesAgo: 0,
        updatedMinutesAgo: 0,
        waitingMinutes: null,
        startedAt: started,
        updatedAt: started,
        waitingSince: null,
        transcript: [],
      });
      const conversation: Conversation = {
        id,
        token: `mock-${id}`,
        locale: chosen,
        createdAt: iso(started),
        verified: false,
      };
      touch(need(conversations.get(id), 'Conversation'));
      return conversation;
    },

    async *sendMessage(conversationId, input: SendMessageInput, signal): AsyncGenerator<StreamEvent> {
      const c = need(conversations.get(conversationId), 'Conversation');
      if (c.state === 'closed') {
        throw new ApiError(409, {
          code: 'conversation_closed',
          message: 'This conversation has ended.',
          retryable: false,
        });
      }
      c.locale = input.locale;

      const earlier = turns.get(input.clientMessageId);
      if (earlier === 'done') {
        throw new ApiError(409, {
          code: 'duplicate_message',
          message: 'This message was already answered.',
          retryable: false,
        });
      }
      if (!earlier) {
        addEntry(c, { author: 'customer', name: null, text: input.text, tools: [], sources: [] });
        touch(c);
      }
      turns.set(input.clientMessageId, 'failed');

      // Once a person has the conversation, automated replies stop.
      if (c.state === 'agent' || c.state === 'waiting') {
        turns.set(input.clientMessageId, 'done');
        yield { type: 'message.end', finish: 'forwarded' };
        return;
      }

      const intent = classifyIntent(input.text);
      const scenario = scenarioFor(intent);

      // Order tools stay refused until the conversation is verified.
      if (scenario.needsIdentity && !c.verified) {
        for (const { waitMs, event } of refusedTurn({ locale: input.locale, messageId: nextId('reply') })) {
          await wait(waitMs, signal);
          yield event;
        }
        turns.set(input.clientMessageId, 'held');
        return;
      }

      const events = expandScenario(scenario, {
        locale: input.locale,
        nowMs: now(),
        messageId: nextId('reply'),
        nextRefundId: () => {
          refundCounter += 1;
          return `RF-${refundCounter}`;
        },
      });

      if (intent === 'override') {
        addAudit({
          actorKind: 'bot',
          actorName: BOT_NAME,
          action: 'guardrail.blocked',
          target: c.id,
          detail: {
            en: 'A message told the system to ignore its rules. Nothing was changed.',
            ar: 'طلبت رسالة تجاهل القواعد. لم يتغير شيء.',
          },
        });
      }

      let text = '';
      let order: Order | null = null;
      const tools: L[] = [];
      const sources: L[] = [];

      for (const { waitMs, event } of events) {
        await wait(waitMs, signal);
        switch (event.type) {
          case 'tool.start':
            addAudit({
              actorKind: 'bot',
              actorName: BOT_NAME,
              action: 'tool.called',
              target: c.id,
              detail: same(event.label),
            });
            break;
          case 'tool.end':
            if (event.label) tools.push(same(event.label));
            break;
          case 'order.card':
            order = event.order;
            c.orderId = event.order.id;
            break;
          case 'citation':
            sources.push(same(event.citation.title));
            break;
          case 'refund.update':
            fileRefund(c, event.refund, order);
            break;
          case 'text.delta':
            text += event.delta;
            break;
          case 'handoff.update':
            enterQueue(c, scenario.personJoins);
            break;
          default:
            break;
        }
        yield event;
      }
      turns.set(input.clientMessageId, 'done');
      addEntry(c, { author: 'bot', name: null, text, tools, sources });
      touch(c);
    },

    async startVerification(conversationId, phone) {
      const c = need(conversations.get(conversationId), 'Conversation');
      const record = identityOf(c.id);
      if (record.lockedUntil > now()) throw tooManyAttempts(record);
      if (!/^\+974\d{8}$/.test(phone)) {
        throw new ApiError(422, {
          code: 'invalid_phone',
          message: locale === 'ar' ? 'رقم الجوال غير صحيح.' : 'That mobile number is not valid.',
          retryable: true,
        });
      }
      const code = makeCode();
      record.pending = { code, expiresAt: now() + CODE_LIFETIME_SECONDS * 1000 };
      await wait(500);
      return {
        status: 'code_sent',
        maskedPhone: `+974 •••• ${phone.slice(-4)}`,
        expiresInSeconds: CODE_LIFETIME_SECONDS,
        resendInSeconds: RESEND_SECONDS,
        simulatedCode: code,
      };
    },

    async confirmVerification(conversationId, code) {
      const c = need(conversations.get(conversationId), 'Conversation');
      const record = identityOf(c.id);
      if (record.lockedUntil > now()) throw tooManyAttempts(record);
      await wait(400);
      if (!record.pending || record.pending.expiresAt < now()) {
        throw new ApiError(410, {
          code: 'code_expired',
          message: locale === 'ar' ? 'انتهت صلاحية هذا الرمز.' : 'That code has expired.',
          retryable: true,
        });
      }
      if (record.pending.code !== code) {
        record.failures += 1;
        addAudit({
          actorKind: 'system',
          actorName: SYSTEM_NAME,
          action: 'identity.failed',
          target: c.id,
          detail: { en: 'A wrong code was entered', ar: 'أُدخل رمز خاطئ' },
        });
        if (record.failures >= MOCK_RULES.otpMaxFailures) {
          record.lockedUntil = now() + MOCK_RULES.otpLockMinutes * 60_000;
          record.pending = null;
          throw tooManyAttempts(record);
        }
        throw new ApiError(400, {
          code: 'invalid_code',
          message: locale === 'ar' ? 'هذا الرمز غير صحيح.' : 'That code is not right.',
          retryable: true,
          attemptsLeft: MOCK_RULES.otpMaxFailures - record.failures,
        });
      }
      record.pending = null;
      record.failures = 0;
      c.verified = true;
      addAudit({
        actorKind: 'system',
        actorName: SYSTEM_NAME,
        action: 'identity.verified',
        target: c.id,
        detail: { en: 'Customer confirmed by a code sent to their number', ar: 'تم تأكيد العميل برمز أُرسل إلى رقمه' },
      });
      touch(c);
      return { verified: true, customerName: pick(c.customer, c.locale) };
    },

    async requestHandoff(conversationId) {
      const c = need(conversations.get(conversationId), 'Conversation');
      const handoff: Handoff = { status: 'queued', agentName: null, etaMinutes: 2, position: 2 };
      if (c.state === 'bot') {
        enterQueue(c, scenarioFor('handoff').personJoins);
        emitConversation(c.id, { type: 'handoff.update', handoff });
      }
      return handoff;
    },

    subscribeConversation(conversationId, onEvent): Unsubscribe {
      const set = conversationSubs.get(conversationId) ?? new Set();
      set.add(onEvent);
      conversationSubs.set(conversationId, set);
      return () => {
        set.delete(onEvent);
      };
    },

    async getDeskAgent() {
      return signedIn ? deskAgent() : null;
    },
    async signInToDesk() {
      signedIn = true;
      return deskAgent();
    },
    async signOutOfDesk() {
      signedIn = false;
    },
    async getDeskSummary() {
      return summary();
    },
    async listConversations() {
      return [...conversations.values()].map(viewConversation);
    },
    async getConversationDetail(id): Promise<ConversationDetail> {
      const c = need(conversations.get(id), 'Conversation');
      return { ...viewConversation(c), transcript: c.transcript.map(viewEntry) };
    },
    async claimConversation(id) {
      const c = need(conversations.get(id), 'Conversation');
      joinAgent(c, AGENT_NOOR);
      return viewConversation(c);
    },
    async closeConversation(id) {
      const c = need(conversations.get(id), 'Conversation');
      const pending = joinTimers.get(c.id);
      if (pending) clearTimeout(pending);
      joinTimers.delete(c.id);
      c.state = 'closed';
      c.waitingSince = null;
      emitConversation(c.id, { type: 'conversation.closed', at: new Date().toISOString() });
      addAudit({
        actorKind: 'agent',
        actorName: c.agentName ?? AGENT_NOOR,
        action: 'conversation.closed',
        target: c.id,
        detail: { en: 'Ended the conversation', ar: 'أنهى المحادثة' },
      });
      touch(c);
      return viewConversation(c);
    },
    async replyToConversation(id, text) {
      const c = need(conversations.get(id), 'Conversation');
      const agent = c.agentName ?? AGENT_NOOR;
      agentSays(c, agent, text);
      addAudit({
        actorKind: 'agent',
        actorName: agent,
        action: 'agent.replied',
        target: c.id,
        detail: { en: 'Sent a reply to the customer', ar: 'أرسل ردًا إلى العميل' },
      });
    },

    async listRefunds() {
      return [...refunds.values()].map(viewRefund);
    },
    async decideRefund(id, decision: RefundDecision) {
      const stored = need(refunds.get(id), 'Refund');
      if (stored.status !== 'pending' || stored.version !== decision.version) {
        throw new ApiError(409, {
          code: 'refund_already_decided',
          message: 'This refund has already been decided.',
          retryable: false,
        });
      }
      if (!viewRefund(stored).canDecide) {
        throw new ApiError(403, {
          code: 'approval_limit_exceeded',
          message: 'This refund needs a supervisor.',
          retryable: false,
        });
      }
      const at = now();
      const decided = applyDecision(viewRefund(stored), decision, pick(AGENT_NOOR, locale), iso(at));
      stored.status = decided.status;
      stored.decidedBy = AGENT_NOOR;
      stored.decidedAt = at;
      stored.note = decided.note ? same(decided.note) : null;
      stored.version = decided.version;

      resolvedToday += 1;
      const amount = stored.amountQar.toFixed(2);
      addAudit({
        actorKind: 'agent',
        actorName: AGENT_NOOR,
        action: decision.action === 'approve' ? 'refund.approved' : 'refund.rejected',
        target: id,
        detail: {
          en: `QAR ${amount}. ${decided.note ?? 'No note.'}`,
          ar: `${amount} ريالًا. ${decided.note ?? 'بدون ملاحظة.'}`,
        },
      });
      const view = viewRefund(stored);
      emitDesk({ type: 'refund.updated', refund: view });
      emitSummary();
      const c = conversations.get(stored.conversationId);
      emitConversation(stored.conversationId, {
        type: 'refund.update',
        refund: {
          id: view.id,
          orderId: view.orderId,
          amountQar: view.amountQar,
          status: view.status,
          decidedBy: pick(AGENT_NOOR, c?.locale ?? locale),
          // An approval note is for the audit log only. A rejection reason reaches the customer.
          note: decision.action === 'reject' ? view.note : null,
        },
      });
      return view;
    },

    async listAudit(filter: AuditFilter, cursor) {
      const matches = auditLog.filter((a) => {
        if (filter === 'bot') return a.actorKind === 'bot' && a.action !== 'guardrail.blocked';
        if (filter === 'agent') return a.actorKind === 'agent';
        if (filter === 'guardrail') return a.action === 'guardrail.blocked';
        return true;
      });
      const start = cursor ? Number(cursor) : 0;
      const end = start + PAGE_SIZE;
      return {
        entries: matches.slice(start, end).map(viewAudit),
        nextCursor: end < matches.length ? String(end) : null,
      };
    },

    async getTopIssues(windowDays: WindowDays): Promise<TopIssue[]> {
      return issuesFor(windowDays).map((issue) => ({
        id: issue.id,
        label: pick(issue.label, locale),
        count: issue.count,
        changePct: issue.changePct,
      }));
    },

    async getQuality(windowDays: WindowDays): Promise<QualityReport> {
      const { resolved, tiles } = QUALITY_BASE;
      const scale = windowDays === 7 ? 1 : windowDays === 14 ? 0.8 : 0.6;
      const heroTrend = trendFor(11, windowDays, resolved.value, 5, resolved.delta * 1.6);
      return {
        windowDays,
        hero: {
          id: 'resolved',
          label: pick(resolved.label, locale),
          value: resolved.value,
          unit: 'percent',
          delta: Number((resolved.delta * scale).toFixed(1)),
          higherIsBetter: true,
          trend: heroTrend,
        },
        tiles: tiles.map((tile, i) => ({
          id: tile.id,
          label: pick(tile.label, locale),
          value: tile.value,
          unit: tile.unit,
          delta: Number((tile.delta * scale).toFixed(1)),
          higherIsBetter: tile.higherIsBetter,
          trend: trendFor(20 + i, 12, tile.value, tile.spread, tile.delta),
        })),
        series: heroTrend.map((value, i) => ({
          date: iso(now() - (windowDays - 1 - i) * 86_400_000),
          value,
        })),
      };
    },

    subscribeDesk(onEvent): Unsubscribe {
      deskSubs.add(onEvent);
      startTicks();
      return () => {
        deskSubs.delete(onEvent);
      };
    },
  };
}
