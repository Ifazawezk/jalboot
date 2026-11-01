import type { LiveConversation } from '../api/types';

const RANK: Record<LiveConversation['state'], number> = {
  waiting: 0,
  agent: 1,
  bot: 2,
  closed: 3,
};

/** People waiting come first, urgent ones on top, then whoever has waited longest. */
export function sortLive(list: LiveConversation[]): LiveConversation[] {
  return list.slice().sort((a, b) => {
    const byState = RANK[a.state] - RANK[b.state];
    if (byState !== 0) return byState;
    if (a.state === 'waiting') {
      const byPriority = Number(b.priority === 'high') - Number(a.priority === 'high');
      if (byPriority !== 0) return byPriority;
      return Date.parse(a.waitingSince ?? '') - Date.parse(b.waitingSince ?? '');
    }
    return Date.parse(b.updatedAt) - Date.parse(a.updatedAt);
  });
}

export function upsertById<T extends { id: string }>(list: T[], next: T): T[] {
  return list.some((x) => x.id === next.id)
    ? list.map((x) => (x.id === next.id ? next : x))
    : [next, ...list];
}
