"""Dead-man's-switch healthcheck ping for the ETL pipeline.

Pings HEALTHCHECKS_URL (healthchecks.io) at the end of a run. If the URL is
missing (dry-mode), writes a local heartbeat log instead and exits 0.

Exit codes:
  0 = heartbeat sent (or dry-mode logged)
  1 = ping failed (fail-fast — the caller's cron can surface the error)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG_DIR = Path("data")
LOG_PATH = LOG_DIR / "healthcheck.log"


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _log_local(status: str, detail: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(UTC).isoformat()} | {status} | {detail}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file to load HEALTHCHECKS_URL from (optional)",
    )
    args = parser.parse_args()

    _load_env(Path(args.env_file))
    url = os.environ.get("HEALTHCHECKS_URL", "").strip()

    if not url:
        _log_local("DRY", "HEALTHCHECKS_URL not set - local heartbeat only")
        print("healthcheck: dry-mode (HEALTHCHECKS_URL not set) - exit 0")
        return

    logging.getLogger("urllib3").setLevel(logging.ERROR)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        _log_local("FAIL", f"ping {url} failed: {e}")
        print(f"healthcheck: FAIL {e}", file=sys.stderr)
        sys.exit(1)

    _log_local("OK", f"ping {url} -> {resp.status_code}")
    print(f"healthcheck: OK ({resp.status_code})")


if __name__ == "__main__":
    main()
