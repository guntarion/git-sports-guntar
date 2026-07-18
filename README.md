<p align="center">
  <img src="./site/icon.svg" alt="Garmin Git" width="96" /><br>
  <sub>
    (heatmap banner generator by
    <a href="https://github.com/aspain/heatmap-logo">aspain/heatmap-logo</a>)
  </sub>
</p>

<h1 align="center">Garmin Git</h1>
<p align="center"><b>Your Garmin training history as a GitHub-style dashboard</b><br>
<sub>heatmaps · running economy · recovery science · route maps</sub></p>

> **Fork of [aspain/git-sweaty](https://github.com/aspain/git-sweaty).**
> All core pipeline, heatmap rendering, and GitHub Actions infrastructure credit goes to the
> original author. This fork adds Garmin-focused analytics, AI coaching, sports-science metrics,
> and a PostgreSQL-backed app layer.

Turn your **Garmin Connect** activities into GitHub-style contribution graphs, running analytics,
and performance-science metrics — updated automatically every day.

**Live dashboard → [git-sports-guntar.vercel.app](https://git-sports-guntar.vercel.app)**

![Dashboard Preview](site/readme-preview-20260222a.png)

---

## Architecture at a glance

```
Garmin Connect
      │  daily, via GitHub Actions
      ▼
Python ETL  ──► dashboard-data branch (JSON)  ──► Vercel static site
      │
      └──────► PostgreSQL ──► Vercel serverless API ──► Journal · Todos · Performance
```

| Layer | Technology |
|---|---|
| ETL | Python 3.11+, no framework (`requests`, `garminconnect`, `psycopg2`) |
| Frontend | Vanilla JS + inline CSS, **no build step** |
| API | Node ESM serverless functions on Vercel |
| Storage | PostgreSQL (app data + metrics) · JSON on `dashboard-data` (heatmap data) |
| Automation | GitHub Actions (daily ETL) → Vercel (deploy) |

> **Note on hosting.** This fork moved off GitHub Pages. Static hosting has no server, so a page
> cannot safely reach a database — which the journal, todos, and performance features require.
> Vercel serves the same static site *plus* the API that talks to PostgreSQL.

---

## Features

### 📊 Dashboard, Activities, Analytics, Records

- **Dashboard** — GitHub-style heatmap across all activity types, with year/type filters
- **Activities** — per-activity detail: HR zone distribution, per-km split table, running dynamics
- **Analytics** — weekly volume, pace trends, aerobic efficiency, HR zone comparison, AI Coach
- **Records** — leaderboards by distance band, best 1 km splits, PR progression, form records

![Activities Page](docs/screenshot-activities.png)
![Analytics Page](docs/screenshot-analytics.png)
![Records Page](docs/screenshot-records.png)

### 📈 Performance — raw + derived metrics over time

A dedicated page separating **what Garmin measured** from **what is computed here**, with a
month-over-month verdict on every headline number.

![Performance Page](docs/screenshot-performance.png)

**Garmin measurements shown on the page:** VO₂max · Endurance Score · HRV · Hill Score · Pulse Ox ·
Recovery Time · Training Readiness · Acute & Chronic Load · ACWR · Training Status ·
Race Predictions

**Derived metrics** (see [`docs/performance-metrics.md`](docs/performance-metrics.md) for every
formula):

| Metric | Unit | Meaning |
|---|---|---|
| **Running Economy** | ml O₂/kg/km ↓ | Oxygen cost per km, on Garmin's own scale |
| **Efficiency Index** | m/beat ↑ | Distance per heartbeat (assumption-free) |
| **Cardiac Cost** | beats/km ↓ | Heartbeats to cover a kilometre |
| **Vertical Ratio** | % ↓ | Bounce as a proportion of stride |
| **Aerobic Decoupling** | % ↓ | Efficiency drift first half → second half |
| **Training Load** | TRIMP | Zone-weighted training minutes |
| **Recovery Balance** | index | HRV vs load — overreaching indicator |
| **Endurance : VO₂max** | ratio ↑ | Durability per unit of aerobic capacity |
| **Efficiency by HR zone** | m/beat ↑ | Efficiency within each intensity band |

Every card carries a **“How it's computed”** toggle with its definition and formula, so no number
is a black box.

#### Two design decisions worth knowing

**Running Economy is measured over a fixed km 2–4 window, not the whole run.** Measured
end-to-end, the number tracks how *far* you ran rather than how efficiently — longer runs
accumulate cardiac drift. On the reference dataset, `corr(distance, RE)` was **+0.53** whole-run
versus **+0.04** windowed, and runs ≥ 6 km scored 16.7 ml/kg/km worse than runs < 6 km, a bigger
gap than the entire baseline spread.

**Month-over-month comparisons use the same elapsed window.** On the 18th, "this month so far"
is compared against **day 1–18 of last month**, never against the full previous month. Equal-length
windows are fair for both averages and sums, so the comparison is valid from day 1 of a month.
Tiles with fewer than 3 readings say so instead of implying confidence they do not have.

### 🌙 Wellness — sleep, recovery and daily load

![Wellness Page](docs/screenshot-wellness.png)

Sleep stages stacked per night (deep / light / REM / awake) with the nightly score, Body Battery
as a charge-vs-drain diverging chart, resting heart rate, daily steps against the Garmin goal,
weekly stress, lactate threshold, and Garmin's personal records.

### 🗺️ Map — where every session happened

![Map Page](docs/screenshot-map.png)

Every GPS session drawn as a route on a dark basemap, coloured by sport, with a ranked places
sidebar, sport filters and click-to-fly navigation.

**This page is fully auth-gated with no public path.** The start coordinates of a run typically
disclose a home address, and the rest of this dashboard is public.

### 🤖 AI Coach (Coach RunAnalytica)

Powered by [Qwen](https://www.alibabacloud.com/en/product/modelstudio) (Alibaba DashScope, ACTOR
prompt framework): monthly performance review, goal tracker, categorised training insights,
3 actionable weekly recommendations, and a weekly focus theme. Reports are persisted to
PostgreSQL, and generation is skipped when no new running data has arrived.

![AI Coach Panel](docs/screenshot-ai.png)

### 📓 Journal & Todos — database-backed

Markdown journal and todo list, stored in **PostgreSQL** rather than browser localStorage, so they
persist across devices and browsers. Protected by an access token; the rest of the dashboard stays
publicly readable. Existing localStorage entries are migrated automatically on first unlock.

![Journal Page](docs/screenshot-journal.png)
![Todos Page](docs/screenshot-todos.png)

---

## Setup

### 1) Fork and configure the ETL

Fork this repository, then add repository **secrets**
(`Settings → Secrets and variables → Actions`):

| Secret | Required | Purpose |
|---|---|---|
| `GARMIN_TOKENS_B64` | one of these | Base64 OAuth token store (preferred) |
| `GARMIN_EMAIL` + `GARMIN_PASSWORD` | one of these | Fallback credentials |
| `DATABASE_URL` | for app features | PostgreSQL connection string |
| `VERCEL_TOKEN` | for auto-deploy | Create at <https://vercel.com/account/tokens> |
| `QWEN_API_KEY` | optional | Enables the AI Coach |

Repository **variables**: `DASHBOARD_SOURCE=garmin`, `DASHBOARD_REPO=<you>/<repo>`,
`DASHBOARD_DISTANCE_UNIT`, `DASHBOARD_ELEVATION_UNIT`, `DASHBOARD_WEEK_START`.

### 2) Local development

```bash
git clone https://github.com/<you>/<repo>.git && cd <repo>
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Interactive Garmin login — handles MFA, writes .garmin_token_store + config.local.yaml
.venv/bin/python scripts/garmin_login_local.py

# Verify auth without writing anything
.venv/bin/python scripts/sync_garmin.py --dry-run

# Serve locally (auto-uses .venv; pulls data from the dashboard-data branch)
bash scripts/dev_dashboard.sh --port 4180
```

Create a `.env` in the **repository root** (never inside `site/`, which is web-served):

```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

> Run Python scripts from the repository root — paths such as `site/activities.json` are relative.

### 3) Database

Tables are created automatically on first use. To apply the schema manually:

```bash
psql "$DATABASE_URL" -f sql/schema_app.sql
```

Optionally import existing AI history:

```bash
PYTHONPATH=scripts .venv/bin/python scripts/ai_insights_db.py --backfill
```

### 4) Deploy to Vercel

```bash
npm i -g vercel && vercel login
vercel link --yes

printf 'require'             | vercel env add PGSSL production          # if your PG supports TLS
printf '<your-db-url>'       | vercel env add DATABASE_URL production
printf '<choose-a-password>' | vercel env add APP_AUTH_TOKEN production # unlocks Journal/Todos

vercel deploy --prod --yes
```

Then **disable Deployment Protection** (`Project → Settings → Deployment Protection →
Vercel Authentication → Disabled`). New projects enable it by default, which 302-redirects every
request — including the API — behind a Vercel SSO login.

### 5) Trigger a sync

```bash
gh workflow run "Sync Heatmaps" --field source=garmin
```

---

## Setup notes & troubleshooting

**Garmin token refresh.** OAuth tokens expire. To refresh:

```bash
.venv/bin/python scripts/garmin_login_local.py
.venv/bin/python -c "import sys;sys.path.insert(0,'scripts');\
from garmin_token_store import encode_token_store_dir_as_zip_b64 as e;\
sys.stdout.write(e('.garmin_token_store'))" | gh secret set GARMIN_TOKENS_B64 -R <you>/<repo>
```

⚠️ Pipe to **stdin without `--body -`**. `gh secret set --body -` does *not* read stdin; it stores
the literal string `"-"`, which fails later with `binascii.Error: Only base64 data is allowed`.

**Vercel misdetects the project as Python.** The root `requirements.txt` triggers Vercel's Python
builder (`No python entrypoint found`). `vercel.json` pins `framework: null` and `.vercelignore`
excludes the Python files — keep both.

**Garmin rate limits.** Per-day endpoints (HRV, Pulse Ox, training readiness, resting HR, sleep)
cost one request per day of history. Backfills are resumable: they skip dates already stored and
back off on repeated failure. Control depth with `HRV_BACKFILL_DAYS` (workflow default: 7).
Some endpoints also reject long ranges — `get_body_battery` is chunked to 28 days.

**Garmin unit traps.** `recoveryTime` is reported in **minutes**, not hours (a 12 km run returned
1614 = 26.9 h). `get_max_metrics` returns empty on some accounts, so VO₂max history is
reconstructed from per-activity values instead.

**PostgreSQL over the internet.** Enabling `ssl = on` in `postgresql.conf` is *additive* and does
not break existing clients — most default to `sslmode=prefer` and silently upgrade. Only forcing
TLS via `hostssl` in `pg_hba.conf` breaks non-TLS clients. Set `PGSSL=require` on Vercel to
encrypt this app's connection.

**Personal constants.** `config.yaml → running_economy` holds `hr_max`, `hr_rest`, `vo2max_ref`
and `sex`. These shift every heart-rate-derived number. Set `hr_max` from your highest *recorded*
HR rather than a `220 − age` estimate. Keep `vo2max_ref` **frozen** — see the warning in
[`docs/performance-metrics.md`](docs/performance-metrics.md).

**Test baseline.** `cd scripts && ../.venv/bin/python -m pytest ../tests/ -v` reports
**9 failed, 254 passed**. All 9 are pre-existing and unrelated to these features: 4 source-switch
tests that failed before this work, 3 upstream fresh-machine bootstrap simulations, and 2 that
assert upstream README wording this fork deliberately replaced.

---

## Pages

| Page | URL | Auth |
|---|---|---|
| Dashboard | `/` | public |
| Activities | `/activities.html` | public |
| Analytics | `/analytics.html` | public |
| Records | `/records.html` | public |
| Performance | `/performance.html` | public (body weight requires token) |
| Wellness | `/wellness.html` | public |
| Map | `/map.html` | **token** |
| Journal | `/journal.html` | **token** |
| Todos | `/todos.html` | **token** |

## Configuration

Base settings: `config.yaml` · local overrides: `config.local.yaml` (gitignored)

| Setting | Default | Description |
|---|---|---|
| `source` | `garmin` | Data source |
| `sync.start_date` | — | Lower bound for history (`YYYY-MM-DD`) |
| `sync.recent_days` | `7` | Always re-sync the recent N days |
| `units.distance` | `km` | `km` or `mi` |
| `units.elevation` | `m` | `m` or `ft` |
| `heatmaps.week_start` | `sunday` | `sunday` or `monday` |
| `running_economy.hr_max` | — | Highest recorded HR (bpm) |
| `running_economy.hr_rest` | — | Resting HR (bpm) |
| `running_economy.vo2max_ref` | — | Frozen VO₂max reference |

## Documentation

- [`docs/performance-metrics.md`](docs/performance-metrics.md) — definitions and formulas for
  every metric on the Performance page, with filters and caveats
- [`CLAUDE.md`](CLAUDE.md) — architecture, commands, and gotchas for contributors

## Updating from upstream

```bash
git remote add upstream https://github.com/aspain/git-sweaty.git
git fetch upstream && git merge upstream/main
```

Expect conflicts in fork-specific files (`README.md`, `requirements.txt`, `site/*.html`,
`scripts/sync_garmin.py`). Activity data lives on `dashboard-data` and is never touched by
merging `main`.

## Credits

- **Original project**: [aspain/git-sweaty](https://github.com/aspain/git-sweaty)
- **Garmin API**: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
- **AI coaching**: [Qwen (DashScope)](https://www.alibabacloud.com/en/product/modelstudio)
- **Logo generator**: [aspain/heatmap-logo](https://github.com/aspain/heatmap-logo)
