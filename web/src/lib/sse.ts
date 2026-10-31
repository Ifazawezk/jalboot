export interface SseMessage {
  event: string;
  data: string;
  id: string | null;
}

/**
 * Incremental Server-Sent Events parser. EventSource cannot POST or send an
 * Authorization header, so the client reads the stream with fetch and parses it here.
 * Follows the WHATWG rules for line endings, comments and multi-line data.
 */
export class SseParser {
  private buffer = '';
  private skipLeadingLf = false;
  private event = '';
  private data: string[] = [];
  private id: string | null = null;

  feed(chunk: string): SseMessage[] {
    const out: SseMessage[] = [];
    let text = chunk;
    if (this.skipLeadingLf && text.length > 0) {
      if (text.startsWith('\n')) text = text.slice(1);
      this.skipLeadingLf = false;
    }
    this.buffer += text;

    let start = 0;
    for (let i = 0; i < this.buffer.length; i += 1) {
      const ch = this.buffer[i];
      if (ch !== '\n' && ch !== '\r') continue;
      this.takeLine(this.buffer.slice(start, i), out);
      if (ch === '\r') {
        if (i + 1 === this.buffer.length) this.skipLeadingLf = true;
        else if (this.buffer[i + 1] === '\n') i += 1;
      }
      start = i + 1;
    }
    this.buffer = this.buffer.slice(start);
    return out;
  }

  private takeLine(line: string, out: SseMessage[]): void {
    if (line === '') {
      if (this.data.length > 0) {
        out.push({ event: this.event || 'message', data: this.data.join('\n'), id: this.id });
      }
      this.event = '';
      this.data = [];
      return;
    }
    if (line.startsWith(':')) return;
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') this.event = value;
    else if (field === 'data') this.data.push(value);
    else if (field === 'id' && !value.includes('\0')) this.id = value;
  }
}

/** Reads a byte stream into SSE messages. An event cut off by the end of the stream is dropped. */
export async function* readSse(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseMessage, void, undefined> {
  const reader = stream.getReader();
  const decoder = new TextDecoder('utf-8');
  const parser = new SseParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const message of parser.feed(decoder.decode(value, { stream: true }))) {
        yield message;
      }
    }
    for (const message of parser.feed(decoder.decode())) yield message;
  } finally {
    reader.releaseLock();
  }
}
