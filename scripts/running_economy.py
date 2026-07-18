"""
Running Economy estimation from Garmin run data.

Garmin's own Running Economy needs an HRM 600 strap (it measures step speed
loss), which we do not have. But Garmin's unit — ml O2 / kg / km, lower is
better — is the standard physiological scale, and it decomposes as:

    RE (ml/kg/km) = VO2 (ml/kg/min) / speed (km/min)

so we only need to *estimate* VO2 instead of measuring it. We do that with the
standard %HRR ~ %VO2R linear bridge (the same mechanism behind Polar's Running
Index):

    hrr  = (hr - hr_rest) / (hr_max - hr_rest)
    vo2  = 3.5 + hrr * (vo2max_ref - 3.5)

IMPORTANT — vo2max_ref is a FROZEN constant, never the per-activity vo2_max
field. Garmin derives that field from the same HR/pace relationship this metric
measures, so feeding it in per-activity cancels the signal and flattens the
series.

## Why a fixed distance window

Measuring over the whole run makes the score track run *length*, not economy:
on this athlete's history, corr(distance, RE) was +0.527 and runs >=6 km scored
16.7 ml/kg/km worse than runs <6 km — larger than the baseline spread. That is
cardiac drift (HR climbs at constant pace), not a change in efficiency.

So every run is measured over the SAME window: kilometre splits 2..4. Skipping
split 1 drops HR lag and warm-up; stopping at 4 stops drift from accumulating.
That takes corr(distance, RE) to +0.04 — the confound is gone, and runs of any
length become comparable.

## Scoring

Absolute RE carries an unknown offset (vo2max_ref is a guess), so the 0-100
score is normalised against the runner's OWN history using a robust baseline
(median + MAD), not population norms. 50 = personal baseline, 15 points = 1
robust sigma, lower RE scores higher.
"""
from typing import Any, Dict, List, Optional
import statistics as st

RUN_TYPES = {"run", "trailrun", "virtualrun", "trail_run", "virtual_run",
             "treadmill_running", "indoor_running", "running"}
# Matched as substrings: Garmin reports e.g. "treadmill_running", which an
# exact-match set silently lets through.
TRAIL_MARKERS = ("trail",)
INDOOR_MARKERS = ("treadmill", "indoor", "virtual")

DEFAULTS: Dict[str, Any] = {
    "hr_max": 181,          # highest HR actually recorded in this athlete's runs
    "hr_rest": 54,          # Garmin wellness resting HR
    "vo2max_ref": 39.0,     # FROZEN reference; do not feed per-activity vo2_max
    "window_start": 1,      # 0-indexed: skip split 1 (warm-up / HR lag)
    "window_end": 4,        # exclusive -> splits 2,3,4
    # The window must be a genuine ~3 km of running, so only accept true
    # kilometre splits. Garmin sometimes emits merged laps (e.g. one 2996 m
    # "split"), which would silently stretch the window.
    "min_split_m": 800,
    "max_split_m": 1200,
    "hr_band_low": 0.65,    # easy/steady intensity band as a fraction of hr_max
    "hr_band_high": 0.85,
    "max_pace_secs": 900,   # existing project rule: exclude anomalous pace
    "max_split_cv": 0.06,   # <=6% pace CV -> steady state, excludes intervals
    "min_runs_for_score": 8,
    "rolling_window": 5,    # display as a rolling median of N runs
    "exclude_trail": True,
    "exclude_indoor": True,
}

# Garmin's published rating bands (ml/kg/km). Male / female thresholds.
RATING_BANDS = {
    "male": [(185, "Elite"), (190, "Superior"), (195, "Expert"), (205, "Well Trained"),
             (215, "Trained"), (225, "Intermediate")],
    "female": [(190, "Elite"), (195, "Superior"), (200, "Expert"), (210, "Well Trained"),
               (220, "Trained"), (230, "Intermediate")],
}


def rating_for(re_value: float, sex: str = "male") -> str:
    """Map an RE value onto Garmin's 7-tier rating."""
    for threshold, label in RATING_BANDS.get(sex, RATING_BANDS["male"]):
        if re_value < threshold:
            return label
    return "Recreational"


def params_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge running_economy settings from config.yaml over the defaults."""
    p = dict(DEFAULTS)
    cfg = (config or {}).get("running_economy") or {}
    for k, v in cfg.items():
        if k in p and v is not None:
            p[k] = v
    return p


def _kind(a: Dict) -> str:
    return (a.get("raw_type") or a.get("type") or "").lower()


def is_run(a: Dict) -> bool:
    return (a.get("type", "") or "").lower() in RUN_TYPES or _kind(a) in RUN_TYPES


def _is_trail(a: Dict) -> bool:
    return any(m in _kind(a) for m in TRAIL_MARKERS)


def _is_indoor(a: Dict) -> bool:
    """Treadmill/indoor runs must be excluded: pace comes from the
    accelerometer rather than GPS, so it is not comparable to outdoor pace
    (this athlete's treadmill runs show 92 cm stride at 138 spm vs 70 cm at
    153 spm outdoors). Garmin excludes them from Running Economy too."""
    return any(m in _kind(a) for m in INDOOR_MARKERS)


def _usable_splits(a: Dict, p: Dict) -> List[Dict]:
    """Only true kilometre splits with heart rate — see max_split_m note."""
    out = []
    for sp in (a.get("splits") or []):
        d = sp.get("distance") or 0
        if not (p["min_split_m"] <= d <= p["max_split_m"]):
            continue
        if not sp.get("avg_hr") or (sp.get("duration") or 0) <= 0:
            continue
        out.append(sp)
    return out


def compute_activity(a: Dict, p: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """Compute windowed Running Economy for one activity.

    Returns None when the run does not qualify (wrong type, too short, not
    steady, outside the easy/steady HR band...). Callers treat None as
    "not measurable", not as an error.
    """
    p = p or DEFAULTS
    if not is_run(a):
        return None
    if p["exclude_trail"] and _is_trail(a):
        return None
    if p["exclude_indoor"] and _is_indoor(a):
        return None
    if not (0 < (a.get("avg_pace_secs_per_km") or 99999) <= p["max_pace_secs"]):
        return None

    splits = _usable_splits(a, p)
    if len(splits) < p["window_end"]:
        return None
    window = splits[p["window_start"]:p["window_end"]]
    if not window:
        return None

    dist_m = sum(s["distance"] for s in window)
    dur_s = sum(s["duration"] for s in window)
    if dist_m <= 0 or dur_s <= 0:
        return None

    # Time-weighted HR across the window.
    hr = sum(s["avg_hr"] * s["duration"] for s in window) / dur_s
    if not (p["hr_band_low"] <= hr / p["hr_max"] <= p["hr_band_high"]):
        return None

    paces = [s["duration"] / (s["distance"] / 1000.0) for s in window]
    mean_pace = st.mean(paces)
    if len(paces) > 1 and mean_pace > 0:
        if st.pstdev(paces) / mean_pace > p["max_split_cv"]:
            return None  # intervals / fartlek — not steady state

    v_mpm = dist_m / (dur_s / 60.0)                     # m/min
    hrr = (hr - p["hr_rest"]) / (p["hr_max"] - p["hr_rest"])
    vo2 = 3.5 + hrr * (p["vo2max_ref"] - 3.5)           # ml/kg/min
    re = vo2 * 1000.0 / v_mpm                           # ml/kg/km

    # Assumption-free companions.
    ei = v_mpm / hr                                     # metres per heartbeat
    cardiac_cost = hr * mean_pace / 60.0                # beats per km

    # Form indicators (secondary — reported separately, never folded into RE).
    vertical_ratio = None
    if a.get("avg_vertical_osc") and a.get("avg_stride_len"):
        # VR% = vertical oscillation (cm) / stride length (m)
        vertical_ratio = round(a["avg_vertical_osc"] / (a["avg_stride_len"] / 100.0), 2)

    return {
        "activity_id": str(a.get("id") or ""),
        "date": a.get("date"),
        "re_ml_kg_km": round(re, 1),
        "efficiency_index": round(ei, 4),
        "cardiac_cost": round(cardiac_cost, 1),
        "window_hr": round(hr, 1),
        "window_pace_secs_per_km": round(mean_pace, 1),
        "window_distance_m": round(dist_m, 1),
        "window_splits": len(window),
        "vertical_ratio": vertical_ratio,
        "avg_cadence": a.get("avg_cadence"),
        "avg_ground_contact": a.get("avg_ground_contact"),
        "total_distance_m": a.get("distance"),
        "rating": rating_for(re),
    }


def _robust_baseline(values: List[float]) -> tuple:
    med = st.median(values)
    mad = 1.4826 * st.median([abs(v - med) for v in values])
    return med, max(mad, 3.0)  # floor prevents divide-by-noise on tight data


def compute_series(activities: List[Dict], p: Optional[Dict] = None) -> Dict[str, Any]:
    """Compute RE for every qualifying run and attach personal 0-100 scores.

    Scores are only assigned once there are enough qualifying runs to form a
    stable baseline; below that the caller should show "collecting data".
    """
    p = p or DEFAULTS
    items = [m for m in (compute_activity(a, p) for a in activities) if m]
    items.sort(key=lambda m: m.get("date") or "")

    if len(items) < p["min_runs_for_score"]:
        return {
            "items": items,
            "baseline": None,
            "enough_data": False,
            "needed": p["min_runs_for_score"],
        }

    values = [m["re_ml_kg_km"] for m in items]
    med, sigma = _robust_baseline(values)
    for m in items:
        raw = 50 + 15 * (med - m["re_ml_kg_km"]) / sigma
        m["score"] = int(max(0, min(100, round(raw))))

    # Rolling median smooths single-run noise from heat, fatigue, HR artefacts.
    w = p["rolling_window"]
    for i, m in enumerate(items):
        lo = max(0, i - w + 1)
        m["re_rolling"] = round(st.median([x["re_ml_kg_km"] for x in items[lo:i + 1]]), 1)

    return {
        "items": items,
        "baseline": {"median": round(med, 1), "sigma": round(sigma, 2), "n": len(items)},
        "enough_data": True,
        "latest": items[-1] if items else None,
    }
