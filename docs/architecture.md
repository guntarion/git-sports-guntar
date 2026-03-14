# Architecture Overview

## Data Pipeline

The system is an ETL pipeline orchestrated by `scripts/run_pipeline.py`:

```
Source API → Raw JSON → Normalize → Aggregate → Generate site JSON → Deploy
```

### Pipeline Stages (in order)

1. **Sync** (`sync_garmin.py` / `sync_strava.py`)
   - Fetches activities from provider API
   - Stores raw JSON in `activities/raw/{source}/` (gitignored)
   - Manages backfill state in `data/backfill_state_{source}.json`
   - Rate-limited with exponential backoff

2. **Enrich** (`enrich_garmin.py`) — Garmin only
   - Fetches per-activity detail: HR zones (Z1-Z5), km splits
   - Stores in `activities/enriched/garmin/{id}.json`
   - Tracks state to avoid re-fetching

3. **Normalize** (`normalize.py`)
   - Converts provider-specific formats to canonical schema
   - Type aliasing via `activity_types.py` (80+ sport types)
   - Output: `data/activities_normalized.json`

4. **Aggregate** (`aggregate.py`)
   - Groups by day/type for heatmap rendering
   - Output: `data/daily_aggregates.json`

5. **Generate Heatmaps** (`generate_heatmaps.py`)
   - Builds complete dashboard data with stats, type metadata
   - Output: `site/data.json` (consumed by index.html)

6. **Generate Activities** (`generate_activities.py`)
   - Combines normalized + enriched data per activity
   - Computes pace from speed, attaches splits & HR zones
   - Output: `site/activities.json` (consumed by activities.html, analytics.html, records.html)

7. **Generate AI Insights** (`generate_ai_insights.py`) — optional
   - Builds ACTOR-framed prompt from running data summary
   - Calls Qwen API (DashScope OpenAI-compatible endpoint)
   - Returns structured JSON: monthly review, goal tracker, insights, recommendations
   - Output: `site/ai_insights.json` (consumed by analytics.html AI Coach panel)

8. **Sync DB** (`sync_db.py`) — optional
   - Upserts to PostgreSQL: `activities`, `activity_splits`, `activity_hr_zones` tables

## State Management

| File | Purpose | Branch |
|------|---------|--------|
| `data/backfill_state_{source}.json` | Sync cursor position | dashboard-data |
| `data/source_state.json` | Last-used source (strava/garmin) | dashboard-data |
| `data/activities_normalized.json` | Canonical activity list | dashboard-data |
| `data/daily_aggregates.json` | Heatmap aggregates | dashboard-data |
| `activities/enriched/garmin/*.json` | Per-activity HR/splits | dashboard-data |

Source switching (strava → garmin or vice versa) triggers full state reset to prevent mixed data.

## Frontend Architecture

Each page is a standalone HTML file with inline CSS and JS — no build step required.

### Data Loading Pattern

All pages fetch JSON at load time:
```javascript
fetch('activities.json').then(r => r.json()).then(data => {
  S.raw = data.activities;  // Global state
  render();                 // Client-side rendering
});
```

### Page Data Dependencies

```
site/data.json ──────────→ index.html (heatmap dashboard)
site/activities.json ────→ activities.html (activity list + detail)
                     ────→ analytics.html (charts + monthly progress)
                     ────→ records.html (leaderboards + PRs)
site/ai_insights.json ──→ analytics.html (AI Coach panel)
```

## GitHub Actions Flow

```
sync.yml (daily 15:00 UTC or manual)
  ├── Checkout main
  ├── Setup Python 3.11
  ├── Write config.local.yaml from secrets
  ├── Restore state from dashboard-data branch
  ├── Run pipeline (all stages)
  ├── Publish state to dashboard-data branch
  └── Triggers pages.yml

pages.yml (after sync or push to main)
  ├── Checkout main
  ├── Restore site/*.json from dashboard-data branch
  ├── Stamp __APP_VERSION__ with git SHA
  └── Deploy site/ to GitHub Pages
```
