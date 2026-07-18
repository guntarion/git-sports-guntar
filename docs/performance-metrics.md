# Performance Metrics — Definitions & Formulas

Reference for everything shown on [`/performance.html`](https://git-sports-guntar.vercel.app/performance.html).

Metrics fall into two groups:

- **Garmin measurements** — reported by the watch, stored as-is. We do not recompute them.
- **Derived metrics** — computed here from your run data. Each one states its formula, its
  inputs, and the conditions a run must meet to be included.

Implementation lives in [`scripts/running_economy.py`](../scripts/running_economy.py) and
[`scripts/derived_metrics.py`](../scripts/derived_metrics.py). Values are stored in PostgreSQL
and served by [`api/performance.js`](../api/performance.js).

---

## Personal constants

These shift every heart-rate-based calculation, and live in `config.yaml` under `running_economy`:

| Constant | Value | Where it comes from |
|---|---|---|
| `hr_max` | **181 bpm** | Highest HR actually recorded across your runs (not a formula estimate) |
| `hr_rest` | **54 bpm** | Garmin wellness resting heart rate |
| `vo2max_ref` | **39.0** | Your Garmin VO₂max, **frozen deliberately** — see the warning below |
| `sex` | male | Selects Garmin's rating band table |

> ⚠️ **Why `vo2max_ref` is frozen.** It is tempting to feed each run's own `vo2_max` into the
> Running Economy formula. That would be wrong: Garmin *derives* VO₂max from the same
> heart-rate/pace relationship that Running Economy is trying to measure. Using it per-activity
> cancels the signal and flattens the series into a straight line. It must stay a constant.

If you get a proper lab or field HRmax test, update `hr_max` — every RE value will shift, but
the *shape* of the trend (which is what matters) stays the same.

---

# Part 1 — Garmin measurements

## VO₂ Max
**What it is.** Maximum rate of oxygen your body can use, ml/kg/min. A measure of aerobic
**capacity** — the size of the engine.
**Direction.** Higher is better.
**Source.** Two places: each run's `vo2_max` field, plus the current value from
`get_training_status()`. Garmin's dedicated `get_max_metrics()` endpoint returns empty for this
account, so the historical series is reconstructed from per-activity values (one point per day,
last run of the day wins).
**Note.** VO₂max is capacity, *not* efficiency. You can raise VO₂max while running economy stays
flat — they are different qualities. That is exactly what your data shows.

## Endurance Score
**What it is.** Garmin's composite of your ability to sustain prolonged effort, built from
training history and VO₂max.
**Direction.** Higher is better.
**Source.** `get_endurance_score(start, end)` — weekly group averages.

## HRV (last night avg)
**What it is.** Overnight heart-rate variability in milliseconds; the average of the beat-to-beat
variation measured while you sleep. A proxy for autonomic recovery state.
**Direction.** Higher generally indicates better recovery, but **read it against your own
baseline**, not against other people.
**Source.** `get_hrv_data(date)` → `hrvSummary.lastNightAvg`. One request per day, so history is
backfilled gradually (currently from 2026-01-09, when the watch started recording).

## Hill Score
**What it is.** Garmin's rating of hill-running ability, combining a strength component and an
endurance component.
**Direction.** Higher is better.
**Source.** `get_hill_score(start, end)` → daily `overallScore` (with `strengthScore` and
`enduranceScore` kept in the record).

## Race Predictions
**What it is.** Garmin's estimated finish times for 5K / 10K / half / marathon, from your current
fitness.
**Source.** `get_race_predictions()`.
**Note.** These assume race-day conditions and appropriate pacing; treat them as a fitness
indicator rather than a promise.

---

# Part 2 — Derived metrics

## Running Economy (RE)

**What it is.** The oxygen cost of covering a kilometre — how much fuel your engine burns per km.
Garmin's own metric requires an **HRM 600** strap (it measures *step speed loss*), which we do not
have. But Garmin's unit is the standard physiological scale, and it decomposes cleanly, so we
reproduce the scale by *estimating* oxygen uptake instead of measuring it.

**Unit.** ml O₂ / kg / km. **LOWER is better.**

**Formula.**

```
hrr  = (hr_window − hr_rest) / (hr_max − hr_rest)      # fraction of heart-rate reserve
VO2  = 3.5 + hrr × (vo2max_ref − 3.5)                  # ml/kg/min, via %HRR ≈ %VO2R
v    = distance_window / (duration_window / 60)        # m/min
RE   = VO2 × 1000 / v                                  # ml/kg/km
```

The `%HRR ≈ %VO2R` step is the standard ACSM linear bridge between heart rate and oxygen uptake —
the same mechanism behind Polar's Running Index. `3.5` is resting metabolic rate (1 MET).

**The fixed km 2–4 window — the most important design decision.**

Every run is measured over splits **2, 3 and 4 only** — never the whole run.

Measured end-to-end, the number tracks how *far* you ran rather than how efficiently. Verified on
your own history:

| Measurement | corr(distance, RE) |
|---|---|
| Whole run | **+0.527** ❌ |
| Fixed km 2–4 window | **+0.04** ✅ |

Runs ≥6 km scored **16.7 ml/kg/km worse** than runs <6 km — a bigger gap than the entire baseline
spread. That is **cardiac drift** (heart rate climbs at constant pace as a run goes on), not a real
change in efficiency. Because your runs grew from 4 km to 14 km over the season, an
end-to-end measurement showed a *false decline* exactly while your VO₂max was rising 36 → 39.

Skipping split 1 removes warm-up and heart-rate lag; stopping at split 4 stops drift accumulating.
Every run then contributes a comparable 3 km measurement regardless of total length.

**A run must satisfy all of these to be scored:**

| Condition | Threshold | Why |
|---|---|---|
| Activity type | running | — |
| Not treadmill / indoor / virtual | — | Treadmill pace is accelerometer-derived, not GPS. Your treadmill runs show 92 cm stride @ 138 spm vs 70 cm @ 153 spm outdoors — not comparable. Garmin excludes them too. |
| Not trail | — | Terrain dominates the signal |
| True kilometre splits | 800–1200 m each | Garmin sometimes emits merged laps (one 2996 m "split") that would silently stretch the window |
| Splits available | ≥ 4 | Need splits 2–4 plus the skipped first |
| Window HR | 65–85% of `hr_max` | Easy/steady band only |
| Split pace variation | CV ≤ 6% | Excludes intervals and fartlek |
| Average pace | ≤ 900 s/km | Existing project rule for anomalous data |

**Garmin rating bands** (ml/kg/km, male):

| Rating | Range |
|---|---|
| Elite | < 185 |
| Superior | 185–189 |
| Expert | 190–194 |
| Well Trained | 195–204 |
| Trained | 205–214 |
| Intermediate | 215–224 |
| Recreational | > 224 |

**The 0–100 score.** The absolute RE value carries an unknown offset (because `vo2max_ref` is an
estimate), so the score is normalised against **your own** history using a robust baseline that
outliers cannot distort:

```
median = median(all qualifying RE values)
sigma  = 1.4826 × median(|RE − median|)      # MAD; floored at 3.0
score  = 50 + 15 × (median − RE) / sigma     # clamped to 0–100
```

50 = your personal baseline. Each 15 points ≈ 1 robust standard deviation. Lower RE → higher
score. No score is shown until there are at least **8** qualifying runs.

**Read the rolling median, not single runs.** Heat, sleep, fatigue and HR artefacts move a single
run by about as much as a whole season of real adaptation. The dashed line is a 5-run rolling
median.

---

## Efficiency Index (EI)

**What it is.** How far you travel per heartbeat. Assumption-free — no HRmax, HRrest or VO₂max
estimate is involved, so it cannot be distorted by a wrong constant.

**Unit.** metres per beat (m/min per bpm). **Higher is better.**

```
EI = speed (m/min) / average heart rate (bpm)
```

Computed over the same km 2–4 window. This is TrainingPeaks' "Efficiency Factor" applied to running.

**Caveat.** EI rises with speed, so only compare within a similar pace range — which the easy/steady
HR filter already enforces.

## Cardiac Cost

**What it is.** How many heartbeats it costs you to cover a kilometre. The inverse view of EI, in
units that are easy to feel.

**Unit.** beats per km. **Lower is better.**

```
cardiac_cost = average heart rate × pace (s/km) / 60
```

Mathematically `cardiac_cost = 1000 / EI`; both are shown because each is intuitive in a different
way. Also assumption-free.

## Vertical Ratio

**What it is.** How much of your motion goes *up* instead of *forward* — bounce as a proportion of
stride. Garmin's single best running-form indicator.

**Unit.** percent. **Lower is better.**

```
vertical_ratio = vertical oscillation (cm) / stride length (m)
```

(The units cancel to a percentage: cm ÷ m = cm ÷ 100 cm × 100%.)

**Caveat.** Form metrics correlate with economy only weakly and noisily in the literature, so this
is reported **separately** and is never folded into the Running Economy number.

---

# Part 3 — Endurance & recovery

## Aerobic Decoupling

**What it is.** How much your efficiency drifts from the first half of a run to the second — the
classic durability test. If heart rate climbs (or pace falls) as a run goes on, your aerobic system
is not comfortably supporting that effort.

**Unit.** percent. **Lower is better. Under 5% is considered aerobically sound.**

```
body   = splits 2..n                                  # split 1 dropped (warm-up, HR lag)
half   = the split where cumulative time passes 50%
EF₁    = speed_first_half  / HR_first_half            # time-weighted HR
EF₂    = speed_second_half / HR_second_half
decoupling = (EF₁ − EF₂) / EF₁ × 100
```

**Measured over the WHOLE run — deliberately the opposite of Running Economy.** For RE, cardiac
drift is a confound to be engineered out. Here the drift *is* the signal.

**Conditions.** Running, not treadmill/indoor/trail, ≥ 4 usable kilometre splits, and average HR in
the 65–85% band.

**Reading it.** Negative means you got *more* efficient in the second half (negative split, or a
long warm-up). Large positive values on long runs are normal early in a training block and should
shrink as endurance improves.

## Training Load (TRIMP)

**What it is.** Zone-weighted training minutes — a measure of physiological cost that counts hard
minutes as more expensive than easy ones.

**Unit.** weighted minutes, summed per ISO week. Neither high nor low is "better" on its own — it
is the input to recovery balance.

```
TRIMP = Σ over zones ( minutes_in_zone × weight[zone] )
weight = { Z1: 1, Z2: 2, Z3: 3, Z4: 4, Z5: 5 }
```

Uses the per-activity HR-zone table from Garmin. Includes **all** activities, not only runs —
total stress on the body is what governs recovery.

## Recovery Balance

**What it is.** Whether your recovery is keeping up with the training load you are carrying — an
overreaching indicator.

**Unit.** index (z-score difference). **Positive = recovered. Persistently negative = load
outpacing recovery.**

```
per ISO week:
  hrv_week   = mean overnight HRV that week
  load_week  = summed TRIMP that week
recovery_balance = z(hrv_week) − z(load_week)
```

where `z(x) = (x − mean) / stdev` across all weeks in range.

**Why it is one series and not two lines.** You asked for "HRV vs training load". Plotting them as
two lines on one chart would be wrong: HRV sits around 50–70 ms and load around 300–650 TRIMP, so
they need different scales — and a dual-axis chart is the single most common charting mistake, since
the apparent crossings are an artefact of arbitrary scaling. Combining them into one z-score
difference gives a directly readable answer. The raw HRV and load values are still available in the
tooltip and the "Show data" table.

**Validation.** In your heaviest week (2026-06-29, load 644.6) the index drops to **−2.15** — the
classic pattern of load rising while HRV falls.

## Endurance : VO₂max

**What it is.** Endurance score per unit of aerobic capacity. Two runners with identical VO₂max can
differ a lot here; it isolates *durability* from raw engine size.

**Unit.** ratio. **Higher is better.**

```
ratio = endurance_score / vo2max
```

Each endurance reading is matched to the most recent VO₂max at or before that date.

**Reading it.** Rising means endurance is improving faster than capacity — typical of a base-building
block. Falling while VO₂max climbs is not necessarily bad; it can mean sharper, shorter training.

## Efficiency by HR zone

**What it is.** Metres per heartbeat *within each heart-rate zone*, so improvement at easy intensity
is not hidden by how hard your runs happened to be in a given period.

**Unit.** metres per beat. **Higher is better.**

Each kilometre split is bucketed into a zone using **that activity's own** zone boundaries (from
Garmin's `hr_zones`, so a change to your zone setup does not silently shift the buckets), then the
median EI per zone is taken.

**Reading it.** EI normally falls as intensity rises — at higher heart rates, HR climbs faster than
speed does. What matters is the trend *within* a zone over time. Zones with few splits are
statistically weak; the split count is shown next to each bar.

---

# Caveats that apply to everything HR-based

Anything derived from heart rate is confounded by, roughly in order of impact:

1. **Heat and humidity** — the largest factor. Cardiac drift of 10–20 bpm over 30–60 min, amplified
   in heat.
2. **Dehydration**, **altitude**, **illness**, **poor sleep**, **caffeine**, **accumulated fatigue**
   — all raise HR at a given pace, which makes efficiency metrics look worse.
3. **Optical HR artefacts** — wrist sensors can drop out or lock onto cadence.
4. **Hills, wind, surface** — filtered where possible, never perfectly.

This is why the filters are strict, why single runs are never trusted, and why rolling medians are
shown. A metric that moves 5% between two runs has probably told you about the weather, not your
fitness.

---

# Data pipeline

```
Garmin Connect
  → scripts/sync_garmin.py           (activities + running dynamics)
  → scripts/enrich_garmin.py         (HR zones + per-km splits)
  → scripts/generate_activities.py   (site/activities.json)
  → scripts/running_economy.py       (RE, EI, cardiac cost, vertical ratio)
  → scripts/derived_metrics.py       (decoupling, TRIMP, zone efficiency, ratios)
  → scripts/sync_performance_db.py   (PostgreSQL: running_economy, activity_derived,
                                      performance_metrics)
  → api/performance.js               (serves the page)
```

Runs daily via the **Sync Heatmaps** GitHub Actions workflow. Every metric stage is non-fatal: a
failure there never breaks the activity pipeline.

**Privacy.** Performance metrics are publicly readable, matching the rest of the dashboard. **Body
weight is the exception** — it is only returned to an authenticated caller. Journal and todos are
fully auth-gated.
