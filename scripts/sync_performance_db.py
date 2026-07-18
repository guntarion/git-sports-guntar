"""
Sync Garmin performance metrics and Running Economy into PostgreSQL.

Two independent parts, both non-fatal (a failure here must never break the
activity pipeline):

1. Running Economy — computed locally from site/activities.json.
2. Garmin performance metrics — VO2max history, endurance score, hill score,
   race predictions, HRV, body weight. Verified available on this account;
   `get_max_metrics` returns empty, so VO2max history is reconstructed from the
   per-activity vo2_max values instead, with the current value taken from
   get_training_status.

Requires DATABASE_URL. Garmin calls additionally need a token store.
"""
import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from utils import load_config, read_json

ACTIVITIES_PATH = os.path.join("site", "activities.json")

RE_UPSERT = """
INSERT INTO running_economy (
    activity_id, date, re_ml_kg_km, re_rolling, score, rating,
    efficiency_index, cardiac_cost, vertical_ratio, avg_cadence,
    avg_ground_contact, window_hr, window_pace_secs_per_km,
    window_distance_m, total_distance_m, computed_at
) VALUES (
    %(activity_id)s, %(date)s, %(re_ml_kg_km)s, %(re_rolling)s, %(score)s, %(rating)s,
    %(efficiency_index)s, %(cardiac_cost)s, %(vertical_ratio)s, %(avg_cadence)s,
    %(avg_ground_contact)s, %(window_hr)s, %(window_pace_secs_per_km)s,
    %(window_distance_m)s, %(total_distance_m)s, now()
)
ON CONFLICT (activity_id) DO UPDATE SET
    date=EXCLUDED.date, re_ml_kg_km=EXCLUDED.re_ml_kg_km,
    re_rolling=EXCLUDED.re_rolling, score=EXCLUDED.score, rating=EXCLUDED.rating,
    efficiency_index=EXCLUDED.efficiency_index, cardiac_cost=EXCLUDED.cardiac_cost,
    vertical_ratio=EXCLUDED.vertical_ratio, avg_cadence=EXCLUDED.avg_cadence,
    avg_ground_contact=EXCLUDED.avg_ground_contact, window_hr=EXCLUDED.window_hr,
    window_pace_secs_per_km=EXCLUDED.window_pace_secs_per_km,
    window_distance_m=EXCLUDED.window_distance_m,
    total_distance_m=EXCLUDED.total_distance_m, computed_at=now()
"""

METRIC_UPSERT = """
INSERT INTO performance_metrics (metric, date, value, extra, synced_at)
VALUES (%(metric)s, %(date)s, %(value)s, %(extra)s::jsonb, now())
ON CONFLICT (metric, date) DO UPDATE SET
    value=EXCLUDED.value, extra=EXCLUDED.extra, synced_at=now()
"""


def _connect(database_url: str):
    import psycopg2
    from sync_db import _clean_database_url

    return psycopg2.connect(_clean_database_url(database_url), connect_timeout=15)


def _ensure_schema(conn) -> None:
    path = os.path.join("sql", "schema_app.sql")
    if not os.path.exists(path):
        return
    with conn, conn.cursor() as cur:
        cur.execute(open(path, "r", encoding="utf-8").read())


# ── Running Economy ────────────────────────────────────────────────────────────
def sync_running_economy(conn, config: Dict[str, Any]) -> Dict[str, int]:
    from running_economy import compute_series, params_from_config

    if not os.path.exists(ACTIVITIES_PATH):
        return {"computed": 0, "written": 0}

    data = read_json(ACTIVITIES_PATH) or {}
    activities = data.get("activities") or []
    params = params_from_config(config)
    result = compute_series(activities, params)
    items = result["items"]

    written = 0
    for m in items:
        row = {k: m.get(k) for k in (
            "activity_id", "date", "re_ml_kg_km", "re_rolling", "score", "rating",
            "efficiency_index", "cardiac_cost", "vertical_ratio", "avg_cadence",
            "avg_ground_contact", "window_hr", "window_pace_secs_per_km",
            "window_distance_m", "total_distance_m")}
        if not row.get("activity_id") or not row.get("date"):
            continue
        with conn, conn.cursor() as cur:
            cur.execute(RE_UPSERT, row)
        written += 1

    baseline = result.get("baseline")
    if baseline:
        print(f"  RE baseline: median={baseline['median']} sigma={baseline['sigma']} n={baseline['n']}")
    return {"computed": len(items), "written": written}


# ── Garmin performance metrics ─────────────────────────────────────────────────
def _put(conn, metric: str, day: str, value: Optional[float], extra: Any = None) -> None:
    with conn, conn.cursor() as cur:
        cur.execute(METRIC_UPSERT, {
            "metric": metric,
            "date": day,
            "value": value,
            "extra": json.dumps(extra, ensure_ascii=False, default=str) if extra is not None else None,
        })


def sync_garmin_metrics(conn, client, hrv_days: int = 0) -> Dict[str, int]:
    """Pull performance metrics. hrv_days>0 backfills that many days of HRV
    (one request per day — Garmin rate limits, so keep it modest)."""
    counts: Dict[str, int] = {}
    today = date.today()
    d_today = today.isoformat()
    d_year = (today - timedelta(days=365)).isoformat()

    def bump(k, n=1):
        counts[k] = counts.get(k, 0) + n

    # VO2max history from per-activity values (get_max_metrics is empty here).
    try:
        data = read_json(ACTIVITIES_PATH) or {}
        seen = {}
        for a in (data.get("activities") or []):
            if a.get("vo2_max") and a.get("date"):
                seen[a["date"]] = a["vo2_max"]  # last write per day wins
        for day, val in sorted(seen.items()):
            _put(conn, "vo2max", day, val)
            bump("vo2max")
    except Exception as exc:
        print(f"  vo2max history failed: {exc}", file=sys.stderr)

    if client is None:
        return counts

    # Current VO2max + training status
    try:
        ts = client.get_training_status(d_today)
        recent = (ts or {}).get("mostRecentVO2Max") or {}
        gen = recent.get("generic") or {}
        if gen.get("vo2MaxPreciseValue") or gen.get("vo2MaxValue"):
            day = gen.get("calendarDate") or d_today
            _put(conn, "vo2max", day, gen.get("vo2MaxPreciseValue") or gen.get("vo2MaxValue"), gen)
            bump("vo2max")
        status = (ts or {}).get("mostRecentTrainingStatus") or {}
        if status:
            _put(conn, "training_status", d_today, None, status)
            bump("training_status")
        time.sleep(1)
    except Exception as exc:
        print(f"  training_status failed: {exc}", file=sys.stderr)

    # Endurance score — weekly groups across the last year
    try:
        es = client.get_endurance_score(d_year, d_today)
        for week, grp in sorted((es or {}).get("groupMap", {}).items()):
            avg = (grp or {}).get("groupAverage")
            if avg is not None:
                _put(conn, "endurance_score", week, avg, {"max": grp.get("groupMax")})
                bump("endurance_score")
        time.sleep(1)
    except Exception as exc:
        print(f"  endurance_score failed: {exc}", file=sys.stderr)

    # Hill score — daily points
    try:
        hs = client.get_hill_score(d_year, d_today)
        for item in (hs or {}).get("hillScoreDTOList", []) or []:
            day = item.get("calendarDate")
            if not day:
                continue
            _put(conn, "hill_score", day, item.get("overallScore"), {
                "strength": item.get("strengthScore"), "endurance": item.get("enduranceScore")})
            bump("hill_score")
        time.sleep(1)
    except Exception as exc:
        print(f"  hill_score failed: {exc}", file=sys.stderr)

    # Race predictions (single current snapshot)
    try:
        rp = client.get_race_predictions() or {}
        day = rp.get("calendarDate") or d_today
        if rp.get("time5K"):
            _put(conn, "race_predictions", day, rp.get("time5K"), {
                k: rp.get(k) for k in ("time5K", "time10K", "timeHalfMarathon", "timeMarathon")})
            bump("race_predictions")
        time.sleep(1)
    except Exception as exc:
        print(f"  race_predictions failed: {exc}", file=sys.stderr)

    # Body weight history
    try:
        bc = client.get_body_composition(d_year, d_today) or {}
        for w in bc.get("dateWeightList", []) or []:
            day = w.get("calendarDate")
            grams = w.get("weight")
            if day and grams:
                _put(conn, "weight_kg", day, round(grams / 1000.0, 2))
                bump("weight_kg")
        time.sleep(1)
    except Exception as exc:
        print(f"  body_composition failed: {exc}", file=sys.stderr)

    # HRV — one Garmin request per day. Resumable: days already stored are
    # skipped, so a long backfill can be re-run to fill whatever it missed.
    if hrv_days > 0:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT date FROM performance_metrics WHERE metric='hrv'")
            have = {r[0].isoformat() for r in cur.fetchall()}

        wanted = [(today - timedelta(days=i)).isoformat() for i in range(hrv_days)]
        todo = [d for d in wanted if d not in have]
        if todo:
            print(f"  HRV backfill: {len(todo)} days to fetch ({len(have)} already stored)")

        misses = 0
        for n, day in enumerate(todo, 1):
            try:
                hrv = client.get_hrv_data(day) or {}
                s = hrv.get("hrvSummary") or {}
                if s.get("lastNightAvg") is not None:
                    _put(conn, "hrv", s.get("calendarDate") or day, s.get("lastNightAvg"), {
                        "weeklyAvg": s.get("weeklyAvg"),
                        "lastNight5MinHigh": s.get("lastNight5MinHigh"),
                        "status": s.get("status"),
                        "baseline": s.get("baseline"),
                    })
                    bump("hrv")
                misses = 0
                time.sleep(1.2)
            except Exception as exc:
                misses += 1
                print(f"  hrv {day} failed ({misses}): {exc}", file=sys.stderr)
                if misses >= 5:
                    print("  too many consecutive HRV failures; stopping backfill early.",
                          file=sys.stderr)
                    break
                time.sleep(5 * misses)  # back off rather than hammer a rate limit
            if n % 25 == 0:
                print(f"  HRV progress: {n}/{len(todo)}")

    return counts


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL not set; skipping performance DB sync.", file=sys.stderr)
        return 0

    hrv_days = int(os.environ.get("HRV_BACKFILL_DAYS", "0") or 0)
    skip_garmin = os.environ.get("SKIP_GARMIN_METRICS", "").strip() == "1"

    try:
        config = load_config()
        conn = _connect(database_url)
    except Exception as exc:
        print(f"Warning: performance DB sync could not start: {exc}", file=sys.stderr)
        return 0

    try:
        _ensure_schema(conn)

        re_stats = sync_running_economy(conn, config)
        print(f"Running economy: computed={re_stats['computed']} written={re_stats['written']}")

        client = None
        if not skip_garmin:
            try:
                from sync_garmin import load_garmin_client

                client = load_garmin_client(config)
            except Exception as exc:
                print(f"  Garmin client unavailable ({exc}); metrics skipped.", file=sys.stderr)

        counts = sync_garmin_metrics(conn, client, hrv_days=hrv_days)
        if counts:
            print("Performance metrics: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    except Exception as exc:
        print(f"Warning: performance DB sync failed: {exc}", file=sys.stderr)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
