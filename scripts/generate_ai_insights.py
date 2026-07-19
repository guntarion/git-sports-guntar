"""
Generate AI-powered running insights using Qwen API.

Reads activities.json, builds an ACTOR-framed prompt,
calls Qwen (DashScope OpenAI-compatible endpoint),
and writes site/ai_insights.json.

Requires QWEN_API_KEY environment variable.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

ACTIVITIES_PATH = os.path.join("site", "activities.json")
OUTPUT_PATH = os.path.join("site", "ai_insights.json")
HISTORY_PATH = os.path.join("site", "ai_insights_history.json")
MAX_HISTORY = 52  # ~1 year of weekly entries
QWEN_ENDPOINT = os.environ.get(
    "QWEN_ENDPOINT",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
)
QWEN_MODEL = "qwen-plus"
# Bump when the prompt or the data summary changes shape. It is part of the
# regeneration fingerprint, so an improved prompt takes effect on the next run
# instead of waiting for the athlete's data to happen to change.
PROMPT_VERSION = "v2-recovery-aware"

RUNNING_TYPES = {"run", "trailrun", "virtualrun", "trail_run", "virtual_run"}


def _is_running(a: Dict) -> bool:
    return (a.get("type") or "").lower() in RUNNING_TYPES or \
           (a.get("raw_type") or "").lower() in RUNNING_TYPES


def _month_key(date_str: str) -> str:
    return date_str[:7] if date_str else ""


def _build_data_summary(activities: List[Dict]) -> Dict[str, Any]:
    """Build a compact data summary to feed into the AI prompt."""
    runs = [a for a in activities if _is_running(a) and (a.get("distance") or 0) > 500]
    if not runs:
        return {"error": "No running activities found"}

    runs.sort(key=lambda a: a.get("date", ""))

    now = datetime.utcnow()
    this_month = now.strftime("%Y-%m")
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    days_left = (now.replace(month=now.month % 12 + 1, day=1) - now).days if now.month < 12 else \
                (now.replace(year=now.year + 1, month=1, day=1) - now).days

    prior_months = []
    y, m = now.year, now.month
    for _ in range(4):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        prior_months.append(f"{y:04d}-{m:02d}")

    def month_stats(runs_list, mk):
        mr = [a for a in runs_list if _month_key(a.get("date", "")) == mk]
        if not mr:
            return None
        dists = [a.get("distance", 0) for a in mr]
        paces = [a["avg_pace_secs_per_km"] for a in mr if 0 < a.get("avg_pace_secs_per_km", 0) < 900]
        hrs = [a["avg_hr"] for a in mr if a.get("avg_hr", 0) > 0]
        tes = [a["aerobic_te"] for a in mr if a.get("aerobic_te", 0) > 0]
        cadences = [a["avg_cadence"] for a in mr if a.get("avg_cadence", 0) > 0]
        # HR zones
        zone_secs = [0, 0, 0, 0, 0, 0]
        for a in mr:
            for z in (a.get("hr_zones") or []):
                if 1 <= z.get("zone", 0) <= 5:
                    zone_secs[z["zone"]] += z.get("seconds", 0)
        # Efficiency
        effs = []
        for a in mr:
            p = a.get("avg_pace_secs_per_km", 0)
            h = a.get("avg_hr", 0)
            if 0 < p < 900 and h > 50:
                effs.append(round((1000 / p) / h * 1000, 2))

        return {
            "month": mk,
            "runs": len(mr),
            "total_km": round(sum(dists) / 1000, 1),
            "avg_pace_secs": round(sum(paces) / len(paces)) if paces else None,
            "avg_hr": round(sum(hrs) / len(hrs)) if hrs else None,
            "avg_aerobic_te": round(sum(tes) / len(tes), 1) if tes else None,
            "avg_cadence": round(sum(cadences) / len(cadences)) if cadences else None,
            "avg_efficiency": round(sum(effs) / len(effs), 2) if effs else None,
            "zone_pct": {
                f"z{i}": round(zone_secs[i] / max(sum(zone_secs), 1) * 100)
                for i in range(1, 6)
            },
            "longest_km": round(max(dists) / 1000, 1),
            "best_pace_secs": min(paces) if paces else None,
        }

    # Last 10 runs: five was too short a window to see a pattern, and the
    # model kept commenting on single sessions as if they were trends.
    recent = runs[-10:]
    recent_summary = []
    for a in recent:
        recent_summary.append({
            "date": a.get("date"),
            "distance_km": round(a.get("distance", 0) / 1000, 1),
            "pace_min_km": round(a.get("avg_pace_secs_per_km", 0) / 60, 2) if a.get("avg_pace_secs_per_km") else None,
            "avg_hr": a.get("avg_hr"),
            "cadence": a.get("avg_cadence"),
            "aerobic_te": a.get("aerobic_te"),
            "vo2_max": a.get("vo2_max"),
            "stride_len": a.get("avg_stride_len"),
            "ground_contact": a.get("avg_ground_contact"),
            "vertical_osc": a.get("avg_vertical_osc"),
        })

    summary = {
        "total_runs": len(runs),
        "total_km": round(sum(a.get("distance", 0) for a in runs) / 1000, 1),
        "date_range": f"{runs[0].get('date')} to {runs[-1].get('date')}",
        "this_month": month_stats(runs, this_month),
        "last_month": month_stats(runs, last_month),
        "months_back": [m for m in (month_stats(runs, k) for k in prior_months) if m],
        "days_left_this_month": days_left,
        "recent_runs": recent_summary,
    }

    # Recovery, load and efficiency context from PostgreSQL. Without this the
    # coach advises on training while blind to sleep, HRV and accumulated load.
    try:
        from ai_context import safe_build

        ctx = safe_build()
        if ctx:
            summary.update(ctx)
    except Exception as exc:
        print(f"  AI context unavailable: {exc}", file=sys.stderr)

    return summary


def _build_prompt(data_summary: Dict) -> str:
    """Build the ACTOR-framed prompt.

    The earlier version saw only monthly aggregates plus five runs, so it could
    not tell whether a hard week was earned or reckless. It now receives the
    recovery, load and efficiency context too, and is explicitly required to
    reconcile them before prescribing anything.
    """
    data_json = json.dumps(data_summary, indent=2, ensure_ascii=False)
    days_left = data_summary.get("days_left_this_month", 0)

    return f"""## AGENT
You are Coach RunAnalytica — an elite running coach and sports scientist with 15 years
coaching recreational runners. You specialise in heart-rate-based training, periodisation,
recovery management and data-driven analysis of Garmin metrics.

## CONTEXT
A recreational runner's full training dataset is below. Beyond the runs themselves it
includes recovery (HRV, sleep, resting HR, training readiness, body battery, stress),
accumulated load (acute vs chronic, ACWR, weekly TRIMP, recovery balance) and efficiency
(Running Economy in ml O2/kg/km where LOWER is better, aerobic decoupling, VO2max,
best efforts, per-zone efficiency).

```json
{data_json}
```

Reading notes so you interpret the fields correctly:
- `running_economy`: LOWER is better. `rolling_median` is more trustworthy than any single run.
- `aerobic_decoupling_pct`: under 5% means the aerobic system held up over the run.
- `recovery_balance`: HRV z-score minus load z-score. Below 0 means load is outpacing recovery.
- `acwr`: acute:chronic workload ratio. Roughly 0.8–1.3 is the usual safe band; above ~1.5 is
  a spike, below ~0.8 is detraining.
- Trend objects give `recent_avg` vs `baseline_avg`, so judge direction, not just level.
- Absent fields mean "not measured", never "zero". Say so rather than inventing a value.

## TASK
Work through these in order. Later sections must be consistent with earlier ones.

1. **RECOVERY & READINESS FIRST.** Before any training advice, judge whether this athlete is
   recovered. Weigh HRV vs baseline, sleep duration and debt, resting HR direction, training
   readiness, recovery balance and ACWR. State the verdict plainly.

2. **MONTHLY PERFORMANCE REVIEW.** This month vs last month: total km, runs, avg pace, avg HR,
   aerobic TE, efficiency, cadence. Give current, previous, change and verdict for each, then
   name the single most notable finding. Use `months_back` to say whether it is a real trend
   or a one-month blip.

3. **GOAL TRACKER.** What is needed in the remaining {days_left} days to match last month.
   Be concrete: "X.X km across Y sessions". If recovery is poor, say plainly that chasing the
   number is the wrong call rather than encouraging it anyway.

4. **TRAINING INSIGHTS.** 3–5 insights, each citing actual numbers. Prefer insights that
   connect two domains — e.g. how sleep debt shows up in Running Economy, or how a load spike
   tracks with decoupling — over restating one metric.

5. **RECOMMENDATIONS.** Exactly 3, for the coming week, immediately actionable and specific
   ("Zone 2, HR under 135, 5 km easy on Tuesday" — not "run more"). **Each must be consistent
   with the readiness verdict in step 1.** Do not prescribe intensity or volume increases when
   recovery indicators are poor; prescribe the recovery action instead and say what would have
   to improve before the harder work makes sense.

6. **RISK FLAGS.** Any overtraining, injury or illness risk signals — load spikes, chronic
   sleep debt, HRV suppression, rising resting HR, worsening decoupling. Empty list if genuinely none.

7. **WEEKLY FOCUS.** A theme plus 2–3 session types that follow from the above.

## OUTPUT
Return ONLY valid JSON (no markdown, no code fences) with exactly this structure:
{{
  "readiness": {{
    "status": "recovered | adequate | compromised",
    "score_0_100": 0,
    "drivers": ["metric-specific reason with numbers"],
    "guidance": "one sentence on what this means for the coming week"
  }},
  "monthly_review": {{
    "summary": "1-2 sentence overall assessment",
    "metrics": [
      {{ "name": "Total Distance", "current": "X.X km", "previous": "Y.Y km", "change": "+/-Z.Z km", "verdict": "improved" }}
    ],
    "highlight": "the single most notable finding in one sentence"
  }},
  "goal_tracker": {{
    "km_this_month": 0, "km_last_month": 0, "km_remaining": 0,
    "sessions_this_month": 0, "sessions_last_month": 0, "sessions_remaining": 0,
    "projection": "On track / Behind / Ahead",
    "message": "specific narrative, including whether chasing it is advisable"
  }},
  "insights": [
    {{ "category": "aerobic_efficiency", "title": "...", "body": "...", "severity": "positive" }}
  ],
  "recommendations": [
    {{ "action": "...", "reason": "...", "priority": "high" }}
  ],
  "risk_flags": [
    {{ "risk": "...", "evidence": "numbers that show it", "severity": "warning", "action": "..." }}
  ],
  "weekly_focus": {{ "theme": "...", "description": "...", "suggested_sessions": ["..."] }}
}}

## RULES
- Metric units only (km, min/km, bpm, spm, ml/kg/km).
- Always cite actual numbers from the data; never generic advice.
- Compare against this runner's OWN history, never population benchmarks.
- Practical for a recreational runner training 3–5 times a week.
- If data for a section is missing, say so honestly instead of inventing it.
- Tone: encouraging but straight — do not cheer on a training increase that the recovery data
  contradicts.
- verdict ∈ improved | declined | stable · severity ∈ positive | warning | neutral ·
  priority ∈ high | medium · status ∈ recovered | adequate | compromised
- Return ONLY the JSON object."""


def _call_qwen(prompt: str, api_key: str) -> Optional[Dict]:
    """Call Qwen API and parse JSON response."""
    import urllib.request
    import urllib.error

    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": "You are a JSON-only API. Return only valid JSON, no markdown formatting, no code fences."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4000,
    }

    req = urllib.request.Request(
        QWEN_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Qwen API error {e.code}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Qwen API request failed: {e}", file=sys.stderr)
        return None

    content = (result.get("choices") or [{}])[0].get("message", {}).get("content", "")
    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print(f"Failed to parse Qwen response as JSON: {content[:500]}", file=sys.stderr)
        return None


def _running_fingerprint(activities: List[Dict]) -> str:
    """Build a fingerprint from running activities to detect changes."""
    runs = [a for a in activities if _is_running(a) and (a.get("distance") or 0) > 500]
    runs.sort(key=lambda a: a.get("date", ""))
    count = len(runs)
    latest_date = runs[-1].get("date", "") if runs else ""
    total_dist = round(sum(a.get("distance", 0) for a in runs))
    return f"{PROMPT_VERSION}:{count}:{latest_date}:{total_dist}"


def _should_regenerate(activities: List[Dict]) -> bool:
    """Check if running data has changed since last AI insights generation."""
    if not os.path.exists(OUTPUT_PATH):
        return True
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        return True

    old_summary = existing.get("data_summary") or {}
    old_fp = existing.get("running_fingerprint", "")

    # If no fingerprint stored (old format), regenerate
    if not old_fp:
        return True

    new_fp = _running_fingerprint(activities)
    if new_fp != old_fp:
        return True

    print(f"Running data unchanged (fingerprint: {new_fp}); keeping existing AI insights.")
    return False


def _append_to_history(entry: Dict[str, Any]) -> None:
    """Append a new AI insights entry to the history file (newest first)."""
    history: List[Dict] = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []

    # Strip data_summary from history entries to save space
    hist_entry = {k: v for k, v in entry.items() if k != "data_summary"}
    history.insert(0, hist_entry)
    history = history[:MAX_HISTORY]

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"AI insights history updated ({len(history)} entries in {HISTORY_PATH})")


def generate_ai_insights() -> bool:
    """Main entry point. Returns True on success."""
    api_key = os.environ.get("QWEN_API_KEY", "").strip()
    if not api_key:
        print("QWEN_API_KEY not set; skipping AI insights.", file=sys.stderr)
        return False

    if not os.path.exists(ACTIVITIES_PATH):
        print(f"{ACTIVITIES_PATH} not found; skipping AI insights.", file=sys.stderr)
        return False

    with open(ACTIVITIES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    activities = data.get("activities") or []
    if not activities:
        print("No activities in data; skipping AI insights.", file=sys.stderr)
        return False

    if not _should_regenerate(activities):
        return True

    print("Building AI data summary...")
    summary = _build_data_summary(activities)

    if "error" in summary:
        print(f"Data summary error: {summary['error']}", file=sys.stderr)
        return False

    print("Generating ACTOR prompt and calling Qwen API...")
    prompt = _build_prompt(summary)
    insights = _call_qwen(prompt, api_key)

    if not insights:
        print("AI insights generation failed.", file=sys.stderr)
        return False

    output = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": QWEN_MODEL,
        "prompt_version": PROMPT_VERSION,
        "running_fingerprint": _running_fingerprint(activities),
        "data_summary": summary,
        "insights": insights,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Append to history (newest first, capped at MAX_HISTORY)
    _append_to_history(output)

    # Persist to PostgreSQL so insights outlive the static JSON files.
    # Non-fatal: a DB outage must not fail the pipeline.
    try:
        from ai_insights_db import save_insight

        save_insight(output, kind="daily")
    except Exception as exc:
        print(f"Warning: could not save AI insights to DB: {exc}", file=sys.stderr)

    print(f"AI insights written to {OUTPUT_PATH}")
    return True


if __name__ == "__main__":
    success = generate_ai_insights()
    raise SystemExit(0 if success else 1)
