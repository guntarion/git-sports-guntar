// /api/todos — CRUD for todos (auth required).
//   GET                       -> list all (newest first)
//   POST {todo}               -> create one (id/created_at honored for migration)
//   POST {items:[...]}        -> bulk upsert (one-time localStorage import)
//   PATCH ?id=<id> {changes}  -> update fields (also used for toggle: {done, done_at})
//   POST  ?action=clearCompleted -> delete all done todos
//   DELETE ?id=<id>           -> delete
import { query } from './_lib/db.js';
import { requireAuth, readBody, sendJson } from './_lib/http.js';

function mapRow(r) {
  return {
    id: r.id,
    created_at: r.created_at instanceof Date ? r.created_at.toISOString() : r.created_at,
    updated_at: r.updated_at instanceof Date ? r.updated_at.toISOString() : r.updated_at,
    text: r.text,
    done: r.done,
    done_at: r.done_at instanceof Date ? r.done_at.toISOString() : r.done_at,
    priority: r.priority,
    due_date: r.due_date,
    source: r.source,
    source_detail: r.source_detail,
  };
}

const COLS = ['text', 'done', 'done_at', 'priority', 'due_date', 'source', 'source_detail'];

function genId() {
  return 't_' + Date.now() + '_' + Math.random().toString(16).slice(2, 6);
}

async function upsertOne(e) {
  const id = e.id || genId();
  const now = new Date().toISOString();
  const row = {
    id,
    created_at: e.created_at || now,
    updated_at: e.updated_at || now,
    text: e.text || '',
    done: Boolean(e.done),
    done_at: e.done_at ?? null,
    priority: e.priority || 'medium',
    due_date: e.due_date ?? null,
    source: e.source || 'manual',
    source_detail: e.source_detail ?? null,
  };
  const { rows } = await query(
    `INSERT INTO todos
       (id, created_at, updated_at, text, done, done_at, priority, due_date, source, source_detail)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
     ON CONFLICT (id) DO UPDATE SET
       updated_at=EXCLUDED.updated_at, text=EXCLUDED.text, done=EXCLUDED.done,
       done_at=EXCLUDED.done_at, priority=EXCLUDED.priority, due_date=EXCLUDED.due_date,
       source=EXCLUDED.source, source_detail=EXCLUDED.source_detail
     RETURNING *`,
    [row.id, row.created_at, row.updated_at, row.text, row.done, row.done_at,
     row.priority, row.due_date, row.source, row.source_detail]
  );
  return mapRow(rows[0]);
}

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  try {
    const url = new URL(req.url, 'http://x');
    const id = url.searchParams.get('id');
    const action = url.searchParams.get('action');

    if (req.method === 'GET') {
      const { rows } = await query('SELECT * FROM todos ORDER BY created_at DESC');
      return sendJson(res, 200, { items: rows.map(mapRow) });
    }

    if (req.method === 'POST' && action === 'clearCompleted') {
      const { rowCount } = await query('DELETE FROM todos WHERE done = true');
      return sendJson(res, 200, { ok: true, deleted: rowCount });
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
          sets.push(`${c}=$${i}`);
          vals.push(changes[c]);
          i++;
        }
      }
      if (!sets.length) return sendJson(res, 400, { error: 'no changes' });
      sets.push('updated_at=now()');
      vals.push(id);
      const { rows } = await query(
        `UPDATE todos SET ${sets.join(', ')} WHERE id=$${i} RETURNING *`,
        vals
      );
      if (!rows.length) return sendJson(res, 404, { error: 'not found' });
      return sendJson(res, 200, mapRow(rows[0]));
    }

    if (req.method === 'DELETE') {
      if (!id) return sendJson(res, 400, { error: 'missing id' });
      await query('DELETE FROM todos WHERE id=$1', [id]);
      return sendJson(res, 200, { ok: true });
    }

    return sendJson(res, 405, { error: 'method not allowed' });
  } catch (err) {
    return sendJson(res, 500, { error: 'server_error', detail: String(err && err.message || err) });
  }
}
