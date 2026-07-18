#!/usr/bin/env python3
"""Interactive one-time Garmin login for local development.

Prompts for your Garmin email/password (and MFA code if enabled), logs in,
and writes:
  - .garmin_token_store/      (token dir, reused by sync_garmin.py)
  - config.local.yaml         (source: garmin + garmin.token_store_b64)

Run from anywhere; it operates on the repo root. Nothing is committed —
config.local.yaml and .garmin_token_store are gitignored.
"""
from __future__ import annotations

import getpass
import os
import sys

# Resolve repo root (parent of this scripts/ dir) and make helpers importable.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
os.chdir(REPO_ROOT)

from garminconnect import Garmin  # noqa: E402
from garmin_token_store import encode_token_store_dir_as_zip_b64  # noqa: E402

try:
    import yaml  # noqa: E402
except ImportError:
    print("ERROR: PyYAML not installed. Activate .venv first.", file=sys.stderr)
    sys.exit(1)

TOKEN_DIR = ".garmin_token_store"
CONFIG_LOCAL = "config.local.yaml"


def main() -> int:
    print("== Garmin local login ==")
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password (hidden): ")
    if not email or not password:
        print("ERROR: email and password are required.", file=sys.stderr)
        return 1

    garmin = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA one-time code (check email/SMS): ").strip(),
    )

    print("Logging in to Garmin Connect...")
    garmin.login()  # triggers prompt_mfa callback if MFA is enabled

    # Sanity check: pull the athlete's name so we know the session works.
    try:
        full_name = garmin.get_full_name()
        print(f"Login OK. Authenticated as: {full_name}")
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"Login succeeded but profile fetch failed ({exc}); continuing.")

    # Persist the native token store, then encode it for config/GitHub secret.
    os.makedirs(TOKEN_DIR, exist_ok=True)
    garmin.client.dump(TOKEN_DIR)
    token_b64 = encode_token_store_dir_as_zip_b64(TOKEN_DIR)
    print(f"Token store written to {TOKEN_DIR}/ ({len(token_b64)} b64 chars)")

    # Merge into config.local.yaml without clobbering unrelated keys.
    cfg = {}
    if os.path.exists(CONFIG_LOCAL):
        with open(CONFIG_LOCAL, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    cfg["source"] = "garmin"
    garmin_cfg = cfg.get("garmin") or {}
    garmin_cfg["token_store_b64"] = token_b64
    cfg["garmin"] = garmin_cfg

    with open(CONFIG_LOCAL, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, default_flow_style=False)
    print(f"Updated {CONFIG_LOCAL} (source=garmin, garmin.token_store_b64 set).")

    print("\nDone. Next:")
    print("  .venv/bin/python scripts/sync_garmin.py --dry-run   # verify auth")
    print("  bash scripts/dev_dashboard.sh --sync                # full sync + serve")
    print("\nFor GitHub Actions, copy the b64 into secret GARMIN_TOKENS_B64:")
    print("  .venv/bin/python -c \"import sys;sys.path.insert(0,'scripts');"
          "from garmin_token_store import encode_token_store_dir_as_zip_b64 as e;"
          "print(e('.garmin_token_store'))\" | gh secret set GARMIN_TOKENS_B64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
