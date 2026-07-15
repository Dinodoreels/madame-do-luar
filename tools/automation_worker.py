import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

import automation_engine


load_dotenv()


def main() -> int:
    interval = int(os.getenv("AUTOMATION_WORKER_INTERVAL_SECONDS", "300"))
    sync_rules = os.getenv("AUTOMATION_SYNC_RULES_ON_START", "true").lower() == "true"
    if sync_rules:
        print({"sync_rules": automation_engine.sincronizar_regras_padrao()})

    print(f"Automation worker iniciado. Intervalo: {interval}s")
    while True:
        started = datetime.now(timezone.utc).isoformat()
        try:
            result = automation_engine.processar_pendentes()
            print({"started_at": started, **result})
        except Exception as exc:
            print({"started_at": started, "error": str(exc)})
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
