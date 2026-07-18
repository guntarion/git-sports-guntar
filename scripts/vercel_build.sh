#!/usr/bin/env bash
# Vercel build step: hydrate site/ with the latest heatmap data JSON, which is
# persisted on the dashboard-data branch (not on main). Mirrors pages.yml.
# Non-fatal: if data can't be fetched, the site still deploys (empty fallback).
set -uo pipefail

BRANCH="${DASHBOARD_DATA_BRANCH:-dashboard-data}"
FILES=(
  "site/data.json"
  "site/activities.json"
  "site/analytics.json"
  "site/ai_insights.json"
  "site/ai_insights_history.json"
)

echo "vercel_build: hydrating data from ${BRANCH}..."

if git rev-parse --git-dir >/dev/null 2>&1; then
  git fetch --depth=1 origin "${BRANCH}" >/dev/null 2>&1 || echo "  (fetch ${BRANCH} failed; using whatever is present)"
  for f in "${FILES[@]}"; do
    if git checkout "origin/${BRANCH}" -- "$f" 2>/dev/null; then
      echo "  ok: $f"
    fi
  done
else
  echo "  (no git dir in build; skipping data hydration)"
fi

# Guarantee data.json exists so the dashboard loads without a 404.
if [ ! -f site/data.json ]; then
  echo '{"activities":[],"aggregates":{},"generated_at":null,"types":[]}' > site/data.json
  echo "  wrote empty site/data.json fallback"
fi

echo "vercel_build: done."
