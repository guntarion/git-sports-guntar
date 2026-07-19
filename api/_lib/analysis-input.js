// Assembles the numbers an on-demand analysis reasons over.
//
// Aggregated, never dumped: a 180-day HRV series becomes first/last/mean plus a
// recent-vs-baseline trend. The model needs enough to spot relationships, not a
// database export — and every extra row is prompt budget spent on noise.
import { query } from './db.js';

const round = (v, d = 1) => (v === null || v === undefined ? null : Number(Number(v).toFixed(d)));

function stats(rows) {
  const vals = rows.map((r) => Number(r.value)).filter((v) => Number.isFinite(v));
  if (!vals.length) return null;
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const half = Math.floor(vals.length / 2);
  const firstHalf = vals.slice(0, half);
  const lastHalf = vals.slice(half);
  const avg = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null);
  return {
    n: vals.length,
    first: round(vals[0], 2),
    latest: round(vals[vals.length - 1], 2),
    mean: round(mean, 2),
    min: round(Math.min(...vals), 2),
    max: round(Math.max(...vals), 2),
    // Direction over the window, which is what a "why did it change" question
    // actually turns on.
    early_avg: round(avg(firstHalf), 2),
    late_avg: round(avg(lastHalf), 2),
    change: round((avg(lastHalf) ?? 0) - (avg(firstHalf) ?? 0), 2),
  };
}

const METRICS = [
  'vo2max', 'endurance_score', 'hrv', 'hill_score', 'resting_hr', 'sleep_hours',
  'spo2_avg', 'body_battery_charged', 'stress_weekly', 'training_readiness',
  'recovery_time_min', 'acute_load', 'training_load_weekly', 'recovery_balance',
  'endurance_vo2_ratio', 'steps',
];

export async function buildAnalysisInput(days) {
  const from = days > 0
    ? new Date(Date.now() - days * 864e5).toISOString().slice(0, 10)
    : '2000-01-01';
  const to = new Date().toISOString().slice(0, 10);

  const [pm, re, der, be, singles, ze] = await Promise.all([
    query(
      `SELECT metric, date, value FROM performance_metrics
        WHERE date BETWEEN $1 AND $2 AND value IS NOT NULL AND metric = ANY($3)
        ORDER BY metric, date`,
      [from, to, METRICS]
    ),
    query(
      `SELECT date, re_ml_kg_km, re_rolling, rating, efficiency_index, cardiac_cost,
              vertical_ratio, window_hr, window_pace_secs_per_km, total_distance_m
         FROM running_economy WHERE date BETWEEN $1 AND $2 ORDER BY date`,
      [from, to]
    ),
    query(
      `SELECT date, decoupling_pct, trimp FROM activity_derived
        WHERE date BETWEEN $1 AND $2 ORDER BY date`,
      [from, to]
    ),
    query(
      `SELECT DISTINCT ON (distance_key) distance_key, duration_s, activity_name, date
         FROM best_efforts ORDER BY distance_key, duration_s ASC`
    ),
    query(
      `SELECT DISTINCT ON (metric) metric, date, value, extra FROM performance_metrics
        WHERE metric IN ('acwr','chronic_load','training_status_phrase','race_predictions',
                         'lactate_threshold_hr')
        ORDER BY metric, date DESC`
    ),
    query(
      `SELECT extra FROM performance_metrics WHERE metric='zone_efficiency'
        ORDER BY date DESC LIMIT 1`
    ),
  ]);

  // ── Metric series → compact stats ──
  const byMetric = {};
  for (const r of pm.rows) (byMetric[r.metric] ||= []).push(r);
  const metrics = {};
  for (const [k, rows] of Object.entries(byMetric)) {
    const s = stats(rows);
    if (s) metrics[k] = s;
  }

  // ── Running economy ──
  const reRows = re.rows;
  const economy = reRows.length ? {
    unit: 'ml O2/kg/km — LOWER is better',
    n_runs: reRows.length,
    ...stats(reRows.map((r) => ({ value: r.re_ml_kg_km }))),
    latest_rating: reRows[reRows.length - 1].rating,
    rolling_latest: round(reRows[reRows.length - 1].re_rolling),
    // The inputs RE is derived from, so the model can attribute a change to
    // pace or to heart rate rather than guessing.
    window_hr: stats(reRows.map((r) => ({ value: r.window_hr }))),
    window_pace_secs_per_km: stats(reRows.map((r) => ({ value: r.window_pace_secs_per_km }))),
    efficiency_index: stats(reRows.map((r) => ({ value: r.efficiency_index }))),
    cardiac_cost: stats(reRows.map((r) => ({ value: r.cardiac_cost }))),
    vertical_ratio: stats(reRows.map((r) => ({ value: r.vertical_ratio }))),
    series: reRows.map((r) => ({
      date: r.date instanceof Date ? r.date.toISOString().slice(0, 10) : r.date,
      re: round(r.re_ml_kg_km),
      hr: round(r.window_hr),
      pace: round(r.window_pace_secs_per_km),
      km: round((r.total_distance_m || 0) / 1000, 1),
    })),
  } : null;

  const decRows = der.rows.filter((r) => r.decoupling_pct !== null);
  const decoupling = decRows.length ? {
    note: 'first-half vs second-half efficiency drift; under 5% = aerobically sound',
    ...stats(decRows.map((r) => ({ value: r.decoupling_pct }))),
    series: decRows.map((r) => ({
      date: r.date instanceof Date ? r.date.toISOString().slice(0, 10) : r.date,
      pct: round(r.decoupling_pct, 2),
    })),
  } : null;

  const singleMap = {};
  for (const r of singles.rows) {
    singleMap[r.metric] = { value: r.value === null ? null : Number(r.value), extra: r.extra };
  }

  return {
    period: { from, to, days: days || 'all' },
    metrics,
    running_economy: economy,
    aerobic_decoupling: decoupling,
    training_load_now: {
      acute: singleMap.acute_load?.value ?? metrics.acute_load?.latest ?? null,
      chronic: singleMap.chronic_load?.value ?? null,
      acwr: singleMap.acwr?.value ?? null,
      acwr_status: singleMap.acwr?.extra?.status ?? null,
    },
    garmin_training_status: singleMap.training_status_phrase?.extra?.phrase ?? null,
    lactate_threshold_hr: singleMap.lactate_threshold_hr?.value ?? null,
    race_predictions_seconds: singleMap.race_predictions?.extra ?? null,
    best_efforts_seconds: Object.fromEntries(
      be.rows.map((r) => [r.distance_key, {
        seconds: Math.round(Number(r.duration_s)),
        session: r.activity_name,
        date: r.date instanceof Date ? r.date.toISOString().slice(0, 10) : r.date,
      }])
    ),
    efficiency_by_hr_zone: ze.rows[0]?.extra
      ? Object.fromEntries(Object.entries(ze.rows[0].extra).map(([k, v]) => [k, v.ei]))
      : null,
  };
}

// Cheap change detector so the UI can mark a cached analysis stale without
// calling the model again.
export function fingerprint(input) {
  const bits = [
    input.period.days,
    input.running_economy?.n_runs,
    input.running_economy?.latest,
    input.metrics?.hrv?.latest,
    input.metrics?.sleep_hours?.latest,
    input.metrics?.vo2max?.latest,
    input.training_load_now?.acute,
  ];
  return bits.map((b) => (b === undefined || b === null ? '-' : b)).join(':');
}
