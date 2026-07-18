// /api/journal — CRUD for journal entries (auth required).
//   GET                      -> list all (newest first)
//   POST {entry}             -> create one (id/created_at honored for migration)
//   POST {items:[...]}       -> bulk upsert (used by one-time localStorage import)
//   PATCH  ?id=<id> {changes}-> update fields
//   DELETE ?id=<id>          -> delete
import { query } from './_lib/db.js';
import { requireAuth, readBody, sendJson } from './_lib/http.js';

function mapRow(r) {
  return {
    id: r.id,
    created_at: r.created_at instanceof Date ? r.created_at.toISOString() : r.created_at,
    updated_at: r.updated_at instanceof Date ? r.updated_at.toISOString() : r.updated_at,
    title: r.title,
    body: r.body,
    activity_id: r.activity_id,
    activity_date: r.activity_date,
    activity_name: r.activity_name,
    tags: Array.isArray(r.tags) ? r.tags : [],
    source: r.source,
  };
}

const COLS = ['title', 'body', 'activity_id', 'activity_date', 'activity_name', 'tags', 'source'];

function genId() {
  return 'j_' + Date.now() + '_' + Math.random().toString(16).slice(2, 6);
}

async function upsertOne(e) {
  const id = e.id || genId();
  const now = new Date().toISOString();
  const row = {
    id,
    created_at: e.created_at || now,
    updated_at: e.updated_at || now,
    title: e.title || '',
    body: e.body || '',
    activity_id: e.activity_id ?? null,
    activity_date: e.activity_date ?? null,
    activity_name: e.activity_name ?? null,
    tags: JSON.stringify(Array.isArray(e.tags) ? e.tags : []),
    source: e.source || 'manual',
  };
  const { rows } = await query(
    `INSERT INTO journal_entries
       (id, created_at, updated_at, title, body, activity_id, activity_date, activity_name, tags, source)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)
     ON CONFLICT (id) DO UPDATE SET
       updated_at=EXCLUDED.updated_at, title=EXCLUDED.title, body=EXCLUDED.body,
       activity_id=EXCLUDED.activity_id, activity_date=EXCLUDED.activity_date,
       activity_name=EXCLUDED.activity_name, tags=EXCLUDED.tags, source=EXCLUDED.source
     RETURNING *`,
    [row.id, row.created_at, row.updated_at, row.title, row.body, row.activity_id,
     row.activity_date, row.activity_name, row.tags, row.source]
  );
  return mapRow(rows[0]);
}

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  try {
    const url = new URL(req.url, 'http://x');
    const id = url.searchParams.get('id');

    if (req.method === 'GET') {
      const { rows } = await query('SELECT * FROM journal_entries ORDER BY created_at DESC');
      return sendJson(res, 200, { items: rows.map(mapRow) });
    }

    if (req.method === 'POST') {
      const body = await readBody(req);
      if (Array.isArray(body.items)) {
        const out = [];
        for (const e of body.items) out.push(await upsertOne(e));
        return sendJson(res, 200, { items: out, imported: out.length });
      }
      return sendJson(res, 201, await upsertOne(body));
    }

    if (req.method === 'PATCH') {
      if (!id) return sendJson(res, 400, { error: 'missing id' });
      const changes = await readBody(req);
      const sets = [];
      const vals = [];
      let i = 1;
      for (const c of COLS) {
        if (c in changes) {
          if (c === 'tags') {
            sets.push(`tags=$${i}::jsonb`);
            vals.push(JSON.stringify(Array.isArray(changes.tags) ? changes.tags : []));
          } else {
            sets.push(`${c}=$${i}`);
            vals.push(changes[c]);
          }
          i++;
        }
      }
      sets.push(`updated_at=now()`);
      vals.push(id);
      const { rows } = await query(
        `UPDATE journal_entries SET ${sets.join(', ')} WHERE id=$${i} RETURNING *`,
        vals
      );
      if (!rows.length) return sendJson(res, 404, { error: 'not found' });
      return sendJson(res, 200, mapRow(rows[0]));
    }

    if (req.method === 'DELETE') {
      if (!id) return sendJson(res, 400, { error: 'missing id' });
      await query('DELETE FROM journal_entries WHERE id=$1', [id]);
      return sendJson(res, 200, { ok: true });
    }

    return sendJson(res, 405, { error: 'method not allowed' });
  } catch (err) {
    return sendJson(res, 500, { error: 'server_error', detail: String(err && err.message || err) });
  }
}
