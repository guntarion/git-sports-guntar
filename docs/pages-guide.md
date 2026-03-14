# Frontend Pages Guide

## Navigation Structure

All pages cross-link via header nav:
```
Dashboard (index.html) ↔ Activities ↔ Analytics ↔ Records
```

---

## 1. Dashboard — `site/index.html` + `site/app.js`

**Data**: `site/data.json`
**URL**: `/` or `/index.html`

GitHub-style contribution heatmap showing all activities.

**Features:**
- Heatmap grid (year rows × week columns × day cells)
- Multi-type days shown as proportional split squares
- Type filter (sidebar/dropdown)
- Year selector
- Unit switcher (km/mi, m/ft)
- Responsive: desktop grid → mobile horizontal scroll
- Touch-optimized tooltips (tap-to-pin, swipe dismiss)

**Key constants in app.js:**
- 80+ activity type colors
- Cell size, padding, layout configuration
- Touch gesture thresholds

---

## 2. Activities — `site/activities.html`

**Data**: `site/activities.json`
**URL**: `/activities.html`

Detailed per-activity list with expandable cards.

**Features:**
- Sortable activity list (most recent first)
- Type badge with color coding
- Per-activity stats: distance, duration, pace, HR, elevation
- Expandable detail panel per activity:
  - HR Zone distribution bars (Z1-Z5)
  - Split/lap table (per km): distance, pace, HR, elevation
  - Extended stats: cadence, stride, ground contact, VO2 max
- Type and year filters

**Data fields used per activity:**
- Core: `id`, `date`, `type`, `distance`, `moving_time`, `elevation_gain`
- Pace: `avg_pace_secs_per_km` (computed from `avg_speed_mps`)
- HR: `avg_hr`, `max_hr`
- Garmin enriched: `splits[]`, `hr_zones[]`
- Running dynamics: `avg_cadence`, `avg_stride_len`, `avg_ground_contact`, `avg_vertical_osc`
- Training: `aerobic_te`, `anaerobic_te`, `vo2_max`

---

## 3. Analytics — `site/analytics.html`

**Data**: `site/activities.json` + `site/ai_insights.json`
**URL**: `/analytics.html`

Comprehensive running analytics dashboard.

**Sections (top to bottom):**

1. **AI Coach Panel** (from `ai_insights.json`)
   - Coach RunAnalytica persona
   - Monthly review summary + highlight
   - Monthly comparison metrics (improved/declined/stable)
   - Goal tracker with progress bar
   - Training insights (positive/warning/neutral)
   - 3 actionable recommendations (high/medium priority)
   - Weekly focus theme + suggested sessions

2. **Monthly Progress Dashboard**
   - Distance progress vs last month (with progress bar)
   - Sessions count comparison
   - Avg pace comparison with delta
   - Avg HR comparison with delta
   - Aerobic efficiency comparison

3. **Weekly Running Volume** (bar chart + 4-week rolling average line)

4. **Pace Trend** (line chart, distance-colored points by band)
   - Bands: <3km (purple), 3-6km (cyan), 6-12km (teal), >12km (orange)

5. **Avg HR Trend** (line chart)

6. **Aerobic Efficiency** (higher = better, line chart)
   - Formula: `(1000 / pace_secs) / avg_hr * 1000`

7. **Cadence Trend** (line chart, target 170-180 spm)

8. **Weekly Training Load** (bar chart, sum of aerobic TE per week)

9. **HR Zone Distribution** (this month vs last month, horizontal bars)

10. **Running Form Trends** (ground contact, stride length)

11. **Monthly Summary Table** (runs, distance, time, pace, HR, efficiency, TE)

**Filters:**
- Type: Running / All
- Year: All / specific year

**Data filtering (applied in JS):**
- `distance > 500` (exclude short activities)
- `avg_pace_secs_per_km < 900` (exclude anomalous pace)

---

## 4. Records — `site/records.html`

**Data**: `site/activities.json`
**URL**: `/records.html`

Running records leaderboard with personal bests.

**Sections:**

1. **Hero Card** — Latest/selected run's rank within its distance band
   - Rank, tier badge (PR / Top 5 / Top 10 / etc.)
   - Gap to PR (pace difference)
   - Zone 2 rank (HR < 135 bpm)
   - Full stats grid

2. **Band Leaderboards** (tabs):
   - `< 3 km` — short runs
   - `3–6 km` — mid runs
   - `6–12 km` — long runs
   - `> 12 km` — ultra
   - `Best 1km Splits` — fastest individual km splits

3. **Monthly Champions** — Best pace, longest, best TE, Z2 best per month

4. **Monthly PR Progression** — Table showing best pace per band per month

5. **Running Form Records** — Best cadence, stride, ground contact, vert osc, VO2 max, TE

6. **Split Analysis**:
   - Best negative splits (2nd half faster than 1st)
   - Most consistent pacing (lowest pace variation)

**Filters:**
- Period: All Time / This Month / Last 3 Months
- Zone 2 toggle (HR < 135 bpm only)
- Year selector

**Data filtering:**
- Activities: `distance > 500`, `avg_pace_secs_per_km < 900`
- Splits: `distance >= 500` (exclude partial km at end of run)

---

## Shared Patterns

### Tooltip Configuration (all charts)
```javascript
plugins: { tooltip: { mode: 'index', intersect: false } }
```

### Distance Bands (analytics + records)
```javascript
var BANDS = [
  { key: 'short', label: '< 3 km', min: 0, max: 3000, color: '#a78bfa' },
  { key: 'mid', label: '3–6 km', min: 3000, max: 6000, color: '#00bbf9' },
  { key: 'long', label: '6–12 km', min: 6000, max: 12000, color: '#00f5d4' },
  { key: 'ultra', label: '> 12 km', min: 12000, max: 1e9, color: '#f97316' },
];
```

### Running Type Detection
```javascript
var RUNNING = ['Run', 'TrailRun', 'VirtualRun', 'run', 'trail_run', 'virtual_run'];
function isRun(a) { return RUNNING.some(t => (a.type||'').toLowerCase() === t.toLowerCase()); }
```
