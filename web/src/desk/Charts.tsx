import { useId, useMemo, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { areaPath, linePath, nearestIndex, niceTicks, scalePoints } from '../lib/charts';
import { useWidth } from '../ui/hooks';

const HEIGHT = 240;
const PAD = { top: 18, right: 56, bottom: 30, left: 44 };

type Anchor = 'start' | 'middle' | 'end';

export interface ChartPoint {
  date: string;
  value: number;
}

/** A single series, so no legend box: the title says what is plotted. Time follows reading direction. */
export function TrendChart({
  series,
  rtl,
  ariaLabel,
  formatValue,
  formatDate,
}: {
  series: ChartPoint[];
  rtl: boolean;
  ariaLabel: string;
  formatValue: (value: number) => string;
  formatDate: (iso: string) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const readoutId = useId();

  const values = series.map((point) => point.value);
  const ticks = useMemo(() => niceTicks(Math.min(...values), Math.max(...values), 4), [values]);
  const domain: [number, number] = [ticks[0] ?? 0, ticks[ticks.length - 1] ?? 1];
  const pad = rtl ? { ...PAD, left: PAD.right, right: PAD.left } : PAD;
  const inner = Math.max(width, 200);

  const raw = scalePoints(values, inner, HEIGHT, domain, pad);
  const points = rtl ? raw.map((p) => ({ x: inner - p.x, y: p.y })) : raw;
  const baseline = HEIGHT - PAD.bottom;
  const last = points[points.length - 1];
  const lastValue = values[values.length - 1];
  const middle = Math.floor((series.length - 1) / 2);
  const shown = active === null ? null : points[active];
  const shownPoint = active === null ? null : series[active];

  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    setActive(nearestIndex(points, event.clientX - box.left));
  };

  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    // Arrow keys move the marker the way the arrow points, in either direction of text.
    const forward = event.key === (rtl ? 'ArrowLeft' : 'ArrowRight');
    setActive((current) => {
      const from = current ?? series.length - 1;
      return Math.min(series.length - 1, Math.max(0, from + (forward ? 1 : -1)));
    });
  };

  return (
    <div className="trend" ref={ref}>
      {width > 0 && (
        <svg
          width={inner}
          height={HEIGHT}
          viewBox={`0 0 ${inner} ${HEIGHT}`}
          role="img"
          aria-label={ariaLabel}
          aria-describedby={readoutId}
          tabIndex={0}
          onPointerMove={onPointerMove}
          onPointerLeave={() => setActive(null)}
          onBlur={() => setActive(null)}
          onKeyDown={onKeyDown}
        >
          {ticks.map((tick) => {
            const y = scalePoints([tick], inner, HEIGHT, domain, pad)[0]?.y ?? 0;
            const labelX = rtl ? inner - 4 : 4;
            return (
              <g key={tick}>
                <line className="trend__grid" x1={pad.left} x2={inner - pad.right} y1={y} y2={y} />
                <text className="trend__tick" x={labelX} y={y + 4}>
                  {formatValue(tick)}
                </text>
              </g>
            );
          })}
          <path className="trend__area" d={areaPath(points, baseline)} />
          <path className="trend__line" d={linePath(points)} />
          {[0, middle, series.length - 1].map((index) => {
            const point = points[index];
            const item = series[index];
            if (!point || !item) return null;
            // SVG anchors follow the text direction, so these need no mirroring for Arabic.
            const anchor: Anchor = index === 0 ? 'start' : index === series.length - 1 ? 'end' : 'middle';
            return (
              <text key={index} className="trend__tick" x={point.x} y={HEIGHT - 8} style={{ textAnchor: anchor }}>
                {formatDate(item.date)}
              </text>
            );
          })}
          {last && lastValue !== undefined && (
            <>
              <circle className="trend__dot" cx={last.x} cy={last.y} r={4.5} />
              <text
                className="trend__end"
                x={rtl ? last.x - 10 : last.x + 10}
                y={last.y + 4}
              >
                {formatValue(lastValue)}
              </text>
            </>
          )}
          {shown && (
            <>
              <line className="trend__cross" x1={shown.x} x2={shown.x} y1={PAD.top} y2={baseline} />
              <circle className="trend__dot" cx={shown.x} cy={shown.y} r={4.5} />
            </>
          )}
          {/* A transparent layer so the whole plot answers the pointer, not just the 2px line. */}
          <rect x={0} y={0} width={inner} height={HEIGHT} fill="transparent" />
        </svg>
      )}
      {shown && shownPoint && (
        <div
          className="trend__tip"
          style={{
            insetBlockStart: Math.max(0, shown.y - 58),
            left: Math.min(Math.max(8, shown.x - 62), inner - 132),
          }}
        >
          <strong>{formatValue(shownPoint.value)}</strong>
          <span>{formatDate(shownPoint.date)}</span>
        </div>
      )}
      <p className="sr-only" id={readoutId} role="status">
        {shownPoint ? `${formatDate(shownPoint.date)}: ${formatValue(shownPoint.value)}` : ''}
      </p>
    </div>
  );
}

/** A 12 point trend beside a figure. Mirrored in Arabic, so the newest point sits at the reading end. */
export function Sparkline({ values }: { values: number[] }) {
  const width = 112;
  const height = 34;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = { top: 6, right: 6, bottom: 6, left: 2 };
  const points = scalePoints(values, width, height, [lo, hi === lo ? lo + 1 : hi], pad);
  const end = points[points.length - 1];
  return (
    <svg className="spark flip-rtl" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path className="spark__line" d={linePath(points)} />
      {end && <circle className="spark__dot" cx={end.x} cy={end.y} r={4} />}
    </svg>
  );
}
