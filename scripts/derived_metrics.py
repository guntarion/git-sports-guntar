"""
Second-order metrics derived from run data.

Four indicators that say something the raw Garmin numbers do not:

1. Aerobic decoupling — how much efficiency drifts from the first half of a run
   to the second. The classic TrainingPeaks durability test: under ~5% means the
   aerobic system held up; a large positive value means HR climbed (or pace fell)
   as the run went on. Unlike Running Economy this is measured over the WHOLE
   run, because the drift *is* the signal here rather than the confound.

2. Training load (TRIMP) — zone-weighted minutes, so 30 min in zone 4 costs far
   more than 30 min in zone 1. Aggregated per ISO week.

3. Zone efficiency — metres per heartbeat within each HR zone, so improvement at
   easy intensity is not hidden by a change in how hard the runs were.

4. Endurance : VO2max ratio — endurance score per unit of aerobic capacity. Two
   runners with the same VO2max can differ a lot here; rising means endurance is
   improving faster than raw capacity.

Plus a combined recovery-balance series (HRV z-score minus load z-score) used to
flag possible overreaching without plotting two different scales on one axis.
"""
from typing import Any, Dict, List, Optional
import statistics as st
from datetime import date, datetime, timedelta

from running_economy import (
    DEFAULTS, _is_indoor, _is_trail, _usable_splits, is_run,
)

# Zone-weighted minutes. Standard TRIMP-style weighting: cost rises with intensity.
ZONE_WEIGHTS = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}

# Decoupling needs enough splits to form two halves that mean something.
MIN_SPLITS_DECOUPLING = 4


def _ef(distance_m: float, duration_s: float, hr: float) -> Optional[float]:
    """Efficiency factor: metres per minute per heartbeat."""
    if duration_s <= 0 or hr <= 0:
        return None
    return (distance_m / (duration_s / 60.0)) / hr


def aerobic_decoupling(a: Dict, p: Optional[Dict] = None) -> Optional[float]:
    """Percent drift in efficiency from first to second half of a run.

    Positive = efficiency fell (HR drifted up or pace fell). <5% is the
    conventional "aerobically sound" threshold. Returns None when the run is
    not a valid steady aerobic test.
    """
    p = p or DEFAULTS
    if not is_run(a) or _is_indoor(a) or _is_trail(a):
        return None
    splits = _usable_splits(a, p)
    if len(splits) < MIN_SPLITS_DECOUPLING:
        return None

    # Skip split 1 (warm-up / HR lag), then cut the remainder into halves by time.
    body = splits[1:]
    if len(body) < 2:
        return None
    total = sum(s["duration"] for s in body)
    if total <= 0:
        return None

    half_t, acc, cut = total / 2.0, 0.0, 0
    for i, s in enumerate(body):
        acc += s["duration"]
        if acc >= half_t:
            cut = i + 1
            break
    first, second = body[:cut], body[cut:]
    if not first or not second:
        return None

    def agg(group):
        d = sum(s["distance"] for s in group)
        t = sum(s["duration"] for s in group)
        hr = sum(s["avg_hr"] * s["duration"] for s in group) / t if t else 0
        return _ef(d, t, hr)

    ef1, ef2 = agg(first), agg(second)
    if not ef1 or not ef2:
        return None
    # Only meaningful for an easy/steady aerobic effort.
    hr_all = sum(s["avg_hr"] * s["duration"] for s in body) / total
    if not (p["hr_band_low"] <= hr_all / p["hr_max"] <= p["hr_band_high"]):
        return None
    return round((ef1 - ef2) / ef1 * 100.0, 2)


def trimp(a: Dict) -> Optional[float]:
    """Zone-weighted training load in weighted-minutes."""
    zones = a.get("hr_zones") or []
    if not zones:
        return None
    total = 0.0
    for z in zones:
        zn = z.get("zone")
        secs = z.get("seconds") or 0
        if zn in ZONE_WEIGHTS and secs > 0:
            total += (secs / 60.0) * ZONE_WEIGHTS[zn]
    return round(total, 1) if total > 0 else None


def _zone_bounds(a: Dict) -> List[tuple]:
    """(zone, low_bpm) pairs from the activity's own zone table, ascending."""
    out = []
    for z in (a.get("hr_zones") or []):
        if z.get("zone") and z.get("low_bpm"):
            out.append((z["zone"], z["low_bpm"]))
    out.sort(key=lambda x: x[1])
    return out


def zone_efficiency(activities: List[Dict], p: Optional[Dict] = None) -> Dict[str, Any]:
    """Metres-per-heartbeat within each HR zone, pooled across runs.

    Splits are bucketed by their own average HR using that activity's zone
    boundaries, so a change in zone setup does not silently shift the buckets.
    """
    p = p or DEFAULTS
    buckets: Dict[int, List[float]] = {}
    for a in activities:
        if not is_run(a) or _is_indoor(a) or _is_trail(a):
            continue
        bounds = _zone_bounds(a)
        if not bounds:
            continue
        for s in _usable_splits(a, p):
            hr = s["avg_hr"]
            zone = None
            for zn, low in bounds:
                if hr >= low:
                    zone = zn
            if zone is None:
                continue
            ei = _ef(s["distance"], s["duration"], hr)
            if ei:
                buckets.setdefault(zone, []).append(ei)
    return {
        f"z{zn}": {"ei": round(st.median(v), 4), "splits": len(v)}
        for zn, v in sorted(buckets.items()) if v
    }


def _iso_week_start(day: str) -> str:
    d = datetime.strptime(day, "%Y-%m-%d").date()
    return (d - timedelta(days=d.weekday())).isoformat()


def weekly_load(activities: List[Dict]) -> Dict[str, float]:
    """ISO-week -> summed TRIMP across all activities (not only runs: total
    stress on the body is what matters for recovery)."""
    out: Dict[str, float] = {}
    for a in activities:
        d = a.get("date")
        t = trimp(a)
        if not d or not t:
            continue
        wk = _iso_week_start(d)
        out[wk] = round(out.get(wk, 0.0) + t, 1)
    return out


def _z(values: List[float]) -> List[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    m = st.mean(values)
    s = st.pstdev(values) or 1.0
    return [(v - m) / s for v in values]


def recovery_balance(hrv_series: List[Dict], load_by_week: Dict[str, float]) -> List[Dict]:
    """HRV z-score minus training-load z-score, per week.

    Positive = HRV is holding up relative to the load being carried.
    Persistently negative = load rising while HRV falls, the classic
    overreaching pattern. Expressed as one derived series so we never plot two
    incompatible scales against a shared axis.
    """
    if not hrv_series or not load_by_week:
        return []
    # Weekly mean HRV
    weekly_hrv: Dict[str, List[float]] = {}
    for r in hrv_series:
        d, v = r.get("date"), r.get("value")
        if not d or v is None:
            continue
        weekly_hrv.setdefault(_iso_week_start(d), []).append(float(v))

    weeks = sorted(set(weekly_hrv) & set(load_by_week))
    if len(weeks) < 3:
        return []
    hrv_vals = [st.mean(weekly_hrv[w]) for w in weeks]
    load_vals = [load_by_week[w] for w in weeks]
    zh, zl = _z(hrv_vals), _z(load_vals)
    return [
        {
            "date": w,
            "value": round(zh[i] - zl[i], 3),
            "hrv": round(hrv_vals[i], 1),
            "load": round(load_vals[i], 1),
        }
        for i, w in enumerate(weeks)
    ]


def endurance_vo2_ratio(endurance: List[Dict], vo2: List[Dict]) -> List[Dict]:
    """Endurance score per unit VO2max, matched to the most recent VO2max
    at or before each endurance reading."""
    if not endurance or not vo2:
        return []
    vo2_sorted = sorted([r for r in vo2 if r.get("value")], key=lambda r: r["date"])
    out = []
    for e in sorted(endurance, key=lambda r: r["date"]):
        if not e.get("value"):
            continue
        prior = [v for v in vo2_sorted if v["date"] <= e["date"]]
        if not prior:
            continue
        v = float(prior[-1]["value"])
        if v <= 0:
            continue
        out.append({"date": e["date"], "value": round(float(e["value"]) / v, 1)})
    return out


def compute_per_activity(activities: List[Dict], p: Optional[Dict] = None) -> List[Dict]:
    """Per-activity decoupling + TRIMP for everything that qualifies."""
    p = p or DEFAULTS
    rows = []
    for a in activities:
        aid = str(a.get("id") or "")
        if not aid or not a.get("date"):
            continue
        dec = aerobic_decoupling(a, p)
        tri = trimp(a)
        if dec is None and tri is None:
            continue
        rows.append({
            "activity_id": aid,
            "date": a.get("date"),
            "decoupling_pct": dec,
            "trimp": tri,
        })
    rows.sort(key=lambda r: r["date"])
    return rows
