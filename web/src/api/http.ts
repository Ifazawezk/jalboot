import type { SupportApi, Unsubscribe } from './client';
import {
  ApiError,
  CONVERSATION_EVENT_TYPES,
  DESK_EVENT_TYPES,
  STREAM_EVENT_TYPES,
  type ApiErrorBody,
  type AuditPage,
  type Conversation,
  type ConversationDetail,
  type ConversationEvent,
  type DeskAgent,
  type DeskEvent,
  type DeskPolicy,
  type DeskSummary,
  type Handoff,
  type LiveConversation,
  type Locale,
  type Policy,
  type QualityReport,
  type Refund,
  type StreamEvent,
  type TopIssue,
  type VerifyConfirmResult,
  type VerifyStartResult,
} from './types';
import { readSse, type SseMessage } from '../lib/sse';

const RECONNECT_MIN_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

export function parseEvent<T extends { type: string }>(
  message: SseMessage,
  known: readonly string[],
): T | null {
  // Unknown event names are skipped, so the backend can add events without breaking old pages.
  if (!known.includes(message.event)) return null;
  try {
    return { ...(JSON.parse(message.data) as object), type: message.event } as T;
  } catch {
    return null;
  }
}

/** Reads the error envelope from API.md, and FastAPI's default { detail } as a fallback. */
export async function readError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = {
    code: `http_${response.status}`,
    message: response.statusText || 'Request failed',
    retryable: response.status === 429 || response.status >= 500,
  };
  try {
    const json = (await response.json()) as {
      error?: Partial<ApiErrorBody>;
      detail?: unknown;
    };
    if (json.error) body = { ...body, ...json.error };
    else if (typeof json.detail === 'string') body = { ...body, message: json.detail };
  } catch {
    // A body that is not JSON keeps the defaults above.
  }
  return new ApiError(response.status, body);
}

export function backoffMs(attempt: number): number {
  return Math.min(RECONNECT_MAX_MS, RECONNECT_MIN_MS * 2 ** attempt);
}

interface DeskSession {
  agent: DeskAgent;
  csrfToken: string;
}

export function createHttpApi(
  base: string,
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): SupportApi {
  const root = base.replace(/\/$/, '');
  let locale: Locale = 'en';

  // Both of these live in memory only. The desk session itself is an HttpOnly cookie
  // that page scripts cannot read, so nothing here can be stolen from storage.
  const conversationTokens = new Map<string, string>();
  let csrfToken: string | null = null;

  const customerHeaders = (conversationId: string | null, extra?: Record<string, string>) => {
    const token = conversationId ? conversationTokens.get(conversationId) : null;
    return {
      'Accept-Language': locale,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...extra,
    };
  };

  async function customer<T>(path: string, conversationId: string | null, init?: RequestInit): Promise<T> {
    const response = await fetchImpl(`${root}${path}`, {
      ...init,
      headers: customerHeaders(
        conversationId,
        init?.body ? { 'Content-Type': 'application/json' } : undefined,
      ),
    });
    if (!response.ok) throw await readError(response);
    return (await response.json()) as T;
  }

  function deskRequest(path: string, init?: RequestInit): Promise<Response> {
    const isWrite = (init?.method ?? 'GET') !== 'GET';
    return fetchImpl(`${root}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        'Accept-Language': locale,
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(isWrite && csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
    });
  }

  /** Restores the session from the cookie. Null means signed out. */
  async function loadSession(): Promise<DeskAgent | null> {
    const response = await deskRequest('/desk/me');
    if (response.status === 401) {
      csrfToken = null;
      return null;
    }
    if (!response.ok) throw await readError(response);
    const session = (await response.json()) as DeskSession;
    csrfToken = session.csrfToken;
    return session.agent;
  }

  async function desk<T>(path: string, init?: RequestInit): Promise<T> {
    let response = await deskRequest(path, init);
    if (response.status === 403) {
      const error = await readError(response);
      if (error.code !== 'csrf_failed') throw error;
      // A stale CSRF token: fetch a fresh one and retry once.
      if (!(await loadSession())) throw error;
      response = await deskRequest(path, init);
    }
    if (!response.ok) throw await readError(response);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  /** Keeps a GET event stream open, reconnecting with Last-Event-ID after a drop. */
  function follow<T extends { type: string }>(
    path: string,
    init: () => RequestInit,
    known: readonly string[],
    onEvent: (event: T) => void,
  ): Unsubscribe {
    const controller = new AbortController();
    let lastId: string | null = null;

    const run = async () => {
      let attempt = 0;
      while (!controller.signal.aborted) {
        try {
          const request = init();
          const response = await fetchImpl(`${root}${path}`, {
            ...request,
            headers: {
              ...(request.headers as Record<string, string>),
              Accept: 'text/event-stream',
              ...(lastId ? { 'Last-Event-ID': lastId } : {}),
            },
            signal: controller.signal,
          });
          if (!response.ok) throw await readError(response);
          if (!response.body) throw new Error('No stream body');
          attempt = 0;
          for await (const message of readSse(response.body)) {
            if (message.id) lastId = message.id;
            const event = parseEvent<T>(message, known);
            if (event) onEvent(event);
          }
        } catch (error) {
          if (controller.signal.aborted) return;
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) return;
        }
        const delay = backoffMs(attempt);
        attempt += 1;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    };
    void run();
    return () => controller.abort();
  }

  return {
    mode: 'live',

    setLocale(next) {
      locale = next;
    },

    async getPolicy() {
      try {
        return await customer<Policy>('/policy', null);
      } catch {
        return null;
      }
    },

    async createConversation(chosen) {
      const conversation = await customer<Conversation>('/conversations', null, {
        method: 'POST',
        body: JSON.stringify({ locale: chosen }),
      });
      conversationTokens.set(conversation.id, conversation.token);
      return conversation;
    },

    async *sendMessage(conversationId, input, signal) {
      const response = await fetchImpl(`${root}/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: customerHeaders(conversationId, {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        }),
        body: JSON.stringify(input),
        signal,
      });
      if (!response.ok) throw await readError(response);
      if (!response.body) throw new Error('No stream body');
      for await (const message of readSse(response.body)) {
        const event = parseEvent<StreamEvent>(message, STREAM_EVENT_TYPES);
        if (event) yield event;
      }
    },

    startVerification(conversationId, phone) {
      return customer<VerifyStartResult>(`/conversations/${conversationId}/verify/start`, conversationId, {
        method: 'POST',
        body: JSON.stringify({ phone }),
      });
    },

    confirmVerification(conversationId, code) {
      return customer<VerifyConfirmResult>(`/conversations/${conversationId}/verify/confirm`, conversationId, {
        method: 'POST',
        body: JSON.stringify({ code }),
      });
    },

    requestHandoff(conversationId, reason) {
      return customer<Handoff>(`/conversations/${conversationId}/handoff`, conversationId, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
    },

    subscribeConversation(conversationId, onEvent) {
      return follow<ConversationEvent>(
        `/conversations/${conversationId}/events`,
        () => ({ headers: customerHeaders(conversationId) }),
        CONVERSATION_EVENT_TYPES,
        onEvent,
      );
    },

    getDeskAgent: loadSession,

    async signInToDesk(email, password) {
      const session = await desk<DeskSession>('/desk/session', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      csrfToken = session.csrfToken;
      return session.agent;
    },

    async signOutOfDesk() {
      await desk<void>('/desk/logout', { method: 'POST' });
      csrfToken = null;
    },

    getDeskSummary: () => desk<DeskSummary>('/desk/summary'),
    listConversations: () =>
      desk<{ conversations: LiveConversation[] }>('/desk/conversations').then((r) => r.conversations),
    getConversationDetail: (id) => desk<ConversationDetail>(`/desk/conversations/${id}`),
    claimConversation: (id) =>
      desk<LiveConversation>(`/desk/conversations/${id}/claim`, { method: 'POST' }),
    closeConversation: (id) =>
      desk<LiveConversation>(`/desk/conversations/${id}/close`, { method: 'POST' }),
    async getDeskPolicy() {
      try {
        return await desk<DeskPolicy>('/desk/policy');
      } catch {
        return null;
      }
    },
    replyToConversation: (id, text) =>
      desk<void>(`/desk/conversations/${id}/reply`, {
        method: 'POST',
        body: JSON.stringify({ text }),
      }),
    listRefunds: () => desk<{ refunds: Refund[] }>('/desk/refunds').then((r) => r.refunds),
    decideRefund: (id, decision) =>
      desk<Refund>(`/desk/refunds/${id}/decision`, {
        method: 'POST',
        body: JSON.stringify(decision),
      }),
    listAudit: (filter, cursor) => {
      const query = new URLSearchParams({ filter });
      if (cursor) query.set('cursor', cursor);
      return desk<AuditPage>(`/desk/audit?${query.toString()}`);
    },
    getTopIssues: (windowDays) =>
      desk<{ issues: TopIssue[] }>(`/desk/metrics/top-issues?windowDays=${windowDays}`).then(
        (r) => r.issues,
      ),
    getQuality: (windowDays) => desk<QualityReport>(`/desk/metrics/quality?windowDays=${windowDays}`),
    subscribeDesk: (onEvent) =>
      follow<DeskEvent>(
        '/desk/events',
        () => ({ credentials: 'include', headers: { 'Accept-Language': locale } }),
        DESK_EVENT_TYPES,
        onEvent,
      ),
  };
}
