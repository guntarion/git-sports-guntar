// /api/locations — session locations and GPS routes.
//
// AUTH REQUIRED, without exception. Start coordinates of a run typically
// disclose a home address, so this endpoint is never public — unlike
// /api/performance, which has a public read path.
//
//   GET /api/locations                 -> places summary + activities (no routes)
//   GET /api/locations?routes=1        -> include full route polylines
//   GET /api/locations?type=running    -> filter by sport (substring match)
//   GET /api/locations?place=Bandung   -> filter by place
import { query } from './_lib/db.js';
import { requireAuth, sendJson } from './_lib/http.js';

export default async function handler(req, res) {
  if (!requireAuth(req, res)) return;
  if (req.method !== 'GET') return sendJson(res, 405, { error: 'method not allowed' });

  try {
    const url = new URL(req.url, 'http://x');
    const withRoutes = url.searchParams.get('routes') === '1';
    const type = url.searchParams.get('type');
    const place = url.searchParams.get('place');

    const where = [];
    const params = [];
    if (type) { params.push(`%${type}%`); where.push(`type ILIKE $${params.length}`); }
    if (place) { params.push(place); where.push(`location_name = $${params.length}`); }
    const clause = where.length ? `WHERE ${where.join(' AND ')}` : '';

    const cols = `activity_id, date, type, name, location_name,
                  start_lat, start_lon, end_lat, end_lon,
                  min_lat, max_lat, min_lon, max_lon, distance_m, route_points`
      + (withRoutes ? ', route' : '');

    const [rows, places, sports] = await Promise.all([
      query(`SELECT ${cols} FROM activity_locations ${clause} ORDER BY date DESC`, params),
      query(
        `SELECT location_name AS place, COUNT(*)::int AS sessions,
                SUM(distance_m)::float AS distance_m,
                MIN(date) AS first_date, MAX(date) AS last_date,
                AVG(start_lat)::float AS lat, AVG(start_lon)::float AS lon
           FROM activity_locations
          WHERE location_name IS NOT NULL AND location_name <> ''
          GROUP BY location_name ORDER BY COUNT(*) DESC`
      ),
      query(`SELECT type, COUNT(*)::int AS n FROM activity_locations
              GROUP BY type ORDER BY COUNT(*) DESC`),
    ]);

    const iso = (d) => (d instanceof Date ? d.toISOString().slice(0, 10) : d);
    const activities = rows.rows.map((r) => ({
      id: r.activity_id,
      date: iso(r.date),
      type: r.type,
      name: r.name,
      place: r.location_name,
      start: r.start_lat !== null ? [Number(r.start_lat), Number(r.start_lon)] : null,
      end: r.end_lat !== null ? [Number(r.end_lat), Number(r.end_lon)] : null,
      bbox: r.min_lat !== null
        ? [Number(r.min_lat), Number(r.min_lon), Number(r.max_lat), Number(r.max_lon)]
        : null,
      distance_m: r.distance_m === null ? null : Number(r.distance_m),
      route_points: r.route_points,
      route: withRoutes ? (r.route || null) : undefined,
    }));

    return sendJson(res, 200, {
      activities,
      places: places.rows.map((p) => ({
        place: p.place,
        sessions: p.sessions,
        distance_km: p.distance_m ? Math.round(p.distance_m / 100) / 10 : 0,
        first_date: iso(p.first_date),
        last_date: iso(p.last_date),
        center: [Number(p.lat), Number(p.lon)],
      })),
      sports: sports.rows.map((s) => ({ type: s.type, count: s.n })),
      total: activities.length,
      with_routes: withRoutes,
    });
  } catch (err) {
    return sendJson(res, 500, { error: 'server_error', detail: String((err && err.message) || err) });
  }
}
