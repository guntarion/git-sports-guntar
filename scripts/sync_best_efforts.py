"""
Compute best efforts (fastest time for a target distance) from Garmin activity
detail streams, and store them in PostgreSQL.

Why streams and not the stored splits: our per-km splits are not a reliable
grid — Garmin emits a mix of 1000 m, 800 m, 400 m and even merged multi-km
laps. A best 400 m or best 1 mile simply cannot be derived from them. The
activity detail endpoint exposes `sumDistance` and `sumDuration` samples
(~1700 per run), which give an exact distance-vs-time curve, so a proper
rolling window finds the genuine fastest segment for any distance.

One request per running activity, resumable: activities already processed are
skipped, so this can be stopped and restarted.

Usage (from the repo root):
    DATABASE_URL=... python scripts/sync_best_efforts.py
    DATABASE_URL=... python scripts/sync_best_efforts.py --limit 20
    DATABASE_URL=... python scripts/sync_best_efforts.py --rebuild   # ignore cache
"""
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from utils import load_config

# Target distances in metres. Keys are stable identifiers used by the UI.
TARGETS: List[Tuple[str, str, float]] = [
    ("400m",     "400 m",          400.0),
    ("half_mile", "½ mile",        804.672),
    ("1k",       "1 km",           1000.0),
    ("1mile",    "1 mile",         1609.344),
    ("5k",       "5 km",           5000.0),
    ("10k",      "10 km",          10000.0),
    ("15k",      "15 km",          15000.0),
    ("20k",      "20 km",          20000.0),
    ("half",     "Half Marathon",  21097.5),
    ("30k",      "30 km",          30000.0),
    ("marathon", "Marathon",       42195.0),
]

RUN_HINTS = ("running", "run")

UPSERT = """
INSERT INTO best_efforts (
    activity_id, distance_key, date, activity_name, activity_type,
    distance_m, duration_s, pace_secs_per_km, computed_at
) VALUES (
    %(activity_id)s, %(distance_key)s, %(date)s, %(activity_name)s, %(activity_type)s,
    %(distance_m)s, %(duration_s)s, %(pace_secs_per_km)s, now()
)
ON CONFLICT (activity_id, distance_key) DO UPDATE SET
    date=EXCLUDED.date, activity_name=EXCLUDED.activity_name,
    activity_type=EXCLUDED.activity_type, distance_m=EXCLUDED.distance_m,
    duration_s=EXCLUDED.duration_s, pace_secs_per_km=EXCLUDED.pace_secs_per_km,
    computed_at=now()
"""


def _connect(database_url: str):
    import psycopg2
    from sync_db import _clean_database_url

    return psycopg2.connect(_clean_database_url(database_url), connect_timeout=15)


def _ensure_schema(conn) -> None:
    path = os.path.join("sql", "schema_app.sql")
    if os.path.exists(path):
        with conn, conn.cursor() as cur:
            cur.execute(open(path, "r", encoding="utf-8").read())


def extract_stream(detail: Dict[str, Any]) -> List[Tuple[float, float]]:
    """[(cumulative_distance_m, cumulative_seconds), ...], strictly increasing.

    Metric positions differ per activity, so the indices are resolved from
    metricDescriptors rather than hard-coded.
    """
    descs = detail.get("metricDescriptors") or []
    idx = {}
    for d in descs:
        k = d.get("key")
        if k in ("sumDistance", "sumDuration", "sumElapsedDuration"):
            idx[k] = d.get("metricsIndex")
    if "sumDistance" not in idx:
        return []
    dur_key = "sumDuration" if "sumDuration" in idx else "sumElapsedDuration"
    if dur_key not in idx:
        return []

    di, ti = idx["sumDistance"], idx[dur_key]
    out: List[Tuple[float, float]] = []
    for row in (detail.get("activityDetailMetrics") or []):
        m = row.get("metrics") or []
        if di >= len(m) or ti >= len(m):
            continue
        dist, dur = m[di], m[ti]
        if dist is None or dur is None:
            continue
        # Keep the curve monotonic; pauses and GPS jitter can produce dips.
        if out and (dist < out[-1][0] or dur < out[-1][1]):
            continue
        out.append((float(dist), float(dur)))
    return out


def best_for_distance(stream: List[Tuple[float, float]], target_m: float) -> Optional[float]:
    """Fastest elapsed time covering at least `target_m`, via a rolling window.

    Returns seconds, or None when the activity never covers the distance.
    """
    n = len(stream)
    if n < 2 or stream[-1][0] < target_m:
        return None
    best = None
    j = 0
    for i in range(n):
        if j < i:
            j = i
        while j < n and (stream[j][0] - stream[i][0]) < target_m:
            j += 1
        if j >= n:
            break
        span = stream[j][1] - stream[i][1]
        if span > 0 and (best is None or span < best):
            best = span
    return best


def compute_for_activity(detail: Dict[str, Any]) -> Dict[str, float]:
    stream = extract_stream(detail)
    if not stream:
        return {}
    out = {}
    for key, _label, metres in TARGETS:
        secs = best_for_distance(stream, metres)
        if secs:
            out[key] = secs
    return out


def _is_run(type_key: str) -> bool:
    t = (type_key or "").lower()
    # Treadmill distance is accelerometer-derived, so its times are not
    # comparable with GPS-measured efforts.
    if "treadmill" in t or "indoor" in t:
        return False
    return any(h in t for h in RUN_HINTS)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL not set; skipping best efforts.", file=sys.stderr)
        return 0

    rebuild = "--rebuild" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        try:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        except (IndexError, ValueError):
            limit = None
    if limit is None:
        try:
            limit = int(os.environ.get("BEST_EFFORT_LIMIT", "") or 0) or None
        except ValueError:
            limit = None

    try:
        config = load_config()
        from sync_garmin import load_garmin_client

        client = load_garmin_client(config)
        conn = _connect(database_url)
    except Exception as exc:
        print(f"Warning: best-effort sync could not start: {exc}", file=sys.stderr)
        return 0

    try:
        _ensure_schema(conn)

        done = set()
        if not rebuild:
            with conn, conn.cursor() as cur:
                cur.execute("SELECT DISTINCT activity_id FROM best_efforts")
                done = {r[0] for r in cur.fetchall()}

        # Candidate runs from the bulk list (cheap).
        runs = []
        start = 0
        while True:
            batch = client.get_activities(start, 200) or []
            if not batch:
                break
            for a in batch:
                tk = ((a.get("activityType") or {}).get("typeKey")) or ""
                if not _is_run(tk):
                    continue
                aid = str(a.get("activityId"))
                if aid in done:
                    continue
                runs.append({
                    "id": aid,
                    "date": (a.get("startTimeLocal") or "")[:10],
                    "name": a.get("activityName"),
                    "type": tk,
                })
            if len(batch) < 200:
                break
            start += 200
            time.sleep(1.0)

        if limit:
            runs = runs[:limit]
        if not runs:
            print("Best efforts: nothing new to process.")
            return 0

        print(f"Best efforts: {len(runs)} runs to process ({len(done)} already done)")
        written = 0
        misses = 0
        for n, r in enumerate(runs, 1):
            try:
                detail = client.get_activity_details(r["id"]) or {}
                efforts = compute_for_activity(detail)
                for key, secs in efforts.items():
                    metres = next(m for k, _l, m in TARGETS if k == key)
                    with conn, conn.cursor() as cur:
                        cur.execute(UPSERT, {
                            "activity_id": r["id"],
                            "distance_key": key,
                            "date": r["date"] or None,
                            "activity_name": r["name"],
                            "activity_type": r["type"],
                            "distance_m": metres,
                            "duration_s": round(secs, 1),
                            "pace_secs_per_km": round(secs / (metres / 1000.0), 1),
                        })
                    written += 1
                misses = 0
                time.sleep(1.2)
            except Exception as exc:
                misses += 1
                print(f"  {r['id']} failed ({misses}): {exc}", file=sys.stderr)
                if misses >= 5:
                    print("  too many consecutive failures; stopping early.", file=sys.stderr)
                    break
                time.sleep(5 * misses)
            if n % 20 == 0:
                print(f"  progress: {n}/{len(runs)}")

        print(f"Best efforts: {written} rows written across {len(runs)} runs")
    except Exception as exc:
        print(f"Warning: best-effort sync failed: {exc}", file=sys.stderr)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
