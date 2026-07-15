import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

load_dotenv(ROOT / ".env")

from app.modules.automation.job_queue import job_queue_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker de jobs Madame do Luar.")
    parser.add_argument("--limit", type=int, default=int(os.getenv("JOB_WORKER_LIMIT", "25")))
    parser.add_argument("--interval", type=int, default=int(os.getenv("JOB_WORKER_INTERVAL_SECONDS", "15")))
    parser.add_argument("--once", action="store_true", help="Processa uma vez e encerra.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    while True:
        result = job_queue_service.process_due(limit=args.limit, dry_run=args.dry_run)
        print(result, flush=True)
        if args.once:
            break
        time.sleep(max(1, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
