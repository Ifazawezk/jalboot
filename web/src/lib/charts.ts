export interface Point {
  x: number;
  y: number;
}

/** Rounds a span out to steps of 1, 2 or 5 so axis labels stay clean. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const rough = (max - min) / Math.max(1, count - 1);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const ratio = rough / magnitude;
  const step = (ratio <= 1 ? 1 : ratio <= 2 ? 2 : ratio <= 5 ? 5 : 10) * magnitude;
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= end + step / 2; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

export interface Padding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export function scalePoints(
  values: number[],
  width: number,
  height: number,
  domain: [number, number],
  pad: Padding = { top: 0, right: 0, bottom: 0, left: 0 },
): Point[] {
  const [lo, hi] = domain;
  const span = hi - lo || 1;
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const last = Math.max(1, values.length - 1);
  return values.map((value, i) => ({
    x: pad.left + (i / last) * innerW,
    y: pad.top + (1 - (value - lo) / span) * innerH,
  }));
}

export function linePath(points: Point[]): string {
  return points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');
}

export function areaPath(points: Point[], baseline: number): string {
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return '';
  return `${linePath(points)} L${last.x.toFixed(2)} ${baseline} L${first.x.toFixed(2)} ${baseline} Z`;
}

export function nearestIndex(points: Point[], x: number): number {
  let best = 0;
  let bestGap = Number.POSITIVE_INFINITY;
  points.forEach((p, i) => {
    const gap = Math.abs(p.x - x);
    if (gap < bestGap) {
      best = i;
      bestGap = gap;
    }
  });
  return best;
}

/** Whether a change is good, bad or flat for a metric. */
export function deltaTone(delta: number, higherIsBetter: boolean): 'good' | 'bad' | 'flat' {
  if (delta === 0) return 'flat';
  return delta > 0 === higherIsBetter ? 'good' : 'bad';
}
