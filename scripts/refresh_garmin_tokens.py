#!/usr/bin/env python3
"""Refresh Garmin OAuth tokens and update the GitHub secret.

Usage:
    python scripts/refresh_garmin_tokens.py [--dry-run]

Reads credentials from config.local.yaml (garmin.email / garmin.password),
logs in to Garmin Connect, encodes the fresh OAuth tokens as a base64 zip,
and pushes them to the GARMIN_TOKENS_B64 GitHub secret via `gh secret set`.

Options:
    --dry-run   Log in and generate tokens but do NOT update the GitHub secret.
"""

import os
import shutil
import subprocess
import sys
import tempfile

# Allow importing project modules when invoked from repo root or scripts/
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from garmin_token_store import encode_token_store_dir_as_zip_b64  # noqa: E402
from utils import load_config  # noqa: E402


def _resolve_repo() -> str:
    """Return the GitHub owner/repo slug for the current repository."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=SCRIPTS_DIR,
            text=True,
        ).strip()
    except Exception:
        return ""
    # Handle both HTTPS and SSH URLs
    for prefix in ("https://github.com/", "git@github.com:"):
        if url.startswith(prefix):
            slug = url[len(prefix):]
            return slug.removesuffix(".git")
    return ""


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    # --- load credentials ---------------------------------------------------
    config = load_config()
    garmin_cfg = config.get("garmin", {})
    email = garmin_cfg.get("email") or os.environ.get("GARMIN_EMAIL", "")
    password = garmin_cfg.get("password") or os.environ.get("GARMIN_PASSWORD", "")

    if not email or not password:
        print("Error: Garmin email/password not found.")
        print("Set them in config.local.yaml or GARMIN_EMAIL/GARMIN_PASSWORD env vars.")
        return 1

    # --- login ---------------------------------------------------------------
    try:
        from garminconnect import Garmin
    except ImportError:
        print("Error: garminconnect package not installed. Run: pip install garminconnect")
        return 1

    print(f"Logging in to Garmin Connect as {email} ...")
    try:
        client = Garmin(email, password)
        client.login()
    except Exception as exc:
        print(f"Login failed: {exc}")
        return 1
    print("Login successful.")

    # --- save tokens to temp dir --------------------------------------------
    token_dir = tempfile.mkdtemp(prefix="garmin_tokens_")
    try:
        client.garth.dump(token_dir)
        print(f"Tokens saved to {token_dir}/")

        b64 = encode_token_store_dir_as_zip_b64(token_dir)
        print(f"Encoded token store ({len(b64)} chars).")

        if dry_run:
            print("[dry-run] Skipping GitHub secret update.")
            return 0

        # --- update GitHub secret --------------------------------------------
        repo = _resolve_repo()
        cmd = ["gh", "secret", "set", "GARMIN_TOKENS_B64"]
        if repo:
            cmd += ["--repo", repo]

        proc = subprocess.run(
            cmd,
            input=b64,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            print(f"Failed to update GitHub secret: {proc.stderr.strip()}")
            return 1

        print(f"Updated GARMIN_TOKENS_B64 secret on {repo or 'origin'}.")
        print("Done! The next scheduled sync should succeed.")
        return 0
    finally:
        shutil.rmtree(token_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
