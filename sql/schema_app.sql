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

CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_created   ON todos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_done      ON todos(done);
CREATE INDEX IF NOT EXISTS idx_ai_generated    ON ai_insights(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_kind         ON ai_insights(kind);
