---
description: Export the last 6 months of Garmin health metrics to a CSV for medical consultation
argument-hint: "[--months N | --days N]"
allowed-tools: [Bash, SendUserFile]
---

Export daily health metrics (resting HR, HRV, SpO2, VO2max, sleep stages, stress,
body battery, readiness, weight, etc.) to a CSV the user can hand to another
assistant that holds their medical records.

Steps:

1. Run the export from the repo root, passing through any argument the user gave
   (default is 6 months if none): `.venv/bin/python scripts/export_health_csv.py $ARGUMENTS`
   - The script pivots the long/narrow `performance_metrics` table into one row
     per day and expands the useful `extra` JSONB fields (sleep stages, SpO2 low,
     HRV status) into their own columns.
   - Output lands in `exports/` (gitignored — this is personal medical data and
     must never be committed).
2. Read the printed output path, then deliver the file with SendUserFile so it
   is downloadable.
3. Briefly remind the user: empty cells mean no reading that day (not zero);
   sparse metrics like vo2max/weight are expected to have gaps.

Do not commit the CSV or print its contents to the terminal.
