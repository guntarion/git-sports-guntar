// Shared Postgres pool + lazy schema init for Vercel serverless functions.
// A single pool is reused across invocations on a warm instance via globalThis.
import pg from 'pg';

const { Pool } = pg;

// Strip psycopg2/Prisma-only query params that node-pg rejects.
function cleanUrl(url) {
  try {
    const u = new URL(url);
    ['connection_limit', 'pool_timeout', 'pgbouncer', 'sslaccept'].forEach((k) =>
      u.searchParams.delete(k)
    );
    return u.toString();
  } catch {
    return url;
  }
}

function makePool() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error('DATABASE_URL is not set');
  // SSL: opt-in via PGSSL=require (VPS Postgres over the public internet should
  // ideally use TLS). Default off to match the current server config.
  const ssl =
    (process.env.PGSSL || '').toLowerCase() === 'require'
      ? { rejectUnauthorized: false }
      : false;
  return new Pool({ connectionString: cleanUrl(url), ssl, max: 3, idleTimeoutMillis: 10000 });
}

export function getPool() {
  if (!globalThis.__gsPool) globalThis.__gsPool = makePool();
  return globalThis.__gsPool;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS journal_entries (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  activity_id TEXT,
  activity_date TEXT,
  activity_name TEXT,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  source TEXT NOT NULL DEFAULT 'manual'
);
CREATE TABLE IF NOT EXISTS todos (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  text TEXT NOT NULL DEFAULT '',
  done BOOLEAN NOT NULL DEFAULT false,
  done_at TIMESTAMPTZ,
  priority TEXT NOT NULL DEFAULT 'medium',
  due_date TEXT,
  source TEXT NOT NULL DEFAULT 'manual',
  source_detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_created ON todos(created_at DESC);
`;

export async function ensureSchema() {
  if (globalThis.__gsSchemaReady) return;
  await getPool().query(SCHEMA);
  globalThis.__gsSchemaReady = true;
}

export async function query(text, params) {
  await ensureSchema();
  return getPool().query(text, params);
}
