#!/usr/bin/env python3
"""Export daily health metrics to CSV for medical consultation.

Pulls the long/narrow `performance_metrics` table and pivots it into a wide,
one-row-per-day table with the clinically useful `extra` fields expanded into
their own columns (sleep stages, SpO2 low, HRV status/baseline, etc.).

Health data is personal — output goes to exports/ (gitignored). Run from repo root:

    .venv/bin/python scripts/export_health_csv.py            # last 180 days
    .venv/bin/python scripts/export_health_csv.py --months 6
    .venv/bin/python scripts/export_health_csv.py --days 90
"""
from __future__ import annotations
import argparse
import csv
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras


def db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = Path(__file__).resolve().parent.parent / ".env"
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
                break
    if not url:
        raise SystemExit("DATABASE_URL not found (env or .env)")
    return re.sub(r"\?.*$", "", url)  # strip prisma-style params


# Columns: (output_column, metric, extractor(value, extra) -> cell)
def val(v, e):
    return v


def extra_key(key, scale=1.0, nd=None):
    def f(v, e):
        x = (e or {}).get(key)
        if x is None or x == "":
            return ""
        if scale != 1.0 or nd is not None:
            try:
                x = float(x) * scale
            except (TypeError, ValueError):
                return ""
            return round(x, nd) if nd is not None else x
        return x
    return f


def baseline_key(key):
    def f(v, e):
        b = (e or {}).get("baseline") or {}
        return b.get(key, "")
    return f


# Ordered so the medically-relevant fields come first.
COLUMNS = [
    # (col name, metric, extractor)
    ("resting_hr_bpm",        "resting_hr",          val),
    ("hrv_ms",                "hrv",                 val),
    ("hrv_status",            "hrv",                 extra_key("status")),
    ("hrv_weekly_avg_ms",     "hrv",                 extra_key("weeklyAvg")),
    ("spo2_avg_pct",          "spo2_avg",            val),
    ("spo2_lowest_pct",       "spo2_avg",            extra_key("lowest")),
    ("vo2max",                "vo2max",              val),
    ("sleep_total_h",         "sleep_hours",         val),
    ("sleep_score",           "sleep_hours",         extra_key("score")),
    ("sleep_deep_h",          "sleep_hours",         extra_key("deep_s", 1/3600, 2)),
    ("sleep_light_h",         "sleep_hours",         extra_key("light_s", 1/3600, 2)),
    ("sleep_rem_h",           "sleep_hours",         extra_key("rem_s", 1/3600, 2)),
    ("sleep_awake_h",         "sleep_hours",         extra_key("awake_s", 1/3600, 2)),
    ("stress_avg",            "stress_weekly",       val),
    ("body_battery_charged",  "body_battery_charged", val),
    ("body_battery_drained",  "body_battery_charged", extra_key("drained")),
    ("steps",                 "steps",               val),
    ("training_readiness",    "training_readiness",  val),
    ("readiness_level",       "training_readiness",  extra_key("level")),
    ("recovery_time_min",     "recovery_time_min",   val),
    ("acute_load",            "acute_load",          val),
    ("endurance_score",       "endurance_score",     val),
    ("intensity_minutes",     "intensity_minutes",   val),
    ("weight_kg",             "weight_kg",           val),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    span = args.days if args.days else args.months * 30
    today = date.today()
    start = today - timedelta(days=span)

    metrics = sorted({m for _, m, _ in COLUMNS})
    conn = psycopg2.connect(db_url(), sslmode="require")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT metric, date, value, extra
        FROM performance_metrics
        WHERE metric = ANY(%s) AND date >= %s
        ORDER BY date
        """,
        (metrics, start),
    )
    # store[date][metric] = (value, extra)
    store: dict = defaultdict(dict)
    for r in cur.fetchall():
        store[r["date"]][r["metric"]] = (r["value"], r["extra"])

    out = args.out or f"exports/health_export_{start:%Y%m%d}_{today:%Y%m%d}.csv"
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    header = ["date"] + [c for c, _, _ in COLUMNS]
    n_rows = 0
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for d in sorted(store):
            row = [d.isoformat()]
            for _, metric, fn in COLUMNS:
                cell = store[d].get(metric)
                row.append(fn(cell[0], cell[1]) if cell else "")
            w.writerow(row)
            n_rows += 1

    print(f"Wrote {n_rows} days ({start} → {today}) x {len(COLUMNS)} metrics")
    print(f"  {out}")


if __name__ == "__main__":
    main()
