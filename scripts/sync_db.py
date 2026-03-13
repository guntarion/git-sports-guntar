"""
Sync activity data to PostgreSQL database for advanced analytics.

Reads from:
  - data/activities_normalized.json  (basic stats + extended fields)
  - activities/enriched/garmin/*.json (HR zones + splits)

Writes to:
  - activities       (per-session stats)
  - activity_splits  (split/lap data per km)
  - activity_hr_zones (HR zone distribution)

Run after generate_activities.py in the pipeline.
Requires DATABASE_URL environment variable.
"""
import os
import sys
from typing import Any, Dict, List, Optional

from utils import load_config, normalize_source, read_json, utc_now

NORMALIZED_PATH = os.path.join("data", "activities_normalized.json")
ENRICHED_DIR = os.path.join("activities", "enriched", "garmin")

CREATE_ACTIVITIES = """
CREATE TABLE IF NOT EXISTS activities (
    id                  TEXT PRIMARY KEY,
    date                DATE,
    start_date_local    TIMESTAMP,
    type                TEXT,
    raw_type            TEXT,
    name                TEXT,
    source              TEXT,
    distance_m          FLOAT,
    moving_time_s       FLOAT,
    elevation_gain_m    FLOAT,
    avg_hr              INTEGER,
    max_hr              INTEGER,
    calories            INTEGER,
    avg_speed_mps       FLOAT,
    avg_pace_secs_per_km INTEGER,
    aerobic_te          FLOAT,
    anaerobic_te        FLOAT,
    avg_cadence         INTEGER,
    tss                 FLOAT,
    vo2_max             FLOAT,
    avg_vertical_osc    FLOAT,
    avg_ground_contact  INTEGER,
    avg_stride_len      FLOAT,
    synced_at           TIMESTAMP DEFAULT NOW()
);
"""

CREATE_SPLITS = """
CREATE TABLE IF NOT EXISTS activity_splits (
    id              SERIAL PRIMARY KEY,
    activity_id     TEXT REFERENCES activities(id) ON DELETE CASCADE,
    split_num       INTEGER,
    distance_m      FLOAT,
    duration_s      FLOAT,
    avg_speed_mps   FLOAT,
    pace_secs_per_km INTEGER,
    avg_hr          INTEGER,
    max_hr          INTEGER,
    elevation_gain_m FLOAT
);
"""

CREATE_HR_ZONES = """
CREATE TABLE IF NOT EXISTS activity_hr_zones (
    id          SERIAL PRIMARY KEY,
    activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
    zone        INTEGER,
    seconds     INTEGER,
    low_bpm     INTEGER,
    high_bpm    INTEGER
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(type);",
    "CREATE INDEX IF NOT EXISTS idx_activities_source ON activities(source);",
    "CREATE INDEX IF NOT EXISTS idx_splits_activity ON activity_splits(activity_id);",
    "CREATE INDEX IF NOT EXISTS idx_hr_zones_activity ON activity_hr_zones(activity_id);",
]


def _safe_float(value: Any) -> Optional[float]:
    try:
        f = float(value)
        return f if f == f else None  # filter NaN
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_enriched(activity_id: str) -> Optional[Dict]:
    path = os.path.join(ENRICHED_DIR, f"{activity_id}.json")
    if not os.path.exists(path):
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def _upsert_activity(cur: Any, item: Dict, source: str) -> None:
    cur.execute(
        """
        INSERT INTO activities (
            id, date, start_date_local, type, raw_type, name, source,
            distance_m, moving_time_s, elevation_gain_m,
            avg_hr, max_hr, calories, avg_speed_mps, avg_pace_secs_per_km,
            aerobic_te, anaerobic_te, avg_cadence, tss, vo2_max,
            avg_vertical_osc, avg_ground_contact, avg_stride_len,
            synced_at
        ) VALUES (
            %(id)s, %(date)s, %(start_date_local)s, %(type)s, %(raw_type)s,
            %(name)s, %(source)s,
            %(distance_m)s, %(moving_time_s)s, %(elevation_gain_m)s,
            %(avg_hr)s, %(max_hr)s, %(calories)s, %(avg_speed_mps)s,
            %(avg_pace_secs_per_km)s, %(aerobic_te)s, %(anaerobic_te)s,
            %(avg_cadence)s, %(tss)s, %(vo2_max)s,
            %(avg_vertical_osc)s, %(avg_ground_contact)s, %(avg_stride_len)s,
            NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            date                  = EXCLUDED.date,
            start_date_local      = EXCLUDED.start_date_local,
            type                  = EXCLUDED.type,
            raw_type              = EXCLUDED.raw_type,
            name                  = EXCLUDED.name,
            source                = EXCLUDED.source,
            distance_m            = EXCLUDED.distance_m,
            moving_time_s         = EXCLUDED.moving_time_s,
            elevation_gain_m      = EXCLUDED.elevation_gain_m,
            avg_hr                = EXCLUDED.avg_hr,
            max_hr                = EXCLUDED.max_hr,
            calories              = EXCLUDED.calories,
            avg_speed_mps         = EXCLUDED.avg_speed_mps,
            avg_pace_secs_per_km  = EXCLUDED.avg_pace_secs_per_km,
            aerobic_te            = EXCLUDED.aerobic_te,
            anaerobic_te          = EXCLUDED.anaerobic_te,
            avg_cadence           = EXCLUDED.avg_cadence,
            tss                   = EXCLUDED.tss,
            vo2_max               = EXCLUDED.vo2_max,
            avg_vertical_osc      = EXCLUDED.avg_vertical_osc,
            avg_ground_contact    = EXCLUDED.avg_ground_contact,
            avg_stride_len        = EXCLUDED.avg_stride_len,
            synced_at             = NOW()
        """,
        {
            "id": str(item.get("id") or ""),
            "date": item.get("date"),
            "start_date_local": item.get("start_date_local"),
            "type": item.get("type"),
            "raw_type": item.get("raw_type") or item.get("type"),
            "name": item.get("name"),
            "source": source,
            "distance_m": _safe_float(item.get("distance")),
            "moving_time_s": _safe_float(item.get("moving_time")),
            "elevation_gain_m": _safe_float(item.get("elevation_gain")),
            "avg_hr": _safe_int(item.get("avg_hr")),
            "max_hr": _safe_int(item.get("max_hr")),
            "calories": _safe_int(item.get("calories")),
            "avg_speed_mps": _safe_float(item.get("avg_speed_mps")),
            "avg_pace_secs_per_km": _safe_int(item.get("avg_pace_secs_per_km")),
            "aerobic_te": _safe_float(item.get("aerobic_te")),
            "anaerobic_te": _safe_float(item.get("anaerobic_te")),
            "avg_cadence": _safe_int(item.get("avg_cadence")),
            "tss": _safe_float(item.get("tss")),
            "vo2_max": _safe_float(item.get("vo2_max")),
            "avg_vertical_osc": _safe_float(item.get("avg_vertical_osc")),
            "avg_ground_contact": _safe_int(item.get("avg_ground_contact")),
            "avg_stride_len": _safe_float(item.get("avg_stride_len")),
        },
    )


def _replace_splits(cur: Any, activity_id: str, splits: List[Dict]) -> None:
    cur.execute("DELETE FROM activity_splits WHERE activity_id = %s", (activity_id,))
    for i, split in enumerate(splits, start=1):
        cur.execute(
            """
            INSERT INTO activity_splits (
                activity_id, split_num, distance_m, duration_s,
                avg_speed_mps, pace_secs_per_km, avg_hr, max_hr, elevation_gain_m
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                activity_id,
                i,
                _safe_float(split.get("distance")),
                _safe_float(split.get("duration")),
                _safe_float(split.get("avg_speed_mps")),
                _safe_int(split.get("pace_secs_per_km")),
                _safe_int(split.get("avg_hr")),
                _safe_int(split.get("max_hr")),
                _safe_float(split.get("elevation_gain")),
            ),
        )


def _replace_hr_zones(cur: Any, activity_id: str, zones: List[Dict]) -> None:
    cur.execute("DELETE FROM activity_hr_zones WHERE activity_id = %s", (activity_id,))
    for zone in zones:
        cur.execute(
            """
            INSERT INTO activity_hr_zones (activity_id, zone, seconds, low_bpm, high_bpm)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (
                activity_id,
                _safe_int(zone.get("zone")),
                _safe_int(zone.get("seconds")),
                _safe_int(zone.get("low_bpm")),
                _safe_int(zone.get("high_bpm")),
            ),
        )


def sync_to_db(database_url: str) -> Dict[str, Any]:
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'psycopg2-binary'. Add it to requirements.txt."
        ) from exc

    config = load_config()
    source = normalize_source(config.get("source", "strava"))

    if not os.path.exists(NORMALIZED_PATH):
        print("No normalized activities; nothing to sync to DB.")
        return {"upserted": 0, "splits_written": 0, "zones_written": 0}

    normalized_list: List[Dict] = read_json(NORMALIZED_PATH) or []

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                # Ensure schema exists
                cur.execute(CREATE_ACTIVITIES)
                cur.execute(CREATE_SPLITS)
                cur.execute(CREATE_HR_ZONES)
                for idx_sql in CREATE_INDEXES:
                    cur.execute(idx_sql)

        upserted = 0
        splits_written = 0
        zones_written = 0

        for item in normalized_list:
            if not isinstance(item, dict):
                continue
            activity_id = str(item.get("id") or "").strip()
            if not activity_id:
                continue

            enriched = _load_enriched(activity_id) if source == "garmin" else None

            with conn:
                with conn.cursor() as cur:
                    _upsert_activity(cur, item, source)
                    upserted += 1

                    if enriched:
                        splits = enriched.get("splits") or []
                        if splits:
                            _replace_splits(cur, activity_id, splits)
                            splits_written += len(splits)

                        zones = enriched.get("hr_zones") or []
                        if zones:
                            _replace_hr_zones(cur, activity_id, zones)
                            zones_written += len(zones)

    finally:
        conn.close()

    return {
        "upserted": upserted,
        "splits_written": splits_written,
        "zones_written": zones_written,
    }


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL not set; skipping DB sync.", file=sys.stderr)
        return 0

    try:
        summary = sync_to_db(database_url)
        print(
            f"DB sync complete: {summary['upserted']} upserted, "
            f"{summary['splits_written']} splits, "
            f"{summary['zones_written']} HR zone rows"
        )
    except Exception as exc:
        print(f"Warning: DB sync failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
