import type {
  Citation,
  ConversationEvent,
  Handoff,
  Order,
  RefundSummary,
  StreamEvent,
} from '../api/types';
import { stripMarkers } from './citations';

export interface ToolActivity {
  id: string;
  tool: string;
  /** Plain-language fallback from the server, used when the tool name is unknown here. */
  label: string;
  status: 'running' | 'ok' | 'error';
}

export interface BotItem {
  kind: 'bot';
  id: string;
  text: string;
  tools: ToolActivity[];
  orders: Order[];
  citations: Citation[];
  refunds: RefundSummary[];
  status: 'streaming' | 'complete' | 'stopped' | 'failed';
  errorMessage: string | null;
  retryable: boolean;
}

export interface CustomerItem {
  kind: 'customer';
  id: string;
  text: string;
}

export interface AgentItem {
  kind: 'agent';
  id: string;
  agentName: string;
  text: string;
  at: string;
}

export interface NoticeItem {
  kind: 'notice';
  id: string;
  notice:
    | 'handoff_queued'
    | 'handoff_joined'
    | 'handoff_failed'
    | 'closed'
    | 'refund_decided'
    | 'identity_verified'
    | 'identity_cancelled';
  agentName: string | null;
  refundId: string | null;
}

export type ChatItem = BotItem | CustomerItem | AgentItem | NoticeItem;

/** Where the identity check is. The phone number and the code are never stored here. */
export type IdentityPhase = 'none' | 'phone' | 'code' | 'verified';

export interface ChatState {
  items: ChatItem[];
  streaming: boolean;
  handoff: Handoff | null;
  closed: boolean;
  identity: IdentityPhase;
  maskedPhone: string | null;
}

export type ChatAction =
  | StreamEvent
  | ConversationEvent
  | { type: 'customer.message'; id: string; text: string }
  | { type: 'identity.code_sent'; maskedPhone: string }
  | { type: 'identity.restart' }
  | { type: 'identity.verified' }
  | { type: 'identity.cancelled' }
  | { type: 'handoff.failed' }
  | { type: 'turn.stopped' }
  | { type: 'turn.failed'; message: string; retryable: boolean }
  | { type: 'reset' };

export const initialChatState: ChatState = {
  items: [],
  streaming: false,
  handoff: null,
  closed: false,
  identity: 'none',
  maskedPhone: null,
};

/** True while the chat box must stay locked, so a code cannot be typed into the conversation. */
export function identityOpen(phase: IdentityPhase): boolean {
  return phase === 'phone' || phase === 'code';
}

function updateOpenBot(state: ChatState, update: (item: BotItem) => BotItem): ChatState {
  for (let i = state.items.length - 1; i >= 0; i -= 1) {
    const item = state.items[i];
    if (item?.kind === 'bot' && item.status === 'streaming') {
      const items = state.items.slice();
      items[i] = update(item);
      return { ...state, items };
    }
  }
  return state;
}

function replaceBy<T>(list: T[], next: T, same: (a: T) => boolean): T[] {
  return list.some(same) ? list.map((x) => (same(x) ? next : x)) : [...list, next];
}

function closeOpenBot(
  state: ChatState,
  status: BotItem['status'],
  errorMessage: string | null,
  retryable: boolean,
): ChatState {
  const next = updateOpenBot(state, (item) => ({
    ...item,
    status,
    errorMessage,
    retryable,
    tools: item.tools.map((t) =>
      t.status === 'running' ? { ...t, status: status === 'failed' ? 'error' : 'ok' } : t,
    ),
  }));
  return { ...next, streaming: false };
}

function failTurn(state: ChatState, message: string, retryable: boolean): ChatState {
  if (state.items.some((item) => item.kind === 'bot' && item.status === 'streaming')) {
    return closeOpenBot(state, 'failed', message, retryable);
  }
  return {
    ...state,
    streaming: false,
    items: [
      ...state.items,
      {
        kind: 'bot',
        id: `failed-${state.items.length}`,
        text: '',
        tools: [],
        orders: [],
        citations: [],
        refunds: [],
        status: 'failed',
        errorMessage: message,
        retryable,
      },
    ],
  };
}

function applyRefund(state: ChatState, refund: RefundSummary): ChatState {
  let found = false;
  const items: ChatItem[] = state.items.map((item) => {
    if (item.kind !== 'bot' || !item.refunds.some((r) => r.id === refund.id)) return item;
    found = true;
    return { ...item, refunds: item.refunds.map((r) => (r.id === refund.id ? refund : r)) };
  });
  if (found) {
    const decided = refund.status === 'approved' || refund.status === 'rejected';
    const alreadyNoted = items.some(
      (item) => item.kind === 'notice' && item.refundId === refund.id,
    );
    if (decided && !alreadyNoted) {
      items.push({
        kind: 'notice',
        id: `notice-${refund.id}`,
        notice: 'refund_decided',
        agentName: refund.decidedBy,
        refundId: refund.id,
      });
    }
    return { ...state, items };
  }
  return updateOpenBot(state, (item) => ({ ...item, refunds: [...item.refunds, refund] }));
}

function addNotice(
  state: ChatState,
  notice: 'identity_verified' | 'identity_cancelled' | 'handoff_failed',
): ChatState {
  return {
    ...state,
    items: [
      ...state.items,
      {
        kind: 'notice',
        id: `notice-${notice}-${state.items.length}`,
        notice,
        agentName: null,
        refundId: null,
      },
    ],
  };
}

function applyHandoff(state: ChatState, handoff: Handoff): ChatState {
  const items = state.items.slice();
  const noted = (notice: NoticeItem['notice']) =>
    items.some((item) => item.kind === 'notice' && item.notice === notice);
  if (handoff.status === 'queued' && !noted('handoff_queued')) {
    items.push({
      kind: 'notice',
      id: `notice-queued-${items.length}`,
      notice: 'handoff_queued',
      agentName: null,
      refundId: null,
    });
  }
  if (handoff.status === 'joined' && !noted('handoff_joined')) {
    items.push({
      kind: 'notice',
      id: `notice-joined-${items.length}`,
      notice: 'handoff_joined',
      agentName: handoff.agentName,
      refundId: null,
    });
  }
  return { ...state, items, handoff };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'reset':
      return initialChatState;
    case 'customer.message':
      return {
        ...state,
        items: [...state.items, { kind: 'customer', id: action.id, text: action.text }],
      };
    case 'message.start': {
      // The backend keeps the ID when it runs a held turn again, so only a reply that is still
      // open counts as a repeat. A finished one means a new run, which needs its own bubble.
      const runs = state.items.filter(
        (item) => item.id === action.messageId || item.id.startsWith(`${action.messageId}-run-`),
      );
      if (runs.some((item) => item.kind === 'bot' && item.status === 'streaming')) return state;
      return {
        ...state,
        streaming: true,
        items: [
          ...state.items,
          {
            kind: 'bot',
            id: runs.length > 0 ? `${action.messageId}-run-${runs.length + 1}` : action.messageId,
            text: '',
            tools: [],
            orders: [],
            citations: [],
            refunds: [],
            status: 'streaming',
            errorMessage: null,
            retryable: false,
          },
        ],
      };
    }
    case 'tool.start':
      return updateOpenBot(state, (item) => ({
        ...item,
        tools: [
          ...item.tools,
          { id: action.toolCallId, tool: action.tool, label: action.label, status: 'running' },
        ],
      }));
    case 'tool.end':
      return updateOpenBot(state, (item) => ({
        ...item,
        tools: item.tools.map((t) =>
          t.id === action.toolCallId
            ? { ...t, status: action.status, label: action.label ?? t.label }
            : t,
        ),
      }));
    case 'text.delta':
      return updateOpenBot(state, (item) => ({ ...item, text: item.text + action.delta }));
    case 'order.card':
      return updateOpenBot(state, (item) => ({
        ...item,
        orders: replaceBy(item.orders, action.order, (o) => o.id === action.order.id),
      }));
    case 'citation':
      return updateOpenBot(state, (item) => ({
        ...item,
        citations: replaceBy(item.citations, action.citation, (c) => c.n === action.citation.n),
      }));
    case 'refund.update':
      return applyRefund(state, action.refund);
    case 'handoff.update':
      return applyHandoff(state, action.handoff);
    case 'handoff.failed':
      return addNotice(state, 'handoff_failed');
    case 'identity.required':
      return state.identity === 'verified' ? state : { ...state, identity: 'phone', maskedPhone: null };
    case 'identity.code_sent':
      return { ...state, identity: 'code', maskedPhone: action.maskedPhone };
    case 'identity.restart':
      return { ...state, identity: 'phone', maskedPhone: null };
    case 'identity.verified':
      return addNotice({ ...state, identity: 'verified', maskedPhone: null }, 'identity_verified');
    case 'identity.cancelled':
      return addNotice({ ...state, identity: 'none', maskedPhone: null }, 'identity_cancelled');
    case 'message.end': {
      const closed = closeOpenBot(state, 'complete', null, false);
      if (action.finish !== 'forwarded') return closed;
      // The message went to a person, so the opened reply has nothing to show.
      const silent = (item: ChatItem) =>
        item.kind === 'bot' && item.status === 'complete' && !item.text && item.tools.length === 0;
      return { ...closed, items: closed.items.filter((item) => !silent(item)) };
    }
    case 'error':
      return failTurn(state, action.error.message, action.error.retryable);
    case 'turn.stopped':
      return closeOpenBot(state, 'stopped', null, false);
    case 'turn.failed':
      return failTurn(state, action.message, action.retryable);
    case 'agent.message':
      if (state.items.some((item) => item.id === action.messageId)) return state;
      return {
        ...state,
        items: [
          ...state.items,
          {
            kind: 'agent',
            id: action.messageId,
            agentName: action.agentName,
            text: action.text,
            at: action.at,
          },
        ],
      };
    case 'conversation.closed':
      return {
        ...state,
        closed: true,
        items: [
          ...state.items,
          {
            kind: 'notice',
            id: `notice-closed-${state.items.length}`,
            notice: 'closed',
            agentName: null,
            refundId: null,
          },
        ],
      };
    default:
      return state;
  }
}

/** Orders seen so far, newest first, for the side panel. */
export function collectOrders(items: ChatItem[]): Order[] {
  const byId = new Map<string, Order>();
  for (const item of items) {
    if (item.kind !== 'bot') continue;
    for (const order of item.orders) byId.set(order.id, order);
  }
  return [...byId.values()].reverse();
}

/** All sources cited so far, once each. */
export function collectSources(items: ChatItem[]): Citation[] {
  const bySource = new Map<string, Citation>();
  for (const item of items) {
    if (item.kind !== 'bot') continue;
    for (const citation of item.citations) bySource.set(citation.sourceId, citation);
  }
  return [...bySource.values()];
}

/** What a screen reader should hear for the latest turn, or null while it is still forming. */
export function lastSpokenText(items: ChatItem[]): string | null {
  const last = items[items.length - 1];
  if (!last) return null;
  if (last.kind === 'bot' && last.status === 'complete') {
    return stripMarkers(last.text);
  }
  if (last.kind === 'agent') return `${last.agentName}: ${last.text}`;
  return null;
}
