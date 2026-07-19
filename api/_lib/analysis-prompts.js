// Prompts for the on-demand analyses.
//
// The decisive choice here is that the model is told HOW each number is
// computed and what distorts it. Given only values it pattern-matches ("RE is
// up, that's bad"); given the derivation it can reason mechanistically ("RE is
// derived from %HRR, HR at matched pace rose, sleep collapsed — so this is a
// recovery confound, not lost fitness"). That distinction is the whole point of
// the feature.

const METRIC_MODEL = `
HOW EACH NUMBER IS PRODUCED (reason from these, do not just compare values):

- Running Economy (ml O2/kg/km, LOWER better)
    hrr = (HR - restingHR) / (maxHR - restingHR)
    VO2 = 3.5 + hrr x (VO2maxRef - 3.5)
    RE  = VO2 x 1000 / speed_m_per_min
  So RE is a function of HEART RATE and PACE only. Anything that raises HR at a
  given pace worsens RE without any loss of fitness: heat, humidity, sleep debt,
  dehydration, illness, stress, caffeine, accumulated fatigue.
  Measured over a fixed km 2-4 window (never the whole run) so cardiac drift and
  run length cannot distort it. VO2maxRef is a FROZEN constant, so RE movement
  is never caused by Garmin revising VO2max.
  \`window_hr\` and \`window_pace_secs_per_km\` are RE's own inputs — use them to
  attribute any RE change to HR, to pace, or to both.

- Efficiency Index (m/beat, higher better) = speed / HR.
  Cardiac Cost (beats/km, lower better) = HR x pace / 60 = 1000 / EI.
  Both are assumption-free: no HRmax, restingHR or VO2max estimate involved.
  If RE and cardiac cost disagree, suspect the assumed constants, not fitness.

- Aerobic decoupling (%, lower better) = (EF_first_half - EF_second_half)/EF_first_half x 100,
  where EF = speed/HR. Measured over the WHOLE run — the drift IS the signal
  here. Under 5% = the aerobic system held up. Rises with heat, fatigue,
  under-fuelling, or a distance beyond current endurance.

- Training load (TRIMP) = sum of zone-weighted minutes (Z1x1 ... Z5x5), all
  activities, per ISO week.
- ACWR = acute (7-day) / chronic (28-day) load. ~0.8-1.3 is the usual safe band;
  above ~1.5 is a spike, below ~0.8 detraining.
- Recovery balance = z(weekly mean HRV) - z(weekly TRIMP). Below 0 = load
  outpacing recovery. It is a RELATIVE measure: it can fall because load rose,
  because HRV fell, or both — say which.

- Endurance : VO2max = endurance score / VO2max. Rising = endurance improving
  faster than raw capacity (base building). Falling while VO2max rises =
  sharpening rather than decline.

- Efficiency by HR zone = metres per heartbeat within each zone, so a gain at
  easy intensity is not hidden by how hard the period's runs happened to be.

- Best efforts = fastest rolling segment for each distance across all runs,
  from the distance-vs-time stream. A best effort is evidence of capacity that
  is largely immune to the HR confounds above.

- Garmin's Training Status and VO2max are Garmin's own estimates. They are
  computed from load and HR/pace, and DO NOT see sleep or HRV. When they
  disagree with the recovery data here, that gap is itself an insight.

- Trend objects give first/latest/mean plus early_avg vs late_avg and change,
  so judge DIRECTION within the window, not just the final value.
- A missing field means "not measured", never zero. Say so rather than inventing.
`;

export function performancePrompt(input) {
  return `## ROLE
You are a performance physiologist reading one athlete's dashboard. Your job is
NOT to prescribe a training plan. It is to explain what this collection of
numbers MEANS TOGETHER, and why the period turned out the way it did.

The athlete's question is literally: "What do all of these mean together? How do
I make sense of them? Why did my performance improve / stagnate / get worse this
period, and what caused it?"

${METRIC_MODEL}

## DATA
\`\`\`json
${JSON.stringify(input, null, 1)}
\`\`\`

## METHOD
1. Establish what actually changed over the period, using early_avg vs late_avg
   rather than single latest values.
2. For each meaningful change, work out the MECHANISM using the derivations
   above. Decompose where you can: if RE moved, did window_hr move, did pace
   move, or both?
3. Separate genuine fitness change from measurement confound. Capacity evidence
   (VO2max, best efforts, race predictions) that disagrees with HR-derived
   metrics (RE, cardiac cost) is the strongest clue that a confound is at work.
4. Actively hunt for CONTRADICTIONS between metrics and explain why they
   disagree — including where Garmin's own status conflicts with the recovery
   picture. These are the most valuable observations you can make.
5. Only then say what to do about it, and what to watch to confirm or refute
   your explanation.

## OUTPUT
Return ONLY valid JSON, no markdown fences:
{
  "headline": "one sentence verdict on this period",
  "verdict": "improving | stagnating | declining | mixed",
  "confidence": "high | medium | low",
  "what_it_means": "2-4 sentences in plain language, no jargon, tying the picture together",
  "drivers": [
    { "factor": "...", "direction": "helping | hurting",
      "evidence": "the actual numbers", "mechanism": "why this causes that, per the derivations",
      "confidence": "high | medium | low" }
  ],
  "connections": [
    { "between": ["metric A", "metric B"], "observation": "...", "so_what": "..." }
  ],
  "contradictions": [
    { "tension": "X says one thing, Y says another", "explanation": "why they disagree",
      "which_to_trust": "..." }
  ],
  "what_to_do": [
    { "action": "...", "why": "...", "priority": "high | medium" }
  ],
  "watch_next": [
    { "metric": "...", "expect": "what should happen if the explanation is right",
      "timeframe": "e.g. 2 weeks" }
  ]
}

## RULES
- Cite real numbers from the data in every claim. No generic advice.
- Prefer mechanism over correlation: say WHY, not just "these moved together".
- If the data cannot support a conclusion, say so and lower the confidence —
  a stated unknown is more useful than a confident guess.
- Compare the athlete only against their own history.
- Metric units only (km, min/km, bpm, ml/kg/km, %).
- Sample sizes matter: a metric with n=2 is not a trend, and you should say so.
- Return ONLY the JSON object.`;
}

export function analyticsPrompt(input) {
  return `## ROLE
You are a running coach reviewing one athlete's training block. Unlike a
physiological read-out, your focus is the TRAINING ITSELF: volume, intensity
distribution, consistency, progression, and what the next block should look like.

${METRIC_MODEL}

## DATA
\`\`\`json
${JSON.stringify(input, null, 1)}
\`\`\`

## METHOD
1. Characterise the block: volume, how it was distributed across intensities,
   consistency, and whether progression was gradual or spiky (use weekly TRIMP
   and ACWR).
2. Judge whether the athlete ABSORBED that load, using the recovery data — a
   block is only successful if it was recovered from.
3. Identify the limiter: what is most holding performance back right now
   (aerobic base, durability, recovery, consistency, or intensity discipline)?
4. Prescribe the next block accordingly. Every prescription must be consistent
   with the recovery picture — do not add volume or intensity on top of a
   recovery deficit.

## OUTPUT
Return ONLY valid JSON, no markdown fences:
{
  "headline": "one sentence on the block just completed",
  "block_review": {
    "volume": "...", "intensity_distribution": "...", "consistency": "...",
    "progression": "...", "absorbed": "yes | partially | no", "evidence": "numbers"
  },
  "limiter": { "what": "...", "why": "...", "evidence": "numbers" },
  "next_block": {
    "focus": "...", "duration_weeks": 0,
    "weekly_structure": ["..."],
    "volume_guidance": "...", "intensity_guidance": "..."
  },
  "do_now": [ { "action": "...", "why": "...", "priority": "high | medium" } ],
  "avoid": [ { "thing": "...", "why": "..." } ]
}

## RULES
- Cite real numbers. Practical for a recreational runner training 3-5x/week.
- Never prescribe more load than the recovery data supports; if recovery is
  poor, the correct prescription is recovery, and say what must improve first.
- Compare the athlete only against their own history.
- Return ONLY the JSON object.`;
}
