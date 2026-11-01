import { describe, expect, it } from 'vitest';
import type { RefundSummary } from '../api/types';
import {
  chatReducer,
  collectSources,
  identityOpen,
  initialChatState,
  lastSpokenText,
  type BotItem,
  type ChatAction,
  type ChatState,
} from './chatState';

const run = (actions: ChatAction[], from: ChatState = initialChatState) =>
  actions.reduce(chatReducer, from);

const bot = (state: ChatState): BotItem => {
  const item = state.items.find((i) => i.kind === 'bot');
  if (item?.kind !== 'bot') throw new Error('no bot item');
  return item;
};

const refund: RefundSummary = {
  id: 'RF-1',
  orderId: 'JB-1',
  amountQar: 62.5,
  status: 'pending',
  decidedBy: null,
  note: null,
  destination: 'original',
};

describe('chatReducer streaming', () => {
  it('builds a reply from deltas and closes it', () => {
    const state = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'text.delta', delta: 'Hello ' },
      { type: 'text.delta', delta: 'there' },
      { type: 'message.end', finish: 'complete' },
    ]);
    expect(bot(state).text).toBe('Hello there');
    expect(bot(state).status).toBe('complete');
    expect(state.streaming).toBe(false);
  });

  it('shows the label from tool.start for any tool, and tool.end can replace it', () => {
    const running = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'tool.start', toolCallId: 't1', tool: 'a_tool_added_next_year', label: 'Checking something new' },
    ]);
    expect(bot(running).tools[0]).toMatchObject({ label: 'Checking something new', status: 'running' });
    const done = chatReducer(running, {
      type: 'tool.end',
      toolCallId: 't1',
      status: 'ok',
      label: 'Checked something new',
    });
    expect(bot(done).tools[0]).toMatchObject({ label: 'Checked something new', status: 'ok' });
  });

  it('keeps the start label when tool.end sends none', () => {
    const state = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'tool.start', toolCallId: 't1', tool: 'track_order', label: 'Checking your order' },
      { type: 'tool.end', toolCallId: 't1', status: 'error' },
    ]);
    expect(bot(state).tools[0]).toMatchObject({ label: 'Checking your order', status: 'error' });
  });

  it('ignores a repeated message.start', () => {
    const state = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'message.start', messageId: 'm1' },
    ]);
    expect(state.items).toHaveLength(1);
  });

  it('opens a new reply when a finished message ID runs again after the identity check', () => {
    const state = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'identity.required', reason: 'order_tools' },
      { type: 'text.delta', delta: 'I need to confirm it is you.' },
      { type: 'message.end', finish: 'identity_required' },
      { type: 'identity.verified' },
      { type: 'message.start', messageId: 'm1' },
      { type: 'text.delta', delta: 'Your order is on the way.' },
      { type: 'message.end', finish: 'complete' },
    ]);
    const bots = state.items.filter((item): item is BotItem => item.kind === 'bot');
    expect(bots.map((item) => item.text)).toEqual([
      'I need to confirm it is you.',
      'Your order is on the way.',
    ]);
    expect(new Set(state.items.map((item) => item.id)).size).toBe(state.items.length);
    expect(state.streaming).toBe(false);
  });

  it('leaves no empty reply when a message is forwarded to a person', () => {
    const withStart = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'message.end', finish: 'forwarded' },
    ]);
    expect(withStart.items).toEqual([]);
    expect(withStart.streaming).toBe(false);
    expect(run([{ type: 'message.end', finish: 'forwarded' }]).items).toEqual([]);
  });

  it('marks unfinished tools when a reply is stopped or fails', () => {
    const open: ChatAction[] = [
      { type: 'message.start', messageId: 'm1' },
      { type: 'tool.start', toolCallId: 't1', tool: 'x', label: 'x' },
    ];
    expect(bot(run([...open, { type: 'turn.stopped' }])).tools[0]?.status).toBe('ok');
    const failed = run([...open, { type: 'turn.failed', message: 'Dropped', retryable: true }]);
    expect(bot(failed).tools[0]?.status).toBe('error');
    expect(bot(failed).retryable).toBe(true);
  });

  it('shows a failure that happens before the reply opens', () => {
    const state = run([{ type: 'turn.failed', message: 'No network', retryable: true }]);
    expect(bot(state)).toMatchObject({ status: 'failed', errorMessage: 'No network' });
  });
});

describe('chatReducer identity', () => {
  it('moves from phone to code to verified', () => {
    const asked = run([{ type: 'identity.required', reason: 'order_tools' }]);
    expect(asked.identity).toBe('phone');
    expect(identityOpen(asked.identity)).toBe(true);

    const sent = chatReducer(asked, { type: 'identity.code_sent', maskedPhone: '+974 •••• 1234' });
    expect(sent.identity).toBe('code');
    expect(identityOpen(sent.identity)).toBe(true);

    const done = chatReducer(sent, { type: 'identity.verified' });
    expect(done.identity).toBe('verified');
    expect(done.maskedPhone).toBeNull();
    expect(identityOpen(done.identity)).toBe(false);
  });

  it('unlocks the chat box when cancelled, and asks again next time', () => {
    const cancelled = run([{ type: 'identity.required', reason: 'x' }, { type: 'identity.cancelled' }]);
    expect(identityOpen(cancelled.identity)).toBe(false);
    expect(chatReducer(cancelled, { type: 'identity.required', reason: 'x' }).identity).toBe('phone');
  });

  it('stays verified if the event repeats', () => {
    const state = run([{ type: 'identity.verified' }, { type: 'identity.required', reason: 'x' }]);
    expect(state.identity).toBe('verified');
  });

  it('adds no customer message at any step, so nothing typed can reach the transcript', () => {
    const state = run([
      { type: 'identity.required', reason: 'x' },
      { type: 'identity.code_sent', maskedPhone: '+974 •••• 1234' },
      { type: 'identity.verified' },
    ]);
    expect(state.items.filter((i) => i.kind === 'customer')).toEqual([]);
  });
});

describe('chatReducer conversation events', () => {
  it('updates a refund card in place and adds one notice when decided', () => {
    const open = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'refund.update', refund },
      { type: 'message.end', finish: 'complete' },
    ]);
    const approved: ChatAction = {
      type: 'refund.update',
      refund: { ...refund, status: 'approved', decidedBy: 'Noor' },
    };
    const state = run([approved, approved], open);
    expect(bot(state).refunds).toHaveLength(1);
    expect(bot(state).refunds[0]?.status).toBe('approved');
    expect(state.items.filter((i) => i.kind === 'notice')).toHaveLength(1);
  });

  it('adds one notice per handoff stage', () => {
    const queued: ChatAction = {
      type: 'handoff.update',
      handoff: { status: 'queued', agentName: null, etaMinutes: 2, position: 1 },
    };
    const joined: ChatAction = {
      type: 'handoff.update',
      handoff: { status: 'joined', agentName: 'Noor', etaMinutes: null, position: null },
    };
    const state = run([queued, queued, joined, joined]);
    expect(state.items.filter((i) => i.kind === 'notice')).toHaveLength(2);
    expect(state.handoff?.agentName).toBe('Noor');
  });

  it('de-duplicates agent messages on reconnect', () => {
    const message: ChatAction = {
      type: 'agent.message',
      messageId: 'a1',
      agentName: 'Noor',
      text: 'Hello',
      at: '2026-11-02T10:00:00Z',
    };
    expect(run([message, message]).items).toHaveLength(1);
  });
});

describe('helpers', () => {
  it('lists each source once', () => {
    const citation = { n: 1, sourceId: 's', title: 't', section: 'x', excerpt: 'e', updatedAt: '' };
    const state = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'citation', citation },
      { type: 'citation', citation: { ...citation, n: 2 } },
    ]);
    expect(collectSources(state.items)).toHaveLength(1);
  });

  it('speaks finished replies without markers, and nothing while streaming', () => {
    const streaming = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'text.delta', delta: 'On the way [1].' },
    ]);
    expect(lastSpokenText(streaming.items)).toBeNull();
    const done = chatReducer(streaming, { type: 'message.end', finish: 'complete' });
    expect(lastSpokenText(done.items)).toBe('On the way.');
  });
});

describe('asking for a person', () => {
  it('says so when the request failed, and leaves the way to ask again open', () => {
    const state = run([{ type: 'handoff.failed' }]);
    expect(state.items).toMatchObject([{ kind: 'notice', notice: 'handoff_failed' }]);
    expect(state.handoff).toBeNull();
  });

  it('does not end a reply that is still being written', () => {
    const state = run([
      { type: 'message.start', messageId: 'm1' },
      { type: 'text.delta', delta: 'Hello' },
      { type: 'handoff.failed' },
    ]);
    expect(bot(state).status).toBe('streaming');
    expect(state.streaming).toBe(true);
  });

  it('gives each failed try its own line', () => {
    const state = run([{ type: 'handoff.failed' }, { type: 'handoff.failed' }]);
    expect(new Set(state.items.map((item) => item.id)).size).toBe(2);
  });
});
