---
description: Refresh Garmin OAuth tokens and update the GitHub secret to fix sync failures
allowed-tools: [Bash, Read]
---

Refresh the Garmin OAuth tokens for this project. Run the following steps:

1. Activate the virtual environment: `source .venv/bin/activate`
2. Run the refresh script: `python scripts/refresh_garmin_tokens.py`
3. If successful, optionally trigger a sync to verify: `gh workflow run "Sync Heatmaps" --field source=garmin`
4. Report the result to the user.

If the script fails with a login error, inform the user that their Garmin credentials in `config.local.yaml` may need updating.
