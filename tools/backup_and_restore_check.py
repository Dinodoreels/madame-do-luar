"""
Executa backup e teste de restore em sequencia.

Uso:
  python tools/backup_and_restore_check.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(command: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode == 0, output


def main() -> int:
    steps = [
        ("backup", [sys.executable, "-B", "tools/backup_database.py"]),
        ("restore_check", [sys.executable, "-B", "tools/restore_database_test.py"]),
    ]
    for name, command in steps:
        ok, output = run_step(command)
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
        if output:
            print(output)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
