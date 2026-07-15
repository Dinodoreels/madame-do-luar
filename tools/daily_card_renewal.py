"""
Agenda e opcionalmente processa a campanha diaria de carta do dia renovada.

Uso local:
  python tools\\daily_card_renewal.py --process
  python tools\\daily_card_renewal.py --dry-run --limit 10
"""

import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
import automation_engine


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Campanha diaria de carta do dia renovada.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximo de usuarios carregados.")
    parser.add_argument("--dry-run", action="store_true", help="Nao grava eventos, apenas mostra elegiveis.")
    parser.add_argument("--process", action="store_true", help="Processa eventos vencidos apos agendar.")
    args = parser.parse_args()

    scheduled = automation_engine.agendar_cartas_do_dia_renovadas(limit=args.limit, dry_run=args.dry_run)
    print({"daily_card_renewal": scheduled})

    if args.process and not args.dry_run:
        processed = automation_engine.processar_pendentes(limit=max(args.limit * 2, 100))
        print({"processed": processed})
    return 0 if "erro" not in scheduled else 1


if __name__ == "__main__":
    raise SystemExit(main())
