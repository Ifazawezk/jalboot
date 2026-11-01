const PATHS = {
  send: 'M4 12h15M13 6l6 6-6 6',
  back: 'M20 12H5M11 6l-6 6 6 6',
  chevron: 'M9 6l6 6-6 6',
  down: 'M12 5v14M6 13l6 6 6-6',
  up: 'M12 19V5M6 11l6-6 6 6',
  stop: 'M7 7h10v10H7z',
  check: 'M5 13l4 4L19 7',
  x: 'M6 6l12 12M18 6L6 18',
  alert: 'M12 4l9 16H3zM12 10v4M12 17h.01',
  clock: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2',
  person: 'M12 12a4 4 0 100-8 4 4 0 000 8zM5 20c1-4 4-6 7-6s6 2 7 6',
  shield: 'M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6zM9 12l2 2 4-4',
  sun: 'M12 16a4 4 0 100-8 4 4 0 000 8zM12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4',
  moon: 'M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z',
  play: 'M8 5l11 7-11 7z',
  skip: 'M6 5l9 7-9 7zM18 5v14',
  flag: 'M6 21V4h11l-2 4 2 4H6',
  list: 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
  chat: 'M4 5h16v11H9l-5 4z',
  receipt: 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6',
  bars: 'M4 6h16M4 12h10M4 18h6',
  pulse: 'M3 12h4l3-7 4 14 3-7h4',
  signOut: 'M10 4H5v16h5M15 8l4 4-4 4M19 12H10',
} as const;

export type IconName = keyof typeof PATHS;

/** Decorative by default. Set `flip` on icons that point along the reading direction. */
export function Icon({ name, flip = false, size = 20 }: { name: IconName; flip?: boolean; size?: number }) {
  return (
    <svg
      className={flip ? 'icon flip-rtl' : 'icon'}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/** A jalboot in two shapes: hull and lateen sail. The sail takes the accent colour. */
export function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg className="brandmark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <path d="M3 21.5h26l-4.2 6.5H8.2z" fill="currentColor" />
      <path
        d="M15 18.5V3.5c5.4 3 9.4 8.2 11 15z"
        fill="var(--accent)"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}
