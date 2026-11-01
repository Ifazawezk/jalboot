import { describe, expect, it } from 'vitest';
import { recordedModel, recordingsFor, type Recording } from './recordings';

const captured: Recording = {
  id: 'en-refund',
  source: 'groq/openai/gpt-oss-20b',
  locale: 'en',
  title: 'Small refund',
  summary: 'A real run.',
  recordedAt: '2026-11-01T02:00:00Z',
  conversationId: 'rec-en-refund',
  steps: [],
};

describe('recordings', () => {
  it('puts real recordings first and keeps the scripted examples after them', () => {
    const list = recordingsFor('en', [captured]);
    expect(list[0]?.source).toBe('groq/openai/gpt-oss-20b');
    expect(list.slice(1).every((recording) => recording.source === undefined)).toBe(true);
    expect(list.length).toBeGreaterThan(1);
  });

  it('shows a recording only in its own language', () => {
    expect(recordingsFor('ar', [captured]).some((recording) => recording.id === 'en-refund')).toBe(false);
  });

  it('names the model without the provider', () => {
    expect(recordedModel(captured)).toBe('openai/gpt-oss-20b');
  });
});
