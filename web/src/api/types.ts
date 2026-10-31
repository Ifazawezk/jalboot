// Wire types shared by the mock, the recordings and the HTTP client.
// API.md documents these same shapes for the backend.

export type Locale = 'en' | 'ar';
export type ApiMode = 'mock' | 'demo' | 'live';
/** What the server answers with: fixed rules in mock mode, or a real model in live mode. */
export type AssistantMode = 'mock' | 'live';

export type Vertical = 'food' | 'grocery' | 'pharmacy' | 'parcel';

export interface OrderItem {
  name: string;
  qty: number;
  priceQar: number;
  flag?: 'missing' | 'wrong';
}

export interface Order {
  id: string;
  vertical: Vertical;
  /** A value from the status paths in the policy rules. See orderStep in lib/orders.ts. */
  status: string;
  store: string;
  area: string;
  placedAt: string;
  etaAt: string | null;
  deliveredAt: string | null;
  rider: string | null;
  items: OrderItem[];
  /** Delivery, service and any other fees together. */
  feesQar: number;
  totalQar: number;
}

export interface Citation {
  /** Marker number. The reply text refers to it as [n]. */
  n: number;
  sourceId: string;
  title: string;
  section: string;
  excerpt: string;
  updatedAt: string;
}

export type RefundStatus = 'auto_approved' | 'pending' | 'approved' | 'rejected';

export interface RefundSummary {
  id: string;
  orderId: string;
  amountQar: number;
  status: RefundStatus;
  decidedBy: string | null;
  note: string | null;
}

export type HandoffStatus = 'requested' | 'queued' | 'joined' | 'closed';

export interface Handoff {
  status: HandoffStatus;
  agentName: string | null;
  etaMinutes: number | null;
  position: number | null;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  retryable: boolean;
  attemptsLeft?: number | null;
  retryAfterSeconds?: number | null;
}

/** Timings a customer may be told, read from the public GET /policy. */
export interface Policy {
  policyVersion: string;
  currency: string;
  assistant?: AssistantMode;
  refund: {
    cardBusinessDays: number | null;
    creditMinutes: number | null;
  };
}

/** Approval limits are internal (REF-05, ESC-03), so only signed-in staff can read them. */
export interface DeskPolicy {
  refund: {
    automatedLimitQar: number | null;
    newAccountAutomatedLimitQar: number | null;
    agentLimitQar: number | null;
    supervisorLimitQar: number | null;
  };
}

export interface VerifyStartResult {
  status: 'code_sent';
  maskedPhone: string;
  expiresInSeconds: number;
  resendInSeconds: number;
  /** Only in simulated mode. Shown in a panel labelled as a simulated SMS. */
  simulatedCode?: string | null;
}

export interface VerifyConfirmResult {
  verified: true;
  customerName?: string | null;
}

/** Events on POST /conversations/{id}/messages. The SSE `event:` field carries `type`. */
export type StreamEvent =
  | { type: 'message.start'; messageId: string }
  | { type: 'tool.start'; toolCallId: string; tool: string; label: string }
  | { type: 'tool.end'; toolCallId: string; status: 'ok' | 'error'; label?: string }
  | { type: 'text.delta'; delta: string }
  | { type: 'order.card'; order: Order }
  | { type: 'citation'; citation: Citation }
  | { type: 'refund.update'; refund: RefundSummary }
  | { type: 'handoff.update'; handoff: Handoff }
  | { type: 'identity.required'; reason: string }
  | { type: 'message.end'; finish: 'complete' | 'handoff' | 'identity_required' | 'forwarded' }
  | { type: 'error'; error: ApiErrorBody };

/** Events on GET /conversations/{id}/events, the channel that stays open between turns. */
export type ConversationEvent =
  | { type: 'handoff.update'; handoff: Handoff }
  | { type: 'refund.update'; refund: RefundSummary }
  | { type: 'agent.message'; messageId: string; agentName: string; text: string; at: string }
  | { type: 'conversation.closed'; at: string };

export const STREAM_EVENT_TYPES = [
  'message.start',
  'tool.start',
  'tool.end',
  'text.delta',
  'order.card',
  'citation',
  'refund.update',
  'handoff.update',
  'identity.required',
  'message.end',
  'error',
] as const satisfies readonly StreamEvent['type'][];

export const CONVERSATION_EVENT_TYPES = [
  'handoff.update',
  'refund.update',
  'agent.message',
  'conversation.closed',
] as const satisfies readonly ConversationEvent['type'][];

export interface Conversation {
  id: string;
  token: string;
  locale: Locale;
  createdAt: string;
  verified: boolean;
  assistant?: AssistantMode;
}

export interface SendMessageInput {
  clientMessageId: string;
  text: string;
  locale: Locale;
}

// Desk

export type LiveState = 'bot' | 'waiting' | 'agent' | 'closed';
export type Priority = 'normal' | 'high';

export interface LiveConversation {
  id: string;
  customer: string;
  locale: Locale;
  state: LiveState;
  priority: Priority;
  verified: boolean;
  summary: string;
  orderId: string | null;
  agentName: string | null;
  startedAt: string;
  updatedAt: string;
  /** Set while state is 'waiting'. The desk counts up from this. */
  waitingSince: string | null;
}

export type TranscriptAuthor = 'customer' | 'bot' | 'agent' | 'system';

export interface TranscriptEntry {
  id: string;
  at: string;
  author: TranscriptAuthor;
  name: string | null;
  text: string;
  /** Plain-language labels of the tools used for this reply. */
  tools: string[];
  /** Titles of the sources cited in this reply. */
  sources: string[];
}

export interface ConversationDetail extends LiveConversation {
  transcript: TranscriptEntry[];
}

export type DeskRole = 'agent' | 'supervisor' | 'finance_lead';

export type RefundReason = 'missing_item' | 'wrong_item' | 'late' | 'quality';

export interface Refund extends RefundSummary {
  conversationId: string;
  customer: string;
  store: string;
  reason: RefundReason;
  summary: string;
  requestedAt: string;
  decidedAt: string | null;
  recommendation: 'approve' | 'review' | 'reject';
  evidence: { label: string; value: string }[];
  policy: { title: string; section: string };
  risks: string[];
  version: number;
  /** Worked out by the backend. The UI never compares an amount with a limit. */
  canDecide: boolean;
  requiredRole: DeskRole;
}

export interface RefundDecision {
  action: 'approve' | 'reject';
  note: string;
  /** The version the agent was looking at. A stale version gets a 409. */
  version: number;
}

export type ActorKind = 'bot' | 'agent' | 'system';

export const AUDIT_ACTIONS = [
  'tool.called',
  'refund.auto_approved',
  'refund.proposed',
  'refund.approved',
  'refund.rejected',
  'handoff.requested',
  'handoff.joined',
  'agent.replied',
  'guardrail.blocked',
  'identity.verified',
  'identity.failed',
  'conversation.closed',
] as const;
export type AuditAction = (typeof AUDIT_ACTIONS)[number];

export interface AuditEntry {
  id: string;
  at: string;
  actorKind: ActorKind;
  actorName: string;
  /** Usually an AuditAction. Anything else is shown as sent. */
  action: string;
  target: string;
  detail: string;
}

export interface AuditPage {
  entries: AuditEntry[];
  nextCursor: string | null;
}

export type AuditFilter = 'all' | 'bot' | 'agent' | 'guardrail';

export type WindowDays = 7 | 14 | 30;

export interface TopIssue {
  id: string;
  label: string;
  count: number;
  /** Percent change against the window before this one. */
  changePct: number;
}

export interface QualityTile {
  id: string;
  label: string;
  value: number;
  unit: 'percent' | 'seconds' | 'score';
  /** Change against the window before this one, in the tile's own unit. */
  delta: number;
  higherIsBetter: boolean;
  trend: number[];
}

export interface QualityReport {
  windowDays: WindowDays;
  hero: QualityTile;
  tiles: QualityTile[];
  /** One point per day for the hero metric, oldest first. */
  series: { date: string; value: number }[];
}

export interface DeskSummary {
  live: number;
  waiting: number;
  refundsPending: number;
  resolvedToday: number;
}

export interface DeskAgent {
  id: string;
  name: string;
  role: DeskRole;
}

export type DeskEvent =
  | { type: 'conversation.updated'; conversation: LiveConversation }
  | { type: 'conversation.message'; conversationId: string; entry: TranscriptEntry }
  | { type: 'refund.created'; refund: Refund }
  | { type: 'refund.updated'; refund: Refund }
  | { type: 'audit.appended'; entry: AuditEntry }
  | { type: 'summary.updated'; summary: DeskSummary };

export const DESK_EVENT_TYPES = [
  'conversation.updated',
  'conversation.message',
  'refund.created',
  'refund.updated',
  'audit.appended',
  'summary.updated',
] as const satisfies readonly DeskEvent['type'][];

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly attemptsLeft: number | null;
  readonly retryAfterSeconds: number | null;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.retryable = body.retryable;
    this.attemptsLeft = body.attemptsLeft ?? null;
    this.retryAfterSeconds = body.retryAfterSeconds ?? null;
  }
}
