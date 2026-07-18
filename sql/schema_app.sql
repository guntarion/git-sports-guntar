-- App data schema (journal + todos) for git-sports-guntar.
-- Mirrors the object shapes in site/storage.js exactly so migration is 1:1.
-- Applied automatically by the API (CREATE ... IF NOT EXISTS); this file is the
-- canonical reference and can also be run manually:
--   psql "$DATABASE_URL" -f sql/schema_app.sql

CREATE TABLE IF NOT EXISTS journal_entries (
    id            TEXT PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    title         TEXT NOT NULL DEFAULT '',
    body          TEXT NOT NULL DEFAULT '',
    activity_id   TEXT,
    activity_date TEXT,
    activity_name TEXT,
    tags          JSONB NOT NULL DEFAULT '[]'::jsonb,
    source        TEXT NOT NULL DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS todos (
    id            TEXT PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    text          TEXT NOT NULL DEFAULT '',
    done          BOOLEAN NOT NULL DEFAULT false,
    done_at       TIMESTAMPTZ,
    priority      TEXT NOT NULL DEFAULT 'medium',
    due_date      TEXT,
    source        TEXT NOT NULL DEFAULT 'manual',
    source_detail TEXT
);

-- AI coaching insights. One row per distinct data state (running_fingerprint),
-- so re-running the pipeline on unchanged data updates rather than duplicates.
-- period_start/period_end are NULL for the daily "this month vs last month"
-- report and set for future on-demand analysis over an arbitrary date range.
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

-- Per-activity Running Economy, computed over a fixed km 2-4 window so runs of
-- different lengths stay comparable (see scripts/running_economy.py).
CREATE TABLE IF NOT EXISTS running_economy (
    activity_id             TEXT PRIMARY KEY,
    date                    DATE NOT NULL,
    re_ml_kg_km             NUMERIC(6,1) NOT NULL,
    re_rolling              NUMERIC(6,1),
    score                   INTEGER,
    rating                  TEXT,
    efficiency_index        NUMERIC(8,4),
    cardiac_cost            NUMERIC(7,1),
    vertical_ratio          NUMERIC(5,2),
    avg_cadence             INTEGER,
    avg_ground_contact      INTEGER,
    window_hr               NUMERIC(5,1),
    window_pace_secs_per_km NUMERIC(6,1),
    window_distance_m       NUMERIC(8,1),
    total_distance_m        NUMERIC(9,1),
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Garmin performance metrics over time (VO2max, endurance score, hill score,
-- HRV, race predictions, weight...). Long/narrow so new metric types need no
-- migration; `extra` keeps the raw payload for anything not modelled yet.
CREATE TABLE IF NOT EXISTS performance_metrics (
    id          BIGSERIAL PRIMARY KEY,
    metric      TEXT NOT NULL,
    date        DATE NOT NULL,
    value       NUMERIC(12,3),
    extra       JSONB,
    synced_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT performance_metrics_metric_date_key UNIQUE (metric, date)
);

-- Second-order per-activity metrics (see scripts/derived_metrics.py).
-- Kept separate from running_economy because they qualify different runs:
-- decoupling needs a long steady effort, RE needs a clean km 2-4 window.
CREATE TABLE IF NOT EXISTS activity_derived (
    activity_id     TEXT PRIMARY KEY,
    date            DATE NOT NULL,
    decoupling_pct  NUMERIC(6,2),
    trimp           NUMERIC(8,1),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_derived_date ON activity_derived(date DESC);
CREATE INDEX IF NOT EXISTS idx_re_date ON running_economy(date DESC);
CREATE INDEX IF NOT EXISTS idx_perf_metric_date ON performance_metrics(metric, date DESC);
CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_created   ON todos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_done      ON todos(done);
CREATE INDEX IF NOT EXISTS idx_ai_generated    ON ai_insights(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_kind         ON ai_insights(kind);
