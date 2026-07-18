// Small HTTP helpers: auth guard, JSON body parsing, responses.
import crypto from 'crypto';

export function sendJson(res, status, body) {
  res.status(status).setHeader('Content-Type', 'application/json');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(body));
}

// Constant-time compare to avoid leaking the token via timing.
function safeEqual(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

// Returns true if the request carries the correct Bearer token.
// Requires APP_AUTH_TOKEN to be configured; if it is not set, access is denied
// (fail closed) so private data is never accidentally exposed.
export function isAuthed(req) {
  const expected = process.env.APP_AUTH_TOKEN || '';
  if (!expected) return false;
  const header = req.headers['authorization'] || '';
  const m = /^Bearer\s+(.+)$/i.exec(header);
  if (!m) return false;
  return safeEqual(m[1].trim(), expected);
}

export function requireAuth(req, res) {
  if (isAuthed(req)) return true;
  const configured = Boolean(process.env.APP_AUTH_TOKEN);
  sendJson(res, 401, {
    error: 'unauthorized',
    detail: configured ? 'Invalid or missing token' : 'APP_AUTH_TOKEN not configured on server',
  });
  return false;
}

// Vercel populates req.body for JSON, but parse defensively for local/other runtimes.
export async function readBody(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  if (typeof req.body === 'string' && req.body) {
    try { return JSON.parse(req.body); } catch { return {}; }
  }
  const chunks = [];
  for await (const c of req) chunks.push(c);
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return {}; }
}
