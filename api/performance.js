// /api/performance — time-series performance data for the Performance page.
//
//   GET /api/performance?from=YYYY-MM-DD&to=YYYY-MM-DD
//     -> { metrics: {vo2max:[{date,value,extra}], ...}, running_economy:[...],
//          summary: {...} }
//
// Public read, matching the rest of the dashboard (heatmap, activities), with
// one exception: body weight is personal and is only returned to an
// authenticated caller. Journal/todos remain fully auth-gated elsewhere.
import { query } from './_lib/db.js';
import { isAuthed, sendJson } from './_lib/http.js';

const PRIVATE_METRICS = new Set(['weight_kg']);

function isDate(s) {
  return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s);
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return sendJson(res, 405, { error: 'method not allowed' });

  try {
    const url = new URL(req.url, 'http://x');
    const from = isDate(url.searchParams.get('from')) ? url.searchParams.get('from') : '2000-01-01';
    const to = isDate(url.searchParams.get('to')) ? url.searchParams.get('to') : '2999-12-31';
    const authed = isAuthed(req);

    const [pm, re, der] = await Promise.all([
      query(
        `SELECT metric, date, value, extra FROM performance_metrics
          WHERE date BETWEEN $1 AND $2 ORDER BY metric, date`,
        [from, to]
      ),
      query(
        `SELECT activity_id, date, re_ml_kg_km, re_rolling, score, rating,
                efficiency_index, cardiac_cost, vertical_ratio, avg_cadence,
                avg_ground_contact, window_hr, window_pace_secs_per_km, total_distance_m
           FROM running_economy
          WHERE date BETWEEN $1 AND $2 ORDER BY date`,
        [from, to]
      ),
      query(
        `SELECT activity_id, date, decoupling_pct, trimp FROM activity_derived
          WHERE date BETWEEN $1 AND $2 ORDER BY date`,
        [from, to]
      ),
    ]);

    const metrics = {};
    for (const row of pm.rows) {
      if (PRIVATE_METRICS.has(row.metric) && !authed) continue;
      (metrics[row.metric] ||= []).push({
        date: row.date instanceof Date ? row.date.toISOString().slice(0, 10) : row.date,
        value: row.value === null ? null : Number(row.value),
        extra: row.extra || null,
      });
    }

    const running_economy = re.rows.map((r) => ({
      activity_id: r.activity_id,
      date: r.date instanceof Date ? r.date.toISOString().slice(0, 10) : r.date,
      re_ml_kg_km: r.re_ml_kg_km === null ? null : Number(r.re_ml_kg_km),
      re_rolling: r.re_rolling === null ? null : Number(r.re_rolling),
      score: r.score,
      rating: r.rating,
      efficiency_index: r.efficiency_index === null ? null : Number(r.efficiency_index),
      cardiac_cost: r.cardiac_cost === null ? null : Number(r.cardiac_cost),
      vertical_ratio: r.vertical_ratio === null ? null : Number(r.vertical_ratio),
      avg_cadence: r.avg_cadence,
      avg_ground_contact: r.avg_ground_contact,
      window_hr: r.window_hr === null ? null : Number(r.window_hr),
      window_pace_secs_per_km: r.window_pace_secs_per_km === null ? null : Number(r.window_pace_secs_per_km),
      total_distance_m: r.total_distance_m === null ? null : Number(r.total_distance_m),
    }));

    const derived = der.rows.map((r) => ({
      activity_id: r.activity_id,
      date: r.date instanceof Date ? r.date.toISOString().slice(0, 10) : r.date,
      decoupling_pct: r.decoupling_pct === null ? null : Number(r.decoupling_pct),
      trimp: r.trimp === null ? null : Number(r.trimp),
    }));

    const last = (arr) => (arr && arr.length ? arr[arr.length - 1] : null);
    const summary = {
      vo2max_latest: last(metrics.vo2max)?.value ?? null,
      endurance_latest: last(metrics.endurance_score)?.value ?? null,
      hill_latest: last(metrics.hill_score)?.value ?? null,
      hrv_latest: last(metrics.hrv)?.value ?? null,
      re_latest: last(running_economy)?.re_ml_kg_km ?? null,
      re_rolling_latest: last(running_economy)?.re_rolling ?? null,
      re_rating: last(running_economy)?.rating ?? null,
      race_predictions: last(metrics.race_predictions)?.extra ?? null,
      decoupling_latest: (() => {
        const d = derived.filter((x) => x.decoupling_pct !== null);
        return d.length ? d[d.length - 1].decoupling_pct : null;
      })(),
      zone_efficiency: last(metrics.zone_efficiency)?.extra ?? null,
      recovery_latest: last(metrics.recovery_balance)?.value ?? null,
      endurance_vo2_latest: last(metrics.endurance_vo2_ratio)?.value ?? null,
      counts: Object.fromEntries(Object.entries(metrics).map(([k, v]) => [k, v.length])),
      running_economy_n: running_economy.length,
      derived_n: derived.length,
      authed,
    };

    return sendJson(res, 200, { metrics, running_economy, derived, summary, range: { from, to } });
  } catch (err) {
    return sendJson(res, 500, { error: 'server_error', detail: String((err && err.message) || err) });
  }
}
