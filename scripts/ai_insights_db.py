"""
Persist AI coaching insights to PostgreSQL.

Called by generate_ai_insights.py after a successful generation so every report
survives beyond the static JSON files. All failures are non-fatal: the pipeline
must still succeed when the database is unreachable or DATABASE_URL is unset.

Also supports a one-time backfill of the existing site/ai_insights_history.json.

Requires DATABASE_URL.
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ai_insights (
    id                  BIGSERIAL PRIMARY KEY,
    generated_at        TIMESTAMPTZ NOT NULL,
    model               TEXT,
    kind                TEXT NOT NULL DEFAULT 'daily',
    running_fingerprint TEXT,
    period_start        DATE,
    period_end          DATE,
    data_summary        JSONB,
    insights            JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The same data state (fingerprint) can legitimately be analysed at
    -- different times; dedupe only on an exact re-save of one generation.
    CONSTRAINT ai_insights_fp_gen_key UNIQUE (running_fingerprint, generated_at)
);
CREATE INDEX IF NOT EXISTS idx_ai_generated ON ai_insights(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_kind ON ai_insights(kind);
"""

UPSERT = """
INSERT INTO ai_insights (
    generated_at, model, kind, running_fingerprint,
    period_start, period_end, data_summary, insights
) VALUES (
    %(generated_at)s, %(model)s, %(kind)s, %(running_fingerprint)s,
    %(period_start)s, %(period_end)s, %(data_summary)s::jsonb, %(insights)s::jsonb
)
ON CONFLICT (running_fingerprint, generated_at) DO UPDATE SET
    model        = EXCLUDED.model,
    kind         = EXCLUDED.kind,
    period_start = EXCLUDED.period_start,
    period_end   = EXCLUDED.period_end,
    data_summary = EXCLUDED.data_summary,
    insights     = EXCLUDED.insights
RETURNING id
"""


def _connect(database_url: str):
    import psycopg2
    from sync_db import _clean_database_url

    return psycopg2.connect(_clean_database_url(database_url), connect_timeout=10)


def _period_from_summary(summary: Optional[Dict]) -> tuple:
    """Derive a date range from the generator's data_summary when available."""
    if not isinstance(summary, dict):
        return (None, None)
    rng = summary.get("date_range") or ""
    if isinstance(rng, str) and " to " in rng:
        start, _, end = rng.partition(" to ")
        return (start.strip() or None, end.strip() or None)
    return (None, None)


def _row_from_payload(payload: Dict[str, Any], kind: str = "daily") -> Dict[str, Any]:
    summary = payload.get("data_summary")
    period_start, period_end = _period_from_summary(summary)
    return {
        "generated_at": payload.get("generated_at"),
        "model": payload.get("model"),
        "kind": kind,
        "running_fingerprint": payload.get("running_fingerprint") or None,
        "period_start": payload.get("period_start") or period_start,
        "period_end": payload.get("period_end") or period_end,
        "data_summary": json.dumps(summary, ensure_ascii=False) if summary is not None else None,
        "insights": json.dumps(payload.get("insights") or {}, ensure_ascii=False),
    }


def save_insight(payload: Dict[str, Any], kind: str = "daily") -> bool:
    """Persist one insights payload. Returns True on success, False otherwise.

    Never raises: AI insights are a non-fatal pipeline stage.
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL not set; skipping AI insights DB save.", file=sys.stderr)
        return False
    try:
        conn = _connect(database_url)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(CREATE_TABLE)
                    cur.execute(UPSERT, _row_from_payload(payload, kind))
                    row_id = cur.fetchone()
            print(f"AI insights saved to DB (id={row_id[0] if row_id else '?'}).")
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f"Warning: AI insights DB save failed: {exc}", file=sys.stderr)
        return False


def backfill_history(history_path: str) -> Dict[str, int]:
    """Import an existing ai_insights_history.json into the table.

    History entries have no data_summary (stripped when written), so those rows
    land with data_summary NULL. Entries without a fingerprint are skipped,
    since the table dedupes on it.
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    if not os.path.exists(history_path):
        return {"read": 0, "saved": 0, "skipped": 0}

    with open(history_path, "r", encoding="utf-8") as f:
        history: List[Dict] = json.load(f)
    if not isinstance(history, list):
        return {"read": 0, "saved": 0, "skipped": 0}

    saved = 0
    skipped = 0
    conn = _connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE)
        for entry in history:
            if not isinstance(entry, dict):
                skipped += 1
                continue
            if not entry.get("running_fingerprint"):
                skipped += 1
                continue
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(UPSERT, _row_from_payload(entry, "daily"))
                saved += 1
            except Exception as exc:
                print(f"  skip entry ({exc})", file=sys.stderr)
                skipped += 1
    finally:
        conn.close()
    return {"read": len(history), "saved": saved, "skipped": skipped}


if __name__ == "__main__":
    # Manual backfill:  python scripts/ai_insights_db.py --backfill
    if "--backfill" in sys.argv:
        path = os.path.join("site", "ai_insights_history.json")
        stats = backfill_history(path)
        print(f"Backfill: read={stats['read']} saved={stats['saved']} skipped={stats['skipped']}")
    else:
        print("Usage: python scripts/ai_insights_db.py --backfill")
