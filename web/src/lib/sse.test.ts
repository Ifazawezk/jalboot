import { describe, expect, it } from 'vitest';
import { readSse, SseParser } from './sse';

function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const out = [];
  for await (const message of readSse(stream)) out.push(message);
  return out;
}

describe('SseParser', () => {
  it('parses an event split across chunks', () => {
    const parser = new SseParser();
    expect(parser.feed('event: text.de')).toEqual([]);
    expect(parser.feed('lta\ndata: {"delta":"hi"}\n')).toEqual([]);
    expect(parser.feed('\n')).toEqual([{ event: 'text.delta', data: '{"delta":"hi"}', id: null }]);
  });

  it('handles CRLF, including a CR and LF that land in different chunks', () => {
    const parser = new SseParser();
    const first = parser.feed('data: a\r');
    const second = parser.feed('\n\r\n');
    expect([...first, ...second]).toEqual([{ event: 'message', data: 'a', id: null }]);
  });

  it('joins multi-line data, skips comments and keeps the id', () => {
    const parser = new SseParser();
    const out = parser.feed(': ping\nid: 7\ndata: one\ndata: two\n\n');
    expect(out).toEqual([{ event: 'message', data: 'one\ntwo', id: '7' }]);
  });

  it('ignores an event with no data', () => {
    expect(new SseParser().feed('event: nothing\n\n')).toEqual([]);
  });
});

describe('readSse', () => {
  it('keeps Arabic intact when a chunk ends in the middle of a character', async () => {
    const bytes = new TextEncoder().encode('data: {"delta":"طلبك"}\n\n');
    const middle = bytes.indexOf(0xd8) + 1;
    const out = await collect(streamOf([bytes.slice(0, middle), bytes.slice(middle)]));
    expect(out[0]?.data).toBe('{"delta":"طلبك"}');
  });

  it('drops an event cut off by the end of the stream', async () => {
    const bytes = new TextEncoder().encode('data: whole\n\ndata: cut');
    const out = await collect(streamOf([bytes]));
    expect(out.map((m) => m.data)).toEqual(['whole']);
  });
});
