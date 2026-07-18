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

CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_created   ON todos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_done      ON todos(done);
