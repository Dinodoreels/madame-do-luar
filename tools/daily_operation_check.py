"""
Executa a verificacao diaria de operacao do Madame do Luar.

Uso:
  python tools/daily_operation_check.py
"""
import json
from pathlib import Path

import db_client


def main() -> int:
    result = db_client.rotina_diaria_verificacao()
    summary = result.get("resultado", {})
    output_dir = Path(__file__).resolve().parents[1] / ".tmp"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "daily_operation_check.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("Verificacao diaria executada.")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary.get("health_status") in ("ok", "degraded") else 2


if __name__ == "__main__":
    raise SystemExit(main())
