import type { ApiMode, AssistantMode } from '../api/types';

export type Banner = 'demo' | 'mock' | 'replies' | null;

/** A live server can still answer in mock mode, and the page says so when it does. */
export function bannerFor(mode: ApiMode, assistant: AssistantMode | null): Banner {
  if (mode !== 'live') return mode;
  return assistant === 'mock' ? 'replies' : null;
}
