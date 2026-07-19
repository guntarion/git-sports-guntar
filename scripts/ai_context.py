"""
Build the recovery / load / efficiency context that the AI coach was missing.

The original prompt saw only this-month-vs-last-month aggregates and the last
five runs (~1.6 KB). Everything the pipeline had since collected — sleep, HRV,
resting HR, training readiness, acute:chronic load, Running Economy, aerobic
decoupling, best efforts — never reached the model. A coach blind to recovery
will happily prescribe hard work on the day your HRV has collapsed, so this
module summarises that data into compact, decision-relevant numbers.

Everything is aggregated, never dumped: 184 HRV rows become a recent average, a
baseline and a trend. The goal is a prompt the model can reason over, not a
database export.

All failures are non-fatal — the caller falls back to the activity-only summary.
"""
import os
import statistics as st
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


def _connect(database_url: str):
    import psycopg2
    from sync_db import _clean_database_url

    return psycopg2.connect(_clean_database_url(database_url), connect_timeout=10)


def _series(cur, metric: str, days: int) -> List[tuple]:
    cur.execute(
        """SELECT date, value FROM performance_metrics
            WHERE metric = %s AND value IS NOT NULL AND date >= %s
            ORDER BY date""",
        (metric, (date.today() - timedelta(days=days)).isoformat()),
    )
    return cur.fetchall()


def _avg(vals) -> Optional[float]:
    vals = [float(v) for v in vals if v is not None]
    return round(st.mean(vals), 1) if vals else None


def _window(rows: List[tuple], days: int) -> List[float]:
    cutoff = date.today() - timedelta(days=days)
    return [float(v) for d, v in rows if d >= cutoff and v is not None]


def _trend(rows: List[tuple], recent_days: int = 14, baseline_days: int = 60) -> Dict[str, Any]:
    """Recent average vs a longer baseline — the shape a coach actually needs."""
    recent = _window(rows, recent_days)
    base = _window(rows, baseline_days)
    if not recent or not base:
        return {}
    r, b = st.mean(recent), st.mean(base)
    out = {
        "recent_avg": round(r, 1),
        "baseline_avg": round(b, 1),
        "delta": round(r - b, 1),
        "n_recent": len(recent),
    }
    if b:
        out["pct_vs_baseline"] = round((r - b) / abs(b) * 100, 1)
    return out


def build_db_context(database_url: str) -> Dict[str, Any]:
    """Compact recovery / load / efficiency context, or {} if unavailable."""
    ctx: Dict[str, Any] = {}
    conn = _connect(database_url)
    try:
        with conn.cursor() as cur:
            # ── Recovery ──────────────────────────────────────────────────
            recovery: Dict[str, Any] = {}
            hrv = _series(cur, "hrv", 90)
            if hrv:
                recovery["hrv_ms"] = _trend(hrv, 7, 60)
                recovery["hrv_ms"]["latest"] = round(float(hrv[-1][1]), 1)
            sleep = _series(cur, "sleep_hours", 90)
            if sleep:
                recovery["sleep_hours"] = _trend(sleep, 7, 60)
                recovery["sleep_under_7h_last_14d"] = sum(1 for v in _window(sleep, 14) if v < 7)
            rhr = _series(cur, "resting_hr", 90)
            if rhr:
                # Rising resting HR against baseline is a classic fatigue signal.
                recovery["resting_hr_bpm"] = _trend(rhr, 7, 60)
            readiness = _series(cur, "training_readiness", 60)
            if readiness:
                recovery["training_readiness"] = {
                    "latest": round(float(readiness[-1][1])),
                    "avg_7d": _avg(_window(readiness, 7)),
                }
            rec_time = _series(cur, "recovery_time_min", 30)
            if rec_time:
                recovery["recovery_time_hours_latest"] = round(float(rec_time[-1][1]) / 60, 1)
            bb = _series(cur, "body_battery_charged", 60)
            if bb:
                recovery["body_battery_charged"] = _trend(bb, 7, 60)
            stress = _series(cur, "stress_weekly", 120)
            if stress:
                recovery["stress_weekly"] = _trend(stress, 21, 90)
            spo2 = _series(cur, "spo2_avg", 60)
            if spo2:
                recovery["spo2_pct_avg_7d"] = _avg(_window(spo2, 7))
            if recovery:
                ctx["recovery"] = recovery

            # ── Training load ─────────────────────────────────────────────
            load: Dict[str, Any] = {}
            with conn.cursor() as c2:
                c2.execute("""SELECT metric, value, extra FROM performance_metrics
                               WHERE metric IN ('acute_load','chronic_load','acwr')
                               ORDER BY date DESC LIMIT 12""")
                for m, v, extra in c2.fetchall():
                    if m not in load and v is not None:
                        load[m] = float(v)
                        if m == "acwr" and extra:
                            load["acwr_status"] = extra.get("status")
            weekly = _series(cur, "training_load_weekly", 120)
            if weekly:
                load["weekly_trimp"] = _trend(weekly, 21, 90)
                load["last_4_weeks"] = [round(float(v)) for _d, v in weekly[-4:]]
            balance = _series(cur, "recovery_balance", 120)
            if balance:
                load["recovery_balance"] = {
                    "latest": round(float(balance[-1][1]), 2),
                    "avg_4w": _avg([v for v in _window(balance, 28)]),
                    "meaning": "HRV z-score minus load z-score; below 0 = load outpacing recovery",
                }
            if load:
                ctx["training_load"] = load

            # ── Efficiency / performance ──────────────────────────────────
            with conn.cursor() as c2:
                c2.execute("""SELECT date, re_ml_kg_km, re_rolling, rating, efficiency_index,
                                     cardiac_cost, vertical_ratio
                                FROM running_economy ORDER BY date DESC LIMIT 10""")
                re_rows = c2.fetchall()
            if re_rows:
                ctx["running_economy"] = {
                    "unit": "ml O2/kg/km, LOWER is better",
                    "latest": float(re_rows[0][1]),
                    "rolling_median": float(re_rows[0][2]) if re_rows[0][2] else None,
                    "rating": re_rows[0][3],
                    "recent_values": [float(r[1]) for r in re_rows[:6]],
                    "efficiency_index_latest": float(re_rows[0][4]) if re_rows[0][4] else None,
                    "vertical_ratio_pct": float(re_rows[0][6]) if re_rows[0][6] else None,
                }

            with conn.cursor() as c2:
                c2.execute("""SELECT date, decoupling_pct FROM activity_derived
                               WHERE decoupling_pct IS NOT NULL
                               ORDER BY date DESC LIMIT 8""")
                dec = c2.fetchall()
            if dec:
                ctx["aerobic_decoupling_pct"] = {
                    "note": "first-half vs second-half efficiency drift; under 5% = aerobically sound",
                    "latest": float(dec[0][1]),
                    "recent": [float(d[1]) for d in dec[:6]],
                    "median_recent": round(st.median([float(d[1]) for d in dec]), 2),
                }

            vo2 = _series(cur, "vo2max", 180)
            if vo2:
                ctx["vo2max"] = {"latest": float(vo2[-1][1]), **_trend(vo2, 30, 150)}

            with conn.cursor() as c2:
                c2.execute("""SELECT DISTINCT ON (distance_key) distance_key, duration_s,
                                     activity_name, date
                                FROM best_efforts ORDER BY distance_key, duration_s ASC""")
                be = c2.fetchall()
            if be:
                ctx["best_efforts_seconds"] = {
                    r[0]: {"seconds": round(float(r[1])), "session": r[2], "date": str(r[3])}
                    for r in be
                }

            with conn.cursor() as c2:
                c2.execute("""SELECT extra FROM performance_metrics
                               WHERE metric='race_predictions' ORDER BY date DESC LIMIT 1""")
                row = c2.fetchone()
            if row and row[0]:
                ctx["race_predictions_seconds"] = row[0]

            with conn.cursor() as c2:
                c2.execute("""SELECT value, extra FROM performance_metrics
                               WHERE metric='training_status_phrase' ORDER BY date DESC LIMIT 1""")
                row = c2.fetchone()
            if row and row[1]:
                ctx["garmin_training_status"] = row[1].get("phrase")

            with conn.cursor() as c2:
                c2.execute("""SELECT extra FROM performance_metrics
                               WHERE metric='zone_efficiency' ORDER BY date DESC LIMIT 1""")
                row = c2.fetchone()
            if row and row[0]:
                ctx["efficiency_by_hr_zone_m_per_beat"] = {
                    k: v.get("ei") for k, v in row[0].items()
                }
    finally:
        conn.close()
    return ctx


def safe_build() -> Dict[str, Any]:
    """Never raises: the AI stage must not break the pipeline."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return {}
    try:
        return build_db_context(url)
    except Exception as exc:  # pragma: no cover - network dependent
        import sys
        print(f"  AI context: DB unavailable ({exc}); using activity data only.", file=sys.stderr)
        return {}
