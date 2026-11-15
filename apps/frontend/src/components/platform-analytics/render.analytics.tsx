'use client';

import { FC, useCallback, useEffect, useMemo, useRef } from 'react';
import type { Integration } from '@prisma/client';
import useSWR from 'swr';
import DrawChart from 'chart.js/auto';
import useCookie from 'react-use-cookie';
import { useFetch } from '@gitroom/helpers/utils/custom.fetch';

export interface AnalyticsDataItem {
  label: string;
  data: Array<{ total: number; date: string }>;
  average?: boolean;
  unit?: 'count' | 'minutes' | 'seconds' | 'percent';
  percentageChange?: number;
}

const labels: Record<string, string> = {
  Views: '조회수',
  'Estimated Minutes Watched': '총 시청 시간',
  'Average View Duration': '평균 시청 시간',
  'Average View Percentage': '평균 시청률',
  'Subscribers Gained': '늘어난 구독자',
  'Subscribers Lost': '줄어든 구독자',
  Likes: '좋아요',
  Impressions: '노출수', Reach: '도달수', Followers: '팔로워',
  Comments: '댓글', Shares: '공유', Engagement: '참여',
};
const reportLabels = ['Views', 'Estimated Minutes Watched', 'Average View Duration', 'Average View Percentage', 'Subscribers Gained', 'Subscribers Lost', 'Likes'];
export const koreanMetricLabel = (label: string) => labels[label] || label;
const numeric = (value: unknown): number | null => {
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  if (value === null || value === undefined || (typeof value === 'string' && value.trim() === '') || typeof value === 'boolean') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const dateKey = (date: string) => date.slice(0, 10);
const pointsByDate = (metric?: AnalyticsDataItem) =>
  new Map((metric?.data || []).map(point => [dateKey(point.date), numeric(point.total)]));

export function metricSum(metric?: AnalyticsDataItem): number | null {
  if (!metric?.data.length) return null;
  const values = metric.data.map(point => numeric(point.total));
  return values.some(value => value === null) ? null : (values as number[]).reduce((sum, value) => sum + value, 0);
}

export function weightedAverage(metric?: AnalyticsDataItem, views?: AnalyticsDataItem): number | null {
  if (!metric || !views?.data.length) return null;
  const averages = pointsByDate(metric);
  let weighted = 0;
  let count = 0;
  for (const point of views.data) {
    const weight = numeric(point.total);
    if (weight === null || weight < 0) return null;
    if (weight === 0) continue;
    const average = averages.get(dateKey(point.date));
    if (average === null || average === undefined) return null;
    weighted += average * weight;
    count += weight;
  }
  return count > 0 ? weighted / count : null;
}

export function formatCount(value: number | null, unit = ''): string {
  return value === null ? '—' : new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 0}).format(value) + unit;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds < 0) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return hours + '시간 ' + minutes + '분';
  if (minutes) return minutes + '분' + (rest ? ' ' + rest + '초' : '');
  return rest + '초';
}

export function buildAnalyticsReport(items: AnalyticsDataItem[], useStandardMetrics = true) {
  const find = (label: string) => items.find(item => item.label === label);
  const views = find('Views');
  const minutes = find('Estimated Minutes Watched');
  const gained = find('Subscribers Gained');
  const lost = find('Subscribers Lost');
  const likes = find('Likes');
  const maps = {views: pointsByDate(views), minutes: pointsByDate(minutes), gained: pointsByDate(gained), lost: pointsByDate(lost), likes: pointsByDate(likes)};
  const dates = [...new Set(Object.values(maps).flatMap(map => [...map.keys()]))].sort();
  const rows = dates.map(date => {
    const increase = maps.gained.get(date) ?? null;
    const decrease = maps.lost.get(date) ?? null;
    return {date, views: maps.views.get(date) ?? null, minutes: maps.minutes.get(date) ?? null,
      likes: maps.likes.get(date) ?? null, net: increase === null || decrease === null ? null : increase - decrease};
  });
  const gainedTotal = metricSum(gained);
  const lostTotal = metricSum(lost);
  const sameSubscriberDates = maps.gained.size > 0 && maps.gained.size === maps.lost.size &&
    [...maps.gained.keys()].every(date => maps.lost.has(date));
  return {
    rows, views: metricSum(views), minutes: metricSum(minutes), likes: metricSum(likes),
    duration: weightedAverage(find('Average View Duration'), views),
    percentage: weightedAverage(find('Average View Percentage'), views),
    gained: gainedTotal, lost: lostTotal,
    net: sameSubscriberDates && gainedTotal !== null && lostTotal !== null ? gainedTotal - lostTotal : null,
    extras: useStandardMetrics ? items.filter(item => !reportLabels.includes(item.label)) : items,
    hasStandardMetrics: useStandardMetrics && items.some(item => reportLabels.includes(item.label)),
  };
}

export const ViewsChart: FC<{rows: ReturnType<typeof buildAnalyticsReport>['rows']}> = ({rows}) => {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [mode] = useCookie('mode', 'dark');
  const points = rows;
  const hasData = points.some(row => row.views !== null);
  const hasPositiveViews = points.some(row => (row.views || 0) > 0);
  useEffect(() => {
    if (!canvas.current || !hasData) return;
    const foreground = mode === 'dark' ? '#c6c6ca' : '#4b4b55';
    const grid = mode === 'dark' ? '#343439' : '#e2e2e8';
    const chart = new DrawChart(canvas.current, {
      type: 'line',
      data: {
        labels: points.map(point => point.date.slice(5).replace('-', '/')),
        datasets: [{label: '조회수', data: points.map(point => point.views), borderColor: '#8b6cef',
          backgroundColor: '#8b6cef', borderWidth: 2, pointRadius: points.length === 1 ? 4 : 2,
          pointHoverRadius: 5, tension: 0, spanGaps: false, fill: false}],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: {mode: 'index', intersect: false},
        scales: {
          x: {grid: {display: false}, ticks: {color: foreground, maxTicksLimit: 7, maxRotation: 0}},
          y: {beginAtZero: true, suggestedMax: hasPositiveViews ? undefined : 1, grid: {color: grid}, ticks: {color: foreground, precision: 0, maxTicksLimit: 5}},
        },
        plugins: {
          legend: {display: false},
          tooltip: {displayColors: false, callbacks: {label: context => '조회수 ' + formatCount(numeric(context.parsed.y), '회')}},
        },
      },
    });
    return () => chart.destroy();
  }, [points, hasData, hasPositiveViews, mode]);
  if (!hasData) return <div className="flex min-h-32 flex-col justify-center gap-2 rounded-lg bg-newTableHeader p-6">
    <p className="font-medium text-newTableText">일별 조회 데이터가 아직 없습니다.</p>
    <p className="text-sm leading-6 text-newTableText">기간을 바꾸어 확인해 보세요. 새 활동이 통계에 반영되기까지 시간이 걸릴 수 있습니다.</p>
  </div>;
  return <div className="h-64 min-w-0"><canvas ref={canvas} role="img" aria-label="날짜별 조회수 추이. 정확한 값은 아래 일별 상세 통계에서 확인할 수 있습니다." /></div>;
};

const sectionTitle = 'text-base font-semibold text-newTableText';
const actionStyle = 'inline-flex min-h-11 items-center justify-center rounded-lg border border-newTableBorder bg-newTableHeader px-4 text-sm font-medium text-newTableText transition-colors hover:bg-boxHover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-wait disabled:opacity-60';

const ValueRow: FC<{label: string; value: string; note?: string}> = ({label, value, note}) =>
  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-newTableBorder py-3 last:border-0">
    <dt className="text-sm leading-6 text-newTableText">{label}{note && <span className="block text-xs">{note}</span>}</dt>
    <dd className="text-xl font-semibold tabular-nums text-newTableText">{value}</dd>
  </div>;

export const RenderAnalytics: FC<{integration: Integration; date: number}> = ({integration, date}) => {
  const fetch = useFetch();
  const load = useCallback(async () => {
    const response = await fetch('/analytics/' + integration.id + '?date=' + date);
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || '통계를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
    if (!Array.isArray(result)) throw new Error('통계 응답을 확인할 수 없습니다.');
    return result as AnalyticsDataItem[];
  }, [integration, date]);
  const {data, error, isLoading, isValidating, mutate} = useSWR('/analytics-' + integration.id + '-' + date, load, {
    shouldRetryOnError: false, refreshInterval: 0, refreshWhenHidden: false,
    revalidateOnFocus: false, revalidateOnReconnect: false, revalidateIfStale: false,
    refreshWhenOffline: false, revalidateOnMount: true,
  });
  const isYouTube = integration.providerIdentifier === 'youtube' || (integration as Integration & {identifier?: string}).identifier === 'youtube';
  const report = useMemo(() => buildAnalyticsReport(data || [], isYouTube), [data, isYouTube]);
  const refresh = () => { void mutate().catch(() => undefined); };
  if (isLoading) return <div role="status" aria-label="통계를 불러오는 중" className="animate-pulse space-y-6 motion-reduce:animate-none">
    <div className="h-24 rounded-lg bg-newTableHeader" /><div className="h-64 rounded-lg bg-newTableHeader" />
  </div>;
  if (error || !data?.length) return <section role={error ? 'alert' : 'status'} className="space-y-4 rounded-lg border border-newTableBorder p-6">
    <h3 className={sectionTitle}>{error ? '통계를 불러오지 못했습니다' : '집계된 통계가 아직 없습니다'}</h3>
    <p className="text-sm leading-6 text-newTableText">{error?.message || '선택한 채널과 기간에 데이터가 있는지 확인하거나 다른 기간을 선택해 주세요.'}</p>
    <button type="button" className={actionStyle} onClick={refresh} disabled={isValidating}>{isValidating ? '불러오는 중…' : '다시 불러오기'}</button>
  </section>;
  const actualDates = report.rows;
  const range = actualDates.length ? actualDates[0].date.replace(/-/g, '.') + ' ~ ' + actualDates[actualDates.length - 1].date.replace(/-/g, '.') : null;
  const sectionId = 'channel-report-' + integration.id;
  return <div className="min-w-0 space-y-8" aria-busy={isValidating}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm leading-6 text-newTableText">{range ? '집계된 날짜 ' + range : '선택한 기간의 통계'}<span className="block text-xs">최근 활동은 집계 시점에 따라 아직 반영되지 않을 수 있습니다.</span></p>
      <button type="button" className={actionStyle} onClick={refresh} disabled={isValidating}>{isValidating ? '불러오는 중…' : '새로고침'}</button>
    </div>
    {report.hasStandardMetrics && <>
      <section aria-labelledby={sectionId + '-summary'} className="space-y-3">
        <h3 id={sectionId + '-summary'} className={sectionTitle}>성과 요약</h3>
        <dl className="grid grid-cols-1 divide-y divide-newTableBorder rounded-lg border border-newTableBorder bg-newTableHeader sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[['조회수', formatCount(report.views, '회')], ['총 시청 시간', formatDuration(report.minutes === null ? null : report.minutes * 60)], ['좋아요', formatCount(report.likes, '개')]].map(([label, value]) =>
            <div key={label} className="min-w-0 space-y-2 p-5"><dt className="text-sm text-newTableText">{label}</dt><dd className="break-words text-2xl font-semibold tabular-nums leading-tight text-newTableText">{value}</dd></div>)}
        </dl>
      </section>
      <div className="grid min-w-0 grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1.7fr)_minmax(220px,1fr)]">
        <section aria-labelledby={sectionId + '-views'} className="min-w-0 space-y-4">
          <div><h3 id={sectionId + '-views'} className={sectionTitle}>일별 조회수</h3><p className="mt-1 text-xs text-newTableText">날짜별 실제 집계 · 단위: 회</p></div>
          <ViewsChart rows={report.rows} />
        </section>
        <div className="min-w-0 space-y-6">
          <section aria-labelledby={sectionId + '-quality'}>
            <h3 id={sectionId + '-quality'} className={sectionTitle}>시청 품질</h3>
            <dl><ValueRow label="평균 시청 시간" value={formatDuration(report.duration)} />
              <ValueRow label="평균 시청률" value={report.percentage === null ? '—' : new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 1}).format(report.percentage) + '%'} /></dl>
            <p className="mt-2 text-xs leading-5 text-newTableText">조회수로 가중 계산합니다. 조회수나 필요한 값이 없으면 —로 표시합니다.</p>
          </section>
          <section aria-labelledby={sectionId + '-subscribers'}>
            <h3 id={sectionId + '-subscribers'} className={sectionTitle}>구독자 변화</h3>
            <dl><ValueRow label="늘어난 구독자" value={formatCount(report.gained, '명')} />
              <ValueRow label="줄어든 구독자" value={formatCount(report.lost, '명')} />
              <ValueRow label="구독자 순증감" value={report.net === null ? '—' : (report.net > 0 ? '+' : '') + formatCount(report.net, '명')} /></dl>
          </section>
        </div>
      </div>
      {!!report.rows.length && <details className="group border-t border-newTableBorder pt-5">
        <summary className="w-fit cursor-pointer rounded font-semibold text-newTableText focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary">일별 상세 통계 <span className="ml-2 text-sm font-normal">{report.rows.length}일</span></summary>
        <div className="mt-4 overflow-x-auto rounded-lg border border-newTableBorder" tabIndex={0} role="region" aria-label="일별 상세 통계 표">
          <table className="w-full min-w-[540px] border-collapse text-right text-sm tabular-nums text-newTableText">
            <caption className="sr-only">{integration.name} 최근 {date}일 일별 조회수, 시청 시간, 좋아요, 구독자 순증감</caption>
            <thead className="bg-newTableHeader"><tr>{['날짜', '조회수', '시청 시간', '좋아요', '구독자 순증감'].map(label => <th key={label} scope="col" className="whitespace-nowrap px-4 py-3 font-medium first:text-left">{label}</th>)}</tr></thead>
            <tbody>{report.rows.map(row => <tr key={row.date} className="border-t border-newTableBorder">
              <th scope="row" className="whitespace-nowrap px-4 py-3 text-left font-normal">{row.date.replace(/-/g, '.')}</th>
              <td className="px-4 py-3">{formatCount(row.views, '회')}</td><td className="whitespace-nowrap px-4 py-3">{formatDuration(row.minutes === null ? null : row.minutes * 60)}</td>
              <td className="px-4 py-3">{formatCount(row.likes, '개')}</td><td className="px-4 py-3">{row.net === null ? '—' : (row.net > 0 ? '+' : '') + formatCount(row.net, '명')}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </details>}
    </>}
    {!!report.extras.length && <section className="space-y-3"><h3 className={sectionTitle}>기타 지표</h3><dl>{report.extras.map(item => {
      const total = metricSum(item);
      const value = item.average && total !== null && item.data.length ? total / item.data.length : total;
      const formatted = value === null ? '—' : item.unit === 'seconds' ? formatDuration(value) : item.unit === 'minutes' ? formatDuration(value * 60) : new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 2}).format(value) + (item.unit === 'percent' || (item.average && !item.unit) ? '%' : '');
      return <ValueRow key={item.label} label={koreanMetricLabel(item.label)} value={formatted} note={item.average ? '일별 수치의 평균' : undefined} />;
    })}</dl></section>}
  </div>;
};
