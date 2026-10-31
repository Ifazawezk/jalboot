import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import { backoffMs, createHttpApi, parseEvent, readError } from './http';
import { ApiError, STREAM_EVENT_TYPES } from './types';

interface Call {
  url: string;
  init: RequestInit;
  headers: Record<string, string>;
}

function json(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function stubFetch(answer: (call: Call, index: number) => Response) {
  const calls: Call[] = [];
  const fetchImpl = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const call = { url: String(input), init, headers: (init.headers ?? {}) as Record<string, string> };
    calls.push(call);
    return answer(call, calls.length - 1);
  }) as typeof fetch;
  return { calls, fetchImpl };
}

const AGENT = { id: 'a1', name: 'Noor', role: 'agent' };

describe('desk session', () => {
  it('signs in with the cookie and sends the CSRF token on later writes', async () => {
    const { calls, fetchImpl } = stubFetch((call) =>
      call.url.endsWith('/desk/session') ? json(200, { csrfToken: 'csrf-1', agent: AGENT }) : json(200, {}),
    );
    const api = createHttpApi('/api/v1', fetchImpl);
    await api.signInToDesk('noor@example.test', 'secret');
    await api.claimConversation('cv-1');

    const claim = calls[1];
    expect(claim?.init.credentials).toBe('include');
    expect(claim?.headers['X-CSRF-Token']).toBe('csrf-1');
    expect(claim?.headers.Authorization).toBeUndefined();
  });

  it('uses the cookie on every desk read, without a CSRF token or bearer header', async () => {
    const { calls, fetchImpl } = stubFetch(() => json(200, { conversations: [] }));
    const api = createHttpApi('/api/v1', fetchImpl);
    await api.listConversations();
    expect(calls[0]?.init.credentials).toBe('include');
    expect(calls[0]?.headers['X-CSRF-Token']).toBeUndefined();
    expect(calls[0]?.headers.Authorization).toBeUndefined();
  });

  it('restores the session from GET /desk/me after a refresh', async () => {
    const { calls, fetchImpl } = stubFetch((call) =>
      call.url.endsWith('/desk/me') ? json(200, { agent: AGENT, csrfToken: 'csrf-2' }) : json(204, null),
    );
    const api = createHttpApi('/api/v1', fetchImpl);
    expect(await api.getDeskAgent()).toEqual(AGENT);
    await api.signOutOfDesk();
    expect(calls[1]?.url).toBe('/api/v1/desk/logout');
    expect(calls[1]?.init.method).toBe('POST');
    expect(calls[1]?.headers['X-CSRF-Token']).toBe('csrf-2');
  });

  it('treats a 401 from /desk/me as signed out', async () => {
    const { fetchImpl } = stubFetch(() => json(401, { error: { code: 'unauthorized', message: 'No' } }));
    expect(await createHttpApi('/api/v1', fetchImpl).getDeskAgent()).toBeNull();
  });

  it('forgets the CSRF token after signing out', async () => {
    const { calls, fetchImpl } = stubFetch((call) =>
      call.url.endsWith('/desk/session') ? json(200, { csrfToken: 'csrf-1', agent: AGENT }) : json(204, null),
    );
    const api = createHttpApi('/api/v1', fetchImpl);
    await api.signInToDesk('a', 'b');
    await api.signOutOfDesk();
    await api.replyToConversation('cv-1', 'hello');
    expect(calls[2]?.headers['X-CSRF-Token']).toBeUndefined();
  });

  it('reloads the session once on csrf_failed, then retries with the new token', async () => {
    const { calls, fetchImpl } = stubFetch((call, index) => {
      if (index === 0) return json(403, { error: { code: 'csrf_failed', message: 'Stale' } });
      if (call.url.endsWith('/desk/me')) return json(200, { agent: AGENT, csrfToken: 'fresh' });
      return json(200, { id: 'cv-1' });
    });
    const api = createHttpApi('/api/v1', fetchImpl);
    await api.claimConversation('cv-1');
    expect(calls.map((c) => c.url.split('/').pop())).toEqual(['claim', 'me', 'claim']);
    expect(calls[2]?.headers['X-CSRF-Token']).toBe('fresh');
  });

  it('does not retry any other 403', async () => {
    const { calls, fetchImpl } = stubFetch(() =>
      json(403, { error: { code: 'approval_limit_exceeded', message: 'Needs a supervisor' } }),
    );
    const api = createHttpApi('/api/v1', fetchImpl);
    await expect(
      api.decideRefund('RF-1', { action: 'approve', note: '', version: 1 }),
    ).rejects.toMatchObject({ code: 'approval_limit_exceeded' });
    expect(calls).toHaveLength(1);
  });

  it('follows desk events with the cookie and no bearer header', async () => {
    const seen: string[] = [];
    const { calls, fetchImpl } = stubFetch(
      () =>
        new Response('event: summary.updated\ndata: {"summary":{"live":1}}\n\n', {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
    );
    const stop = createHttpApi('/api/v1', fetchImpl).subscribeDesk((event) => seen.push(event.type));
    await new Promise((resolve) => setTimeout(resolve, 20));
    stop();
    expect(seen[0]).toBe('summary.updated');
    expect(calls[0]?.init.credentials).toBe('include');
    expect(calls[0]?.headers.Authorization).toBeUndefined();
  });

  it('keeps nothing in browser storage', () => {
    const source = readFileSync('src/api/http.ts', 'utf-8');
    expect(source).not.toMatch(/sessionStorage|localStorage/);
  });
});

describe('customer calls', () => {
  it('sends the conversation token as a bearer header, with no cookie', async () => {
    const { calls, fetchImpl } = stubFetch((call) =>
      call.url.endsWith('/conversations')
        ? json(201, { id: 'cv-1', token: 'tok', locale: 'en', createdAt: '', verified: false })
        : json(200, { status: 'code_sent' }),
    );
    const api = createHttpApi('/api/v1/', fetchImpl);
    await api.createConversation('en');
    await api.startVerification('cv-1', '+97433001234');

    const start = calls[1];
    expect(start?.url).toBe('/api/v1/conversations/cv-1/verify/start');
    expect(start?.headers.Authorization).toBe('Bearer tok');
    expect(start?.init.credentials).toBeUndefined();
    expect(JSON.parse(String(start?.init.body))).toEqual({ phone: '+97433001234' });
  });

  it('posts the code to verify/confirm, never to messages', async () => {
    const { calls, fetchImpl } = stubFetch(() => json(200, { verified: true }));
    await createHttpApi('/api/v1', fetchImpl).confirmVerification('cv-1', '482913');
    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe('/api/v1/conversations/cv-1/verify/confirm');
    expect(JSON.parse(String(calls[0]?.init.body))).toEqual({ code: '482913' });
  });

  it('carries attemptsLeft from a wrong code', async () => {
    const { fetchImpl } = stubFetch(() =>
      json(400, {
        error: { code: 'invalid_code', message: 'Wrong', retryable: true, attemptsLeft: 3 },
      }),
    );
    const error = await createHttpApi('/api/v1', fetchImpl)
      .confirmVerification('cv-1', '000000')
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'invalid_code', attemptsLeft: 3 });
  });

  it('streams a reply through the parser', async () => {
    const body =
      'event: message.start\ndata: {"messageId":"m1"}\n\n' +
      'event: something.new\ndata: {}\n\n' +
      'event: identity.required\ndata: {"reason":"order_tools"}\n\n' +
      'event: message.end\ndata: {"finish":"identity_required"}\n\n';
    const { fetchImpl } = stubFetch(() => new Response(body));
    const events = [];
    const stream = createHttpApi('/api/v1', fetchImpl).sendMessage(
      'cv-1',
      { clientMessageId: 'c1', text: 'hi', locale: 'en' },
      new AbortController().signal,
    );
    for await (const event of stream) events.push(event.type);
    expect(events).toEqual(['message.start', 'identity.required', 'message.end']);
  });

  it('gives null policy when the call fails, so the UI states no limits', async () => {
    const { fetchImpl } = stubFetch(() => json(500, {}));
    expect(await createHttpApi('/api/v1', fetchImpl).getPolicy()).toBeNull();
  });
});

describe('event streams', () => {
  const answerWith = async (status: number, code: string) => {
    vi.useFakeTimers();
    const { calls, fetchImpl } = stubFetch(() =>
      json(status, { error: { code, message: 'No', retryable: status === 429 } }),
    );
    const stop = createHttpApi('/api/v1', fetchImpl).subscribeConversation('cv-1', () => undefined);
    await vi.advanceTimersByTimeAsync(1_500);
    stop();
    vi.useRealTimers();
    return calls.length;
  };

  it('tries again when the server has too many streams, because that passes', async () => {
    expect(await answerWith(429, 'too_many_streams')).toBeGreaterThan(1);
  });

  it('stops for good when the conversation has closed', async () => {
    expect(await answerWith(409, 'conversation_closed')).toBe(1);
  });

  it('stops for good when the session has ended', async () => {
    expect(await answerWith(401, 'unauthorized')).toBe(1);
  });
});

describe('helpers', () => {
  it('skips unknown events and bad JSON', () => {
    expect(parseEvent({ event: 'nope', data: '{}', id: null }, STREAM_EVENT_TYPES)).toBeNull();
    expect(parseEvent({ event: 'text.delta', data: '{bad', id: null }, STREAM_EVENT_TYPES)).toBeNull();
  });

  it('reads FastAPI default errors too', async () => {
    const error = await readError(json(404, { detail: 'Not Found' }));
    expect(error).toMatchObject({ status: 404, message: 'Not Found', retryable: false });
    expect((await readError(new Response('oops', { status: 503 }))).retryable).toBe(true);
  });

  it('backs off exponentially up to the cap', () => {
    expect([0, 1, 2, 10].map(backoffMs)).toEqual([1_000, 2_000, 4_000, 30_000]);
  });
});
