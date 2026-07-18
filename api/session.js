// /api/session — validate the auth token the browser holds.
//   GET -> 200 {ok:true} if the Bearer token is correct, else 401.
// Used by the frontend login gate to verify the entered password.
import { isAuthed, sendJson } from './_lib/http.js';

export default async function handler(req, res) {
  if (isAuthed(req)) return sendJson(res, 200, { ok: true });
  return sendJson(res, 401, { ok: false, configured: Boolean(process.env.APP_AUTH_TOKEN) });
}
