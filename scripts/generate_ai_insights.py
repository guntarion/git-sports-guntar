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
QWEN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen-plus"

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

    # Last 5 runs for context
    recent = runs[-5:]
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

    return {
        "total_runs": len(runs),
        "total_km": round(sum(a.get("distance", 0) for a in runs) / 1000, 1),
        "date_range": f"{runs[0].get('date')} to {runs[-1].get('date')}",
        "this_month": month_stats(runs, this_month),
        "last_month": month_stats(runs, last_month),
        "days_left_this_month": days_left,
        "recent_runs": recent_summary,
    }


def _build_prompt(data_summary: Dict) -> str:
    """Build the ACTOR-framed prompt."""
    data_json = json.dumps(data_summary, indent=2, ensure_ascii=False)

    return f"""## AGENT (Role Definition)
You are Coach RunAnalytica — an elite running coach and sports scientist with 15 years of experience coaching recreational runners. You specialize in heart rate-based training, periodization, and data-driven performance analysis using Garmin metrics (pace, HR zones, cadence, stride length, ground contact time, vertical oscillation, VO2 max, training effect).

## CONTEXT (Background)
You are analyzing running data for a recreational runner who uses a Garmin watch. The data comes from their personal running log and includes per-activity stats, HR zone distributions, and monthly aggregates. They are focused on health and continuous improvement. They want actionable, data-specific guidance — not generic running advice.

Here is their data:
```json
{data_json}
```

## TASK (Instructions)
Analyze the provided data and produce these sections:

1. **MONTHLY PERFORMANCE REVIEW**: Compare this month vs last month across: total km, number of runs, avg pace, avg HR, avg aerobic TE, aerobic efficiency, cadence. For each metric, state current value, previous value, change amount, and whether it improved or declined. Identify the single most notable finding.

2. **GOAL TRACKER**: Calculate what the runner needs to do in the remaining {data_summary.get('days_left_this_month', 0)} days to match or exceed last month's totals. Be specific: "You need X.X more km across Y sessions."

3. **TRAINING INSIGHTS**: Provide 3-4 specific insights based on the data. Categories: aerobic_efficiency, hr_zones, running_form, training_load, recovery. Each insight should reference actual numbers from the data.

4. **RECOMMENDATIONS**: Give exactly 3 actionable recommendations for the coming week. Each must reference specific data points and be immediately actionable (e.g., "Do your next run at Zone 2 HR <135bpm for 5km" rather than "run more").

5. **WEEKLY FOCUS**: A theme for the coming week with 2-3 suggested session types.

## OUTPUTS (Expected Format)
Return ONLY valid JSON (no markdown, no code fences) with this exact structure:
{{
  "monthly_review": {{
    "summary": "1-2 sentence overall assessment",
    "metrics": [
      {{ "name": "Total Distance", "current": "X.X km", "previous": "Y.Y km", "change": "+/-Z.Z km", "verdict": "improved" }}
    ],
    "highlight": "The single most notable finding in one sentence"
  }},
  "goal_tracker": {{
    "km_this_month": 0,
    "km_last_month": 0,
    "km_remaining": 0,
    "sessions_this_month": 0,
    "sessions_last_month": 0,
    "sessions_remaining": 0,
    "projection": "On track / Behind / Ahead",
    "message": "Specific narrative about what to do"
  }},
  "insights": [
    {{ "category": "aerobic_efficiency", "title": "...", "body": "...", "severity": "positive" }}
  ],
  "recommendations": [
    {{ "action": "...", "reason": "...", "priority": "high" }}
  ],
  "weekly_focus": {{
    "theme": "...",
    "description": "...",
    "suggested_sessions": ["..."]
  }}
}}

## RULES (Guidelines)
- Use metric units only (km, min/km, bpm, spm)
- Be specific with numbers — always reference actual values from the data
- Compare against the runner's OWN history, never generic population benchmarks
- Keep recommendations practical for a recreational runner (3-5 runs/week)
- If data is insufficient for a section, include the section but note it honestly
- Tone: encouraging, data-driven, like a supportive coach who respects the runner's intelligence
- verdicts must be exactly one of: "improved", "declined", "stable"
- severity must be exactly one of: "positive", "warning", "neutral"
- priority must be exactly one of: "high", "medium"
- Return ONLY the JSON object, nothing else"""


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
        "max_tokens": 3000,
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
        "data_summary": summary,
        "insights": insights,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"AI insights written to {OUTPUT_PATH}")
    return True


if __name__ == "__main__":
    success = generate_ai_insights()
    raise SystemExit(0 if success else 1)
