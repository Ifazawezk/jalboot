import { describe, expect, it } from 'vitest';
import { MOCK_RULES } from '../data/mockRules';
import { recordingsFor } from '../data/recordings';
import { chatReducer, initialChatState, type ChatAction } from '../lib/chatState';
import type { SupportApi } from './client';
import { createMockApi } from './mock';
import type { ConversationEvent, DeskEvent, StreamEvent } from './types';

const CODE = '482913';
const PHONE = '+97433001234';

function setup(): SupportApi {
  const api = createMockApi({ speed: 0, liveTicks: false, makeCode: () => CODE });
  api.setLocale('en');
  return api;
}

async function say(api: SupportApi, id: string, text: string, clientMessageId: string): Promise<StreamEvent[]> {
  const events: StreamEvent[] = [];
  const stream = api.sendMessage(id, { clientMessageId, text, locale: 'en' }, new AbortController().signal);
  for await (const event of stream) events.push(event);
  return events;
}

const types = (events: StreamEvent[]) => events.map((e) => e.type);

async function verify(api: SupportApi, id: string) {
  await api.startVerification(id, PHONE);
  await api.confirmVerification(id, CODE);
}

describe('desk honesty', () => {
  it.each(['en', 'ar'] as const)('never shows a customer photo as real (%s)', async (locale) => {
    const api = setup();
    api.setLocale(locale);
    const refunds = await api.listRefunds();
    const photos = refunds
      .flatMap((refund) => refund.evidence)
      .filter((item) => /photo|صورة/i.test(item.label));
    expect(photos.length).toBeGreaterThan(0);
    expect(photos.every((item) => item.simulated)).toBe(true);
    expect(photos.some((item) => /received|وصلت/.test(item.value))).toBe(false);
  });
});

describe('identity', () => {
  it('refuses order tools until the conversation is verified', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    const events = await say(api, id, 'Where is my order?', 'c1');
    expect(types(events)).toContain('identity.required');
    expect(types(events)).not.toContain('tool.start');
    expect(types(events)).not.toContain('order.card');
    expect(events[events.length - 1]).toMatchObject({ type: 'message.end', finish: 'identity_required' });
  });

  it('answers general questions without verifying', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    const events = await say(api, id, 'Is there a fee if I cancel?', 'c1');
    expect(types(events)).not.toContain('identity.required');
    expect(types(events)).toContain('citation');
  });

  it('never blocks a safety case behind the check', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    const events = await say(api, id, 'My son has an allergy reaction to this order', 'c1');
    expect(types(events)).not.toContain('identity.required');
    expect(types(events)).toContain('handoff.update');
  });

  it('reruns the held turn after verifying, without storing the message twice', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await say(api, id, 'Where is my order?', 'c1');
    await verify(api, id);
    const events = await say(api, id, 'Where is my order?', 'c1');
    expect(types(events)).toContain('order.card');

    const detail = await api.getConversationDetail(id);
    expect(detail.transcript.filter((e) => e.author === 'customer')).toHaveLength(1);
    expect(detail.verified).toBe(true);
  });

  it('refuses a repeat of a turn that already completed', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await say(api, id, 'Is there a fee if I cancel?', 'c1');
    await expect(say(api, id, 'Is there a fee if I cancel?', 'c1')).rejects.toMatchObject({
      status: 409,
      code: 'duplicate_message',
    });
  });

  it('includes simulatedCode and masks the number', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    const result = await api.startVerification(id, PHONE);
    expect(result.simulatedCode).toBe(CODE);
    expect(result.maskedPhone).toBe('+974 •••• 1234');
    expect(result.maskedPhone).not.toContain('3300');
  });

  it('rejects a malformed number', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await expect(api.startVerification(id, '123')).rejects.toMatchObject({ code: 'invalid_phone' });
  });

  it('counts down wrong codes, then locks at the limit in the rules', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await api.startVerification(id, PHONE);
    for (let i = 1; i < MOCK_RULES.otpMaxFailures; i += 1) {
      await expect(api.confirmVerification(id, '000000')).rejects.toMatchObject({
        code: 'invalid_code',
        attemptsLeft: MOCK_RULES.otpMaxFailures - i,
      });
    }
    await expect(api.confirmVerification(id, '000000')).rejects.toMatchObject({
      status: 429,
      code: 'too_many_attempts',
    });
    await expect(api.confirmVerification(id, CODE)).rejects.toMatchObject({ code: 'too_many_attempts' });
  });

  it('rejects a confirm with no code outstanding', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await expect(api.confirmVerification(id, CODE)).rejects.toMatchObject({ status: 410, code: 'code_expired' });
  });

  it('keeps the phone and the code out of the transcript and the audit log', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await say(api, id, 'Where is my order?', 'c1');
    await api.startVerification(id, PHONE);
    await api.confirmVerification(id, '000000').catch(() => undefined);
    await api.confirmVerification(id, CODE);
    await say(api, id, 'Where is my order?', 'c1');

    const detail = await api.getConversationDetail(id);
    const audit = await api.listAudit('all', null);
    const everything = JSON.stringify([detail, audit]);
    expect(everything).not.toContain(CODE);
    expect(everything).not.toContain('33001234');
    expect(audit.entries.some((e) => e.action === 'identity.verified')).toBe(true);
    expect(audit.entries.some((e) => e.action === 'identity.failed')).toBe(true);
  });
});

describe('tools', () => {
  it('sends a plain-language label with every tool, using the backend tool names', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await verify(api, id);
    const events = await say(api, id, 'Where is my order?', 'c1');
    const starts = events.filter((e) => e.type === 'tool.start');
    expect(starts.map((e) => e.tool)).toEqual(['track_order', 'explain_delay', 'search_knowledge']);
    for (const start of starts) expect(start.label).toMatch(/^[A-Z]/);
    expect(events.filter((e) => e.type === 'tool.end').every((e) => e.label)).toBe(true);
  });
});

describe('refunds', () => {
  async function fileRefund(api: SupportApi) {
    const { id } = await api.createConversation('en');
    await verify(api, id);
    const events = await say(api, id, 'A box of dates is missing from my order', 'c1');
    const update = events.find((e) => e.type === 'refund.update');
    if (update?.type !== 'refund.update') throw new Error('no refund');
    return { id, refund: update.refund };
  }

  it('sends a refund above the automated limit to the queue', async () => {
    const api = setup();
    const { refund } = await fileRefund(api);
    expect(refund.status).toBe('pending');
    expect(refund.amountQar).toBeGreaterThan(MOCK_RULES.refundAutomatedLimitQar);
    expect((await api.listRefunds()).some((r) => r.id === refund.id)).toBe(true);
  });

  it('tells the customer, updates the queue and writes the audit log on approval', async () => {
    const api = setup();
    const { id, refund } = await fileRefund(api);
    const customer: ConversationEvent[] = [];
    const desk: DeskEvent[] = [];
    api.subscribeConversation(id, (event) => customer.push(event));
    api.subscribeDesk((event) => desk.push(event));

    const before = (await api.getDeskSummary()).refundsPending;
    const decided = await api.decideRefund(refund.id, { action: 'approve', note: 'Store confirmed', version: 1 });
    expect(decided.status).toBe('approved');
    expect((await api.getDeskSummary()).refundsPending).toBe(before - 1);

    const update = customer.find((e) => e.type === 'refund.update');
    expect(update).toMatchObject({ refund: { id: refund.id, status: 'approved', note: null } });
    expect(desk.map((e) => e.type)).toEqual(expect.arrayContaining(['refund.updated', 'audit.appended']));
    const audit = await api.listAudit('agent', null);
    expect(audit.entries[0]).toMatchObject({ action: 'refund.approved', target: refund.id });
  });

  it('sends a rejection reason to the customer', async () => {
    const api = setup();
    const { id, refund } = await fileRefund(api);
    const customer: ConversationEvent[] = [];
    api.subscribeConversation(id, (event) => customer.push(event));
    await api.decideRefund(refund.id, { action: 'reject', note: 'The store found the item', version: 1 });
    expect(customer[0]).toMatchObject({ refund: { status: 'rejected', note: 'The store found the item' } });
  });

  it('refuses a stale version with a 409', async () => {
    const api = setup();
    const { refund } = await fileRefund(api);
    await api.decideRefund(refund.id, { action: 'approve', note: '', version: 1 });
    await expect(
      api.decideRefund(refund.id, { action: 'reject', note: 'too late now', version: 1 }),
    ).rejects.toMatchObject({ status: 409, code: 'refund_already_decided' });
  });

  it('refuses a refund above the agent limit and names who can decide it', async () => {
    const api = setup();
    const big = (await api.listRefunds()).find((r) => r.amountQar > MOCK_RULES.refundAgentLimitQar);
    expect(big).toMatchObject({ canDecide: false, requiredRole: 'supervisor' });
    await expect(
      api.decideRefund(big?.id ?? '', { action: 'approve', note: '', version: 1 }),
    ).rejects.toMatchObject({ status: 403, code: 'approval_limit_exceeded' });
  });
});

describe('handoff and desk', () => {
  it('stops automated replies once a person has taken over', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    await api.claimConversation(id);
    const events = await say(api, id, 'Hello?', 'c1');
    expect(events).toEqual([{ type: 'message.end', finish: 'forwarded' }]);
  });

  it('delivers a desk reply to the customer', async () => {
    const api = setup();
    const { id } = await api.createConversation('en');
    const seen: ConversationEvent[] = [];
    api.subscribeConversation(id, (event) => seen.push(event));
    await api.claimConversation(id);
    await api.replyToConversation(id, 'Hello from the desk');
    expect(seen.map((e) => e.type)).toEqual(['handoff.update', 'agent.message']);
  });

  it('ends a conversation for the customer and refuses later messages', async () => {
    const api = setup();
    const { id } = await api.createConversation('ar');
    const seen: ConversationEvent[] = [];
    api.subscribeConversation(id, (event) => seen.push(event));
    const closed = await api.closeConversation(id);
    expect(closed.state).toBe('closed');
    expect(seen.map((e) => e.type)).toEqual(['conversation.closed']);
    await expect(say(api, id, 'Hello?', 'c1')).rejects.toMatchObject({ code: 'conversation_closed' });
  });

  it('gives internal limits to the desk and not to the public policy', async () => {
    const api = setup();
    expect(JSON.stringify(await api.getPolicy())).not.toContain('Limit');
    expect((await api.getDeskPolicy())?.refund.automatedLimitQar).toBe(MOCK_RULES.refundAutomatedLimitQar);
  });

  it('signs out and back in', async () => {
    const api = setup();
    expect(await api.getDeskAgent()).toMatchObject({ role: 'agent' });
    await api.signOutOfDesk();
    expect(await api.getDeskAgent()).toBeNull();
    await api.signInToDesk('', '');
    expect(await api.getDeskAgent()).not.toBeNull();
  });

  it('pages and filters the audit log', async () => {
    const api = setup();
    const first = await api.listAudit('all', null);
    expect(first.entries).toHaveLength(10);
    const second = await api.listAudit('all', first.nextCursor);
    expect(second.entries[0]?.id).not.toBe(first.entries[0]?.id);
    const blocked = await api.listAudit('guardrail', null);
    expect(blocked.entries.every((e) => e.action === 'guardrail.blocked')).toBe(true);
    const bot = await api.listAudit('bot', null);
    expect(bot.entries.some((e) => e.action === 'guardrail.blocked')).toBe(false);
  });

  it('translates desk data when the language changes', async () => {
    const api = setup();
    api.setLocale('ar');
    const issues = await api.getTopIssues(7);
    expect(issues[0]?.label).toMatch(/[\u0600-\u06FF]/);
    expect(issues[0]?.count).toBeGreaterThan(issues[1]?.count ?? 0);
  });

  it('gives one quality point per day of the window', async () => {
    const api = setup();
    const report = await api.getQuality(30);
    expect(report.series).toHaveLength(30);
    expect(report.tiles.length).toBeGreaterThan(3);
  });

  it('only offers recordings in demo mode', () => {
    expect(setup().listRecordings).toBeUndefined();
    expect(createMockApi({ mode: 'demo', liveTicks: false }).listRecordings).toBeTypeOf('function');
  });
});

describe('recordings', () => {
  it.each(['en', 'ar'] as const)('play to the end through the chat reducer in %s', (locale) => {
    for (const recording of recordingsFor(locale)) {
      const state = recording.steps.reduce(
        (current, step) => chatReducer(current, step.event as ChatAction),
        initialChatState,
      );
      expect(state.streaming, recording.id).toBe(false);
      expect(state.items.some((i) => i.kind === 'bot' && i.text.length > 0), recording.id).toBe(true);
    }
  });

  it('match between languages', () => {
    const en = recordingsFor('en');
    const ar = recordingsFor('ar');
    expect(en.map((r) => r.conversationId)).toEqual(ar.map((r) => r.conversationId));
  });

  it('show the identity check on order questions, without a number or a code', () => {
    const raw = JSON.stringify(recordingsFor('en'));
    expect(raw).toContain('identity.code_sent');
    expect(raw).not.toMatch(/simulatedCode|"code"|"phone"/);
    const late = recordingsFor('ar').find((r) => r.id === 'late-order-ar');
    expect(late?.steps.some((s) => s.event.type === 'identity.verified')).toBe(true);
  });
});
