export const DESK_SECTIONS = ['live', 'refunds', 'audit', 'issues', 'quality'] as const;
export type DeskSection = (typeof DESK_SECTIONS)[number];

export type Route =
  | { page: 'chat' }
  | { page: 'desk'; section: DeskSection; id: string | null };

/** Hash routes need no server rewrite, so the site works under any GitHub Pages base path. */
export function parseRoute(hash: string): Route {
  const [page, section, id] = hash.replace(/^#\/?/, '').split('/');
  if (page !== 'desk') return { page: 'chat' };
  const known = DESK_SECTIONS.find((s) => s === section);
  return { page: 'desk', section: known ?? 'live', id: known && id ? decodeURIComponent(id) : null };
}
