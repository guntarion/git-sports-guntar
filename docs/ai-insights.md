# AI Insights System

## Overview

The AI coaching system generates personalized running insights using the Qwen API (Alibaba Cloud DashScope). It runs as part of the daily sync pipeline and produces `site/ai_insights.json`.

## Architecture

```
activities.json → _build_data_summary() → _build_prompt() → Qwen API → ai_insights.json
                                            (ACTOR framework)
```

## Configuration

| Env Variable | Default | Purpose |
|-------------|---------|---------|
| `QWEN_API_KEY` | (required) | DashScope API key |
| `QWEN_ENDPOINT` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions` | API endpoint |

**Model**: `qwen-plus` (reasoning-capable)
**Temperature**: 0.7
**Max tokens**: 3000

## ACTOR Prompt Framework

The prompt follows the ACTOR structure:

- **A**gent: "Coach RunAnalytica" — elite running coach persona
- **C**ontext: Recreational runner using Garmin watch, data-driven
- **T**ask: Analyze 5 sections (monthly review, goals, insights, recommendations, focus)
- **O**utput: Strict JSON schema with typed fields
- **R**ules: Metric units, runner's own history (not population benchmarks), severity/verdict enums

## Data Summary (input to prompt)

Built from `activities.json`, filtered to running activities > 500m:

```json
{
  "total_runs": 42,
  "total_km": 185.3,
  "date_range": "2025-08-01 to 2026-03-14",
  "this_month": { "runs": 3, "total_km": 14.7, "avg_pace_secs": 540, ... },
  "last_month": { "runs": 16, "total_km": 51.8, ... },
  "days_left_this_month": 17,
  "recent_runs": [ /* last 5 runs with full metrics */ ]
}
```

## Output Schema (`ai_insights.json`)

```json
{
  "generated_at": "2026-03-14T03:55:03Z",
  "model": "qwen-plus",
  "data_summary": { /* input data */ },
  "insights": {
    "monthly_review": {
      "summary": "text",
      "metrics": [{ "name": "...", "current": "...", "previous": "...", "change": "...", "verdict": "improved|declined|stable" }],
      "highlight": "text"
    },
    "goal_tracker": {
      "km_this_month": 14.7,
      "km_last_month": 51.8,
      "km_remaining": 37.1,
      "projection": "Behind",
      "message": "text"
    },
    "insights": [{ "category": "aerobic_efficiency|hr_zones|running_form|training_load|recovery", "title": "...", "body": "...", "severity": "positive|warning|neutral" }],
    "recommendations": [{ "action": "...", "reason": "...", "priority": "high|medium" }],
    "weekly_focus": { "theme": "...", "description": "...", "suggested_sessions": ["..."] }
  }
}
```

## Frontend Rendering

The AI Coach panel in `analytics.html` renders above all charts:
- Loads `ai_insights.json` via fetch (graceful null if missing)
- `renderAI()` function builds the panel HTML
- Color-coded: purple gradient border, green/orange/muted severity colors
- Progress bar for goal tracker
- Numbered recommendation cards

## Error Handling

- Non-fatal: pipeline succeeds even if Qwen API fails
- 401 errors: usually wrong endpoint (intl vs china) or expired key
- JSON parse errors: strips markdown code fences before parsing
- Missing data: panel simply doesn't render (no error shown to user)

## Triggering

- **Automatic**: Every sync pipeline run (if `QWEN_API_KEY` is set)
- **Manual**: `gh workflow run "Sync Heatmaps" --field source=garmin`
- Cannot be triggered independently (integrated in pipeline)
