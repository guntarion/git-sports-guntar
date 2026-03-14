# Analytics v2 — Plan

## Philosophy: Analytics vs Records
- **Records** = "What are my bests?" — leaderboards, PRs, ranking
- **Analytics** = "How am I trending?" — insights, predictions, actionable guidance, AI coaching

Analytics should be the **brain** — it interprets data, spots patterns, tells you what's improving/declining, and gives you actionable next steps.

---

## Architecture

### Data Flow
```
activities.json (client-side)
       │
       ▼
analytics.html (JS computes all metrics)
       │
       ▼
AI Insight Panel → calls Qwen API via proxy endpoint
```

### AI Integration: Server-side Proxy
Since QWEN_API_KEY is a secret, we need a server-side proxy. Options:
1. **GitHub Actions → generate AI insights at sync time → write to `site/ai_insights.json`**
   - Pro: No API key exposure, works with static site
   - Con: Only updates when sync runs (daily)
2. **Client-side call to a proxy** (needs external server)
   - Not practical for GitHub Pages

**Chosen: Option 1** — Generate AI insights during the sync pipeline.
A new script `scripts/generate_ai_insights.py` runs after `generate_activities.py`,
calls Qwen API with the ACTOR-framed prompt, writes `site/ai_insights.json`.
The analytics page loads this JSON and renders the AI section.

---

## ACTOR Framework Prompt Design

### Agent (Role)
```
You are Coach RunAnalytica — an elite running coach and sports scientist
with 15 years of experience coaching recreational runners to optimize
their training. You specialize in heart rate-based training, periodization,
and data-driven performance analysis using Garmin metrics.
```

### Context
```
You are analyzing running data for a recreational runner.
Data includes: per-activity stats (pace, HR, cadence, stride, TE, VO2 max,
ground contact, vertical oscillation), per-km splits with HR,
HR zone distributions, and weekly/monthly aggregates.
The runner uses a Garmin watch and trains primarily for health and improvement.
```

### Task
```
Analyze the provided running data and produce:
1. MONTHLY PERFORMANCE REVIEW
   - Compare this month vs last month across all key metrics
   - Highlight what improved and what declined (with exact numbers)
   - Identify the most significant change

2. GOAL TRACKER
   - To match/exceed last month: how many more km, how many more sessions
   - Projected month-end totals based on current trajectory

3. TRAINING INSIGHTS
   - Aerobic efficiency trend analysis (speed/HR ratio)
   - HR zone balance assessment (too much Z4/Z5? not enough Z2?)
   - Cadence & running form observations
   - Recovery pattern analysis (rest days between hard sessions)

4. ACTIONABLE RECOMMENDATIONS
   - Top 3 specific, actionable things to do this week
   - What to avoid based on the data

5. WEEKLY FOCUS
   - Suggested focus for the coming week based on recent patterns
```

### Outputs
```
Return a JSON object with these keys:
{
  "monthly_review": {
    "summary": "1-2 sentence overall assessment",
    "metrics": [
      { "name": "...", "current": "...", "previous": "...",
        "change": "+/-...", "verdict": "improved|declined|stable" }
    ],
    "highlight": "The single most notable finding"
  },
  "goal_tracker": {
    "km_this_month": X,
    "km_last_month": Y,
    "km_remaining": Z,
    "sessions_this_month": N,
    "sessions_last_month": M,
    "sessions_remaining": K,
    "projection": "On track / Behind / Ahead",
    "message": "Narrative projection"
  },
  "insights": [
    { "category": "...", "title": "...", "body": "...",
      "severity": "positive|warning|neutral" }
  ],
  "recommendations": [
    { "action": "...", "reason": "...", "priority": "high|medium" }
  ],
  "weekly_focus": {
    "theme": "...",
    "description": "...",
    "suggested_sessions": [ "..." ]
  }
}
```

### Rules
```
- Use metric units (km, min/km)
- Be specific with numbers, never vague
- Compare against the runner's OWN history, not generic benchmarks
- Keep recommendations practical for a recreational runner
- Max 3 recommendations, prioritized
- If data is insufficient for a section, say so honestly
- Tone: encouraging but data-driven, like a supportive coach
- Language: English (the data visualization is in English)
```

---

## Analytics Page Sections (Redesigned)

### 1. AI Coach Panel (NEW)
- Rendered from `ai_insights.json`
- Styled as a distinctive "coach" card with gradient border
- Monthly review with color-coded metrics (green=improved, red=declined)
- Goal tracker with progress bars
- Recommendations as actionable cards
- Refresh note: "Last updated: [timestamp]"

### 2. Monthly Progress Dashboard (REVAMPED)
- Current month vs last month comparison cards
- Each metric shows: current value, last month value, delta, arrow
- Progress bars showing "% of last month's target reached"
- "To match last month, you need X more km in Y remaining days"

### 3. Trend Charts (KEPT, IMPROVED)
- Pace Trend: colored by distance band (keep from v1)
- HR Trend: with moving average overlay
- Weekly Volume: with month labels + rolling avg (keep from v1)
- Aerobic Efficiency: (keep from v1)
- NEW: Cadence Trend (if data available)
- NEW: Training Load (weekly sum of aerobic TE)

### 4. Training Balance (NEW)
- HR zone pie/donut chart: % time in each zone
- "Balance Score" — are you spending enough time in Z2?
- Comparison: this month zone distribution vs last month

### 5. Running Form Trends (NEW)
- Cadence over time (line chart)
- Ground contact time over time
- Vertical oscillation over time
- Stride length over time
- Each with moving average and interpretation labels

### 6. Recovery Analysis (NEW)
- Calendar heatmap: days with/without running
- Average rest days between sessions
- Sessions per week trend
- "You averaged X days between runs this month vs Y last month"

### 7. Monthly Summary Table (IMPROVED)
- Add delta arrows (↑↓) comparing to previous month
- Color coding: green for improved, red for declined
- Add "km remaining to match" column for current month

---

## Implementation Checklist

### Phase 1: AI Integration Pipeline
- [x] Store QWEN_API_KEY as GitHub secret
- [ ] Create `scripts/generate_ai_insights.py`
  - [ ] Build ACTOR prompt with real data
  - [ ] Call Qwen API (dashscope compatible endpoint)
  - [ ] Parse JSON response
  - [ ] Write `site/ai_insights.json`
- [ ] Add to `scripts/run_pipeline.py` (after generate_activities)
- [ ] Update `sync.yml` to pass QWEN_API_KEY env
- [ ] Update `pages.yml` to restore ai_insights.json from dashboard-data branch
- [ ] Update sync.yml publish step to copy ai_insights.json

### Phase 2: Analytics Page Overhaul
- [ ] Rewrite analytics.html
  - [ ] AI Coach Panel (loads ai_insights.json)
  - [ ] Monthly Progress Dashboard with comparison cards
  - [ ] Trend Charts (pace, HR, efficiency, cadence, training load)
  - [ ] Training Balance (zone distribution comparison)
  - [ ] Running Form Trends
  - [ ] Recovery Analysis
  - [ ] Improved Monthly Summary Table with deltas
- [ ] Remove sections that overlap with records.html
  - Remove: Personal Records section (moved to records.html)
  - Remove: Best Runs Leaderboard (moved to records.html)
  - Keep but differentiate: Summary stats (add comparison context)

### Phase 3: Navigation & Polish
- [ ] Update all page navigation links
- [ ] Test with real data
- [ ] Trigger full sync to generate AI insights
