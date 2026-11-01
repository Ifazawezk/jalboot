import { describe, expect, it } from 'vitest';
import { ar } from './ar';
import { en, type MessageKey } from './en';
import { formatDays, formatMinutes, hasMessage, translate } from './translate';

const keys = Object.keys(en) as MessageKey[];
const slots = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('dictionaries', () => {
  it('have the same keys in both languages', () => {
    expect(Object.keys(ar).sort()).toEqual([...keys].sort());
  });

  it.each(keys)('%s has the same slots in both languages', (key) => {
    expect(slots(ar[key])).toEqual(slots(en[key]));
  });

  it('call the demo conversations scripted examples, not saved or recorded ones', () => {
    expect(en['mode.demo.title']).toBe('Scripted example');
    expect(en['rec.label']).toBe('Scripted example');
    expect(ar['rec.label']).toBe(ar['mode.demo.title']);
    const demoKeys = keys.filter((key) => /^(rec\.|mode\.demo\.|identity\.recorded)/.test(key));
    for (const key of demoKeys) {
      expect(en[key]).not.toMatch(/saved|recorded|recording/i);
      expect(ar[key]).not.toMatch(/محفوظ|مسجل|تسجيل/);
    }
  });

  it('have no list of tools, because labels come from the server', () => {
    expect(keys.filter((key) => key.startsWith('tool.'))).toEqual([]);
  });

  it('state no money amounts, because limits come from GET /policy', () => {
    for (const key of keys) {
      expect(en[key]).not.toMatch(/QAR\s*\d/);
      expect(ar[key]).not.toMatch(/\d+\s*(ريال|ر\.ق)/);
    }
  });

  it('state no fixed timings for refunds or reviews', () => {
    const refundKeys = keys.filter((key) => key.startsWith('refund.'));
    for (const key of refundKeys) {
      expect(en[key]).not.toMatch(/\d/);
      expect(ar[key]).not.toMatch(/\d/);
    }
  });
});

describe('translate', () => {
  it('fills slots and the brand', () => {
    expect(translate('en', 'chat.disclosure')).toContain('Jalboot');
    expect(translate('ar', 'chat.disclosure')).toContain('جالبوت');
    expect(translate('en', 'live.orderRef', { id: 'JB-1' })).toBe('Order JB-1');
  });

  it('isolates values in Arabic so a Latin id cannot reorder the sentence', () => {
    expect(translate('ar', 'live.orderRef', { id: 'JB-1' })).toContain('\u2068JB-1\u2069');
    expect(translate('en', 'live.orderRef', { id: 'JB-1' })).not.toContain('\u2068');
  });

  it('leaves an unknown slot visible instead of printing undefined', () => {
    expect(translate('en', 'live.orderRef')).toBe('Order {id}');
  });

  it('reports which audit actions have labels', () => {
    expect(hasMessage('en', 'audit.act.refund.approved')).toBe(true);
    expect(hasMessage('ar', 'audit.act.something.new')).toBe(false);
  });
});

describe('plurals', () => {
  it.each([
    [1, 'دقيقة واحدة'],
    [2, 'دقيقتان'],
    [5, '5 دقائق'],
    [11, '11 دقيقة'],
  ])('Arabic minutes for %i', (n, expected) => {
    expect(formatMinutes('ar', n)).toBe(expected);
  });

  it.each([
    [7, '7 أيام'],
    [14, '14 يومًا'],
    [30, '30 يومًا'],
  ])('Arabic days for %i', (n, expected) => {
    expect(formatDays('ar', n)).toBe(expected);
  });

  it('English', () => {
    expect(formatMinutes('en', 1)).toBe('1 minute');
    expect(formatDays('en', 7)).toBe('7 days');
  });
});
