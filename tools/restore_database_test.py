"""
Teste de restore em banco alvo isolado.

Nunca aponte RESTORE_DATABASE_URL para producao. Use um projeto Supabase vazio,
um Postgres local ou um banco temporario.

Tambem valida backups `.rest.json` gerados pelo fallback REST, reconstituindo
os registros em SQLite temporario para provar integridade de leitura.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def validate_rest_backup(backup: Path) -> dict:
    data = json.loads(backup.read_text(encoding="utf-8"))
    if data.get("metadata", {}).get("format") != "supabase_rest_json":
        raise ValueError("Arquivo JSON nao parece ser um backup REST do Madame do Luar.")
    tables = data.get("tables")
    summary = data.get("summary")
    if not isinstance(tables, dict) or not isinstance(summary, dict):
        raise ValueError("Backup REST sem secoes obrigatorias `tables` e `summary`.")

    conn = sqlite3.connect(":memory:")
    restored_rows = 0
    try:
        for table, rows in tables.items():
            if not isinstance(rows, list):
                raise ValueError(f"Tabela {table} nao esta em formato de lista.")
            conn.execute(f'CREATE TABLE "{table}" (payload TEXT NOT NULL)')
            conn.executemany(
                f'INSERT INTO "{table}" (payload) VALUES (?)',
                [(json.dumps(row, ensure_ascii=False, sort_keys=True),) for row in rows],
            )
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if count != len(rows):
                raise ValueError(f"Contagem divergente em {table}: esperado {len(rows)}, obtido {count}.")
            restored_rows += count
    finally:
        conn.close()

    return {
        "backup_file": str(backup),
        "backup_type": "supabase_rest_json",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "tables": len(tables),
        "rows": restored_rows,
        "skipped_tables": [
            table for table, item in summary.items()
            if isinstance(item, dict) and item.get("status") != "ok"
        ],
    }


def write_restore_report(report: dict) -> Path:
    output_dir = Path(os.getenv("BACKUP_DIR", "backups"))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "latest_restore_test.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaura um backup .dump em banco isolado para validar recuperacao.")
    parser.add_argument("backup", nargs="?", help="Caminho do arquivo .dump/.rest.json gerado pelo backup_database.py. Se omitido, usa backups/latest_backup_manifest.json.")
    args = parser.parse_args()

    if args.backup:
        backup = Path(args.backup)
    else:
        manifest_file = Path(os.getenv("BACKUP_DIR", "backups")) / "latest_backup_manifest.json"
        if not manifest_file.exists():
            print(f"ERRO: manifesto de backup nao encontrado: {manifest_file}")
            return 1
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        backup = Path(manifest.get("backup_file") or "")
    if not backup.exists():
        print(f"ERRO: backup nao encontrado: {backup}")
        return 1

    if backup.suffix == ".json" or backup.name.endswith(".rest.json"):
        try:
            report = validate_rest_backup(backup)
        except Exception as exc:
            print(f"ERRO: restore/validacao REST falhou: {exc}")
            return 1
        report_file = write_restore_report(report)
        print(f"Restore REST validado em SQLite temporario: {report['rows']} registros em {report['tables']} tabelas.")
        if report["skipped_tables"]:
            print("Tabelas ignoradas no backup por indisponibilidade/permissao: " + ", ".join(report["skipped_tables"]))
        print(f"Relatorio: {report_file}")
        return 0

    restore_url = os.getenv("RESTORE_DATABASE_URL")
    if not restore_url:
        print("ERRO: configure RESTORE_DATABASE_URL para um banco de teste isolado.")
        return 1
    if not shutil.which("pg_restore"):
        print("ERRO: pg_restore nao encontrado no PATH.")
        return 1

    cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", "--dbname", restore_url, str(backup)]
    print(f"Testando restore de {backup} em banco isolado.")
    subprocess.run(cmd, check=True)
    report_file = write_restore_report({
        "backup_file": str(backup),
        "backup_type": "postgres_custom_dump",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "target": "RESTORE_DATABASE_URL",
    })
    print("Restore testado com sucesso.")
    print(f"Relatorio: {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
