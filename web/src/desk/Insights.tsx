import { useEffect, useState } from 'react';
import { useApi } from '../App';
import type { QualityReport, QualityTile, TopIssue, WindowDays } from '../api/types';
import { useI18n } from '../i18n/context';
import { formatDays } from '../i18n/translate';
import { deltaTone } from '../lib/charts';
import { forceLtr, formatDay, formatNumber } from '../lib/format';
import { Icon } from '../ui/Icon';
import { Sparkline, TrendChart } from './Charts';
import { useDesk } from './Desk';

const RANGES: WindowDays[] = [7, 14, 30];

/** One row above the charts. The same choice scopes both Top issues and Quality. */
function RangeFilter() {
  const { t, locale } = useI18n();
  const { windowDays, setWindowDays } = useDesk();
  return (
    <div className="filters" role="group" aria-label={t('range.label')}>
      {RANGES.map((days) => (
        <button key={days} type="button" aria-pressed={windowDays === days} onClick={() => setWindowDays(days)}>
          {formatDays(locale, days)}
        </button>
      ))}
    </div>
  );
}

function ChangeBadge({
  change,
  higherIsBetter,
  text,
  verdict,
}: {
  change: number;
  higherIsBetter: boolean;
  text: string;
  /** Says better or worse in words. Down can be good, so an arrow and a colour are not enough. */
  verdict?: string;
}) {
  const tone = deltaTone(change, higherIsBetter);
  return (
    <span className={`delta delta--${tone}`}>
      {change !== 0 && <Icon name={change > 0 ? 'up' : 'down'} size={15} />}
      <bdi>{text}</bdi>
      {verdict && <span>{verdict}</span>}
    </span>
  );
}

function signed(value: number, locale: 'en' | 'ar', digits: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';
  return forceLtr(`${sign}${formatNumber(Math.abs(value), locale, digits)}`);
}

export function IssuesSection() {
  const api = useApi();
  const { t, locale } = useI18n();
  const { windowDays, handleAuth } = useDesk();
  const [issues, setIssues] = useState<TopIssue[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void api
      .getTopIssues(windowDays)
      .then((value) => {
        if (!active) return;
        setIssues(value);
        setLoading(false);
      })
      .catch((error: unknown) => {
        handleAuth(error);
      });
    return () => {
      active = false;
    };
  }, [api, handleAuth, locale, windowDays]);

  const sorted = issues?.slice().sort((a, b) => b.count - a.count) ?? [];
  const max = sorted[0]?.count ?? 1;
  const total = sorted.reduce((sum, issue) => sum + issue.count, 0);
  const days = formatDays(locale, windowDays);

  return (
    <div className={loading ? 'insight is-loading' : 'insight'}>
      <RangeFilter />
      {issues && (
        <>
          <p className="section-intro">
            {t('issues.total', { count: formatNumber(total, locale), days })}
          </p>
          <table className="issues" aria-label={t('issues.caption')}>
            <thead>
              <tr>
                <th scope="col">{t('issues.col.issue')}</th>
                <th scope="col" className="num">
                  {t('issues.col.count')}
                </th>
                <th scope="col" className="num">
                  {t('issues.col.change')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((issue) => (
                <tr key={issue.id}>
                  <td>
                    <span className="issues__label">{issue.label}</span>
                    <span className="issues__track" aria-hidden="true">
                      <span className="issues__bar" style={{ width: `${(issue.count / max) * 100}%` }} />
                    </span>
                  </td>
                  <td className="num mono">{formatNumber(issue.count, locale)}</td>
                  <td className="num">
                    <ChangeBadge
                      change={issue.changePct}
                      higherIsBetter={false}
                      text={forceLtr(`${signed(issue.changePct, locale, 0)}%`)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="fine">{t('issues.vsPrev', { days })}</p>
        </>
      )}
    </div>
  );
}

function tileValue(tile: QualityTile, locale: 'en' | 'ar'): string {
  const digits = tile.id === 'rating' || tile.unit !== 'score' ? 1 : 0;
  return `${formatNumber(tile.value, locale, digits)}${tile.unit === 'percent' ? '%' : ''}`;
}

function Delta({ tile }: { tile: QualityTile }) {
  const { t, locale } = useI18n();
  if (tile.delta === 0) return <span className="delta delta--flat">{t('quality.noChange')}</span>;
  const unit =
    tile.unit === 'percent'
      ? ` ${t('quality.unit.points')}`
      : tile.unit === 'seconds'
        ? ` ${t('quality.unit.seconds')}`
        : '';
  return (
    <ChangeBadge
      change={tile.delta}
      higherIsBetter={tile.higherIsBetter}
      text={`${signed(tile.delta, locale, 1)}${unit}`}
      verdict={t(deltaTone(tile.delta, tile.higherIsBetter) === 'good' ? 'quality.better' : 'quality.worse')}
    />
  );
}

function Tile({ tile }: { tile: QualityTile }) {
  const { t, locale } = useI18n();
  return (
    <div className="tile">
      <dt>{tile.label}</dt>
      <dd>
        <span className="tile__value">
          {tileValue(tile, locale)}
          {tile.unit === 'seconds' && <small> {t('quality.unit.secondsShort')}</small>}
        </span>
        <Delta tile={tile} />
        <Sparkline values={tile.trend} />
      </dd>
    </div>
  );
}

export function QualitySection() {
  const api = useApi();
  const { t, locale } = useI18n();
  const { windowDays, handleAuth } = useDesk();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void api
      .getQuality(windowDays)
      .then((value) => {
        if (!active) return;
        setReport(value);
        setLoading(false);
      })
      .catch((error: unknown) => {
        handleAuth(error);
      });
    return () => {
      active = false;
    };
  }, [api, handleAuth, locale, windowDays]);

  const percent = (value: number) => `${formatNumber(value, locale, 1)}%`;
  const date = (iso: string) => formatDay(iso, locale);
  const first = report?.series[0];
  const last = report?.series[report.series.length - 1];
  const values = report?.series.map((point) => point.value) ?? [];

  return (
    <div className={loading ? 'insight is-loading' : 'insight'}>
      <RangeFilter />
      {report && first && last && (
        <>
          <div className="quality__top">
            <div className="hero">
              <p className="hero__label">{report.hero.label}</p>
              <p className="hero__value">{tileValue(report.hero, locale)}</p>
              <p className="hero__delta">
                <Delta tile={report.hero} />
                <span className="muted">{t('quality.vsPrev', { days: formatDays(locale, windowDays) })}</span>
              </p>
            </div>
            <figure className="quality__chart">
              <figcaption>
                <span>{t('quality.chartTitle')}</span>
                <button type="button" className="link" onClick={() => setShowTable((open) => !open)}>
                  {t(showTable ? 'quality.hideTable' : 'quality.showTable')}
                </button>
              </figcaption>
              <TrendChart
                series={report.series}
                rtl={locale === 'ar'}
                ariaLabel={`${t('quality.chartDesc', {
                  first: percent(first.value),
                  start: date(first.date),
                  last: percent(last.value),
                  end: date(last.date),
                  high: percent(Math.max(...values)),
                  low: percent(Math.min(...values)),
                })} ${t('quality.chartHint')}`}
                formatValue={percent}
                formatDate={date}
              />
              {showTable && (
                <div className="quality__table" tabIndex={0} role="region" aria-label={t('quality.chartTitle')}>
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">{t('quality.col.day')}</th>
                        <th scope="col" className="num">
                          {t('quality.col.value')}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.series.map((point) => (
                        <tr key={point.date}>
                          <td>{date(point.date)}</td>
                          <td className="num mono">{percent(point.value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </figure>
          </div>
          <dl className="tiles">
            {report.tiles.map((tile) => (
              <Tile key={tile.id} tile={tile} />
            ))}
          </dl>
        </>
      )}
    </div>
  );
}
