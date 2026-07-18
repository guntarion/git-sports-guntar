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

/* Month-over-month comparison.
 *
 * The partial-month trap: on the 18th, comparing "July so far" against "all of
 * June" is not apple-to-apple — June had 30 days of chances to accumulate
 * readings (and, for cumulative metrics, 30 days of load). So we compare the
 * SAME elapsed window: day 1..N of this month vs day 1..N of last month, where
 * N is today's day-of-month (clamped to the previous month's length, e.g. the
 * 31st against a 30-day month). Equal-length windows are fair for both
 * averages and sums, and the comparison stays valid from day 1 of a month.
 */
function monthWindows(now) {
  const y = now.getUTCFullYear(), m = now.getUTCMonth(), day = now.getUTCDate();
  const iso = (dt) => dt.toISOString().slice(0, 10);
  const curFrom = new Date(Date.UTC(y, m, 1));
  const curTo = new Date(Date.UTC(y, m, day));
  const prevFrom = new Date(Date.UTC(y, m - 1, 1));
  const prevMonthDays = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const prevTo = new Date(Date.UTC(y, m - 1, Math.min(day, prevMonthDays)));
  return {
    cur_from: iso(curFrom), cur_to: iso(curTo),
    prev_from: iso(prevFrom), prev_to: iso(prevTo),
    days_elapsed: day,
    month_label: curFrom.toLocaleDateString('en', { month: 'short', timeZone: 'UTC' }),
    prev_label: prevFrom.toLocaleDateString('en', { month: 'short', timeZone: 'UTC' }),
  };
}

// Direction of "better" per metric. 'neutral' = report the delta, no verdict.
const DIRECTION = {
  vo2max: 'up', endurance_score: 'up', hrv: 'up', hill_score: 'up',
  spo2_avg: 'up', training_readiness: 'up', endurance_vo2_ratio: 'up',
  recovery_balance: 'up',
  recovery_time_min: 'down',
  acute_load: 'neutral', chronic_load: 'neutral', acwr: 'neutral',
  training_load_weekly: 'neutral',
  running_economy: 'down', aerobic_decoupling: 'down',
};

function verdictFor(key, cur, prev) {
  if (cur === null || prev === null) return null;
  const dir = DIRECTION[key] || 'neutral';
  const delta = cur - prev;
  // Treat a <1% move as noise rather than a real change.
  const rel = prev !== 0 ? Math.abs(delta / prev) : (delta === 0 ? 0 : 1);
  if (rel < 0.01 || dir === 'neutral') return dir === 'neutral' ? 'neutral' : 'same';
  if (dir === 'up') return delta > 0 ? 'better' : 'worse';
  return delta < 0 ? 'better' : 'worse';
}

function buildComparison(key, cur, prev, nCur, nPrev, decimals) {
  const round = (v) => (v === null || v === undefined ? null : Number(Number(v).toFixed(decimals ?? 1)));
  const c = round(cur), p = round(prev);
  return {
    current: c, previous: p,
    delta: c !== null && p !== null ? round(c - p) : null,
    pct: c !== null && p !== null && p !== 0 ? Number(((c - p) / Math.abs(p) * 100).toFixed(1)) : null,
    verdict: verdictFor(key, c, p),
    n_current: Number(nCur) || 0,
    n_previous: Number(nPrev) || 0,
  };
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return sendJson(res, 405, { error: 'method not allowed' });

  try {
    const url = new URL(req.url, 'http://x');
    const from = isDate(url.searchParams.get('from')) ? url.searchParams.get('from') : '2000-01-01';
    const to = isDate(url.searchParams.get('to')) ? url.searchParams.get('to') : '2999-12-31';
    const authed = isAuthed(req);

    const w = monthWindows(new Date());
    const [pm, re, der, cmpPm, cmpRe, cmpDer] = await Promise.all([
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
      // Same-elapsed-window month comparison, independent of the selected range.
      query(
        `SELECT metric,
                AVG(value) FILTER (WHERE date BETWEEN $1 AND $2) AS cur,
                COUNT(value) FILTER (WHERE date BETWEEN $1 AND $2) AS cur_n,
                AVG(value) FILTER (WHERE date BETWEEN $3 AND $4) AS prev,
                COUNT(value) FILTER (WHERE date BETWEEN $3 AND $4) AS prev_n
           FROM performance_metrics
          WHERE date BETWEEN $3 AND $2
          GROUP BY metric`,
        [w.cur_from, w.cur_to, w.prev_from, w.prev_to]
      ),
      query(
        `SELECT AVG(re_ml_kg_km) FILTER (WHERE date BETWEEN $1 AND $2) AS cur,
                COUNT(*) FILTER (WHERE date BETWEEN $1 AND $2) AS cur_n,
                AVG(re_ml_kg_km) FILTER (WHERE date BETWEEN $3 AND $4) AS prev,
                COUNT(*) FILTER (WHERE date BETWEEN $3 AND $4) AS prev_n
           FROM running_economy WHERE date BETWEEN $3 AND $2`,
        [w.cur_from, w.cur_to, w.prev_from, w.prev_to]
      ),
      query(
        `SELECT AVG(decoupling_pct) FILTER (WHERE date BETWEEN $1 AND $2) AS cur,
                COUNT(decoupling_pct) FILTER (WHERE date BETWEEN $1 AND $2) AS cur_n,
                AVG(decoupling_pct) FILTER (WHERE date BETWEEN $3 AND $4) AS prev,
                COUNT(decoupling_pct) FILTER (WHERE date BETWEEN $3 AND $4) AS prev_n,
                SUM(trimp) FILTER (WHERE date BETWEEN $1 AND $2) AS load_cur,
                SUM(trimp) FILTER (WHERE date BETWEEN $3 AND $4) AS load_prev
           FROM activity_derived WHERE date BETWEEN $3 AND $2`,
        [w.cur_from, w.cur_to, w.prev_from, w.prev_to]
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

    // ── Month-over-month, same elapsed window ──
    const comparison = { window: w, metrics: {} };
    for (const row of cmpPm.rows) {
      if (PRIVATE_METRICS.has(row.metric) && !authed) continue;
      const dec = row.metric === 'acwr' ? 2 : 1;
      comparison.metrics[row.metric] =
        buildComparison(row.metric, row.cur, row.prev, row.cur_n, row.prev_n, dec);
    }
    const r0 = cmpRe.rows[0] || {};
    comparison.metrics.running_economy =
      buildComparison('running_economy', r0.cur, r0.prev, r0.cur_n, r0.prev_n, 1);
    const d0 = cmpDer.rows[0] || {};
    comparison.metrics.aerobic_decoupling =
      buildComparison('aerobic_decoupling', d0.cur, d0.prev, d0.cur_n, d0.prev_n, 2);
    comparison.metrics.training_load_total =
      buildComparison('training_load_weekly', d0.load_cur, d0.load_prev, 0, 0, 0);

    return sendJson(res, 200, {
      metrics, running_economy, derived, summary, comparison, range: { from, to },
    });
  } catch (err) {
    return sendJson(res, 500, { error: 'server_error', detail: String((err && err.message) || err) });
  }
}
