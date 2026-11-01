import type { SupportApi } from './client';

/** Each mode is its own chunk, so a live build ships no sample data. */
export async function loadApi(): Promise<SupportApi> {
  if (import.meta.env.VITE_API_MODE === 'live') {
    const { createHttpApi } = await import('./http');
    return createHttpApi(import.meta.env.VITE_API_BASE ?? '/api/v1');
  }
  const { createMockApi } = await import('./mock');
  return createMockApi({ mode: import.meta.env.VITE_API_MODE === 'demo' ? 'demo' : 'mock' });
}
