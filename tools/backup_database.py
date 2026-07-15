"""
Backup logico do Postgres/Supabase.

Fluxo preferencial:
- `pg_dump` + DATABASE_URL, SUPABASE_DB_URL, POSTGRES_URL ou SUPABASE_DB_PASSWORD.

Fallback operacional:
- exportacao JSON via Supabase REST usando SUPABASE_URL e SUPABASE_KEY.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

REST_TABLES = [
    "users",
    "admin_users",
    "plans",
    "credit_packages",
    "coupons",
    "plan_change_history",
    "credit_transactions",
    "cards",
    "questions",
    "ai_prompts",
    "readings",
    "daily_cards",
    "subscriptions",
    "payments",
    "payment_webhook_events",
    "rituals",
    "ritual_purchases",
    "message_events",
    "automation_rules",
    "automation_steps",
    "notification_logs",
    "customer_tags",
    "user_customer_tags",
    "customer_segments",
    "user_customer_segments",
    "admin_customer_notes",
    "segment_automation_triggers",
    "system_logs",
    "audit_logs",
    "settings",
    "internal_alerts",
    "reprocess_queue",
]


def database_url() -> str | None:
    direct = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or os.getenv("POSTGRES_URL")
    if direct:
        return direct
    supabase_url = os.getenv("SUPABASE_URL")
    password = os.getenv("SUPABASE_DB_PASSWORD")
    if not supabase_url or not password:
        return None
    host = urlparse(supabase_url).netloc
    project_ref = host.split(".")[0]
    return f"postgresql://postgres:{quote_plus(password)}@db.{project_ref}.supabase.co:5432/postgres"


def supabase_rest_config() -> tuple[str, dict[str, str]] | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return url.rstrip("/"), {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_with_pg_dump(url: str, output_dir: Path, stamp: str) -> Path:
    output_file = output_dir / f"madame_do_luar_{stamp}.dump"
    cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(output_file), url]
    print(f"Gerando backup Postgres em {output_file}")
    subprocess.run(cmd, check=True)
    return output_file


def fetch_table(url: str, headers: dict[str, str], table: str, page_size: int) -> tuple[str, list[dict], str | None]:
    rows: list[dict] = []
    offset = 0
    count_status = "ok"
    while True:
        endpoint = f"{url}/rest/v1/{table}?select=*&limit={page_size}&offset={offset}"
        response = requests.get(
            endpoint,
            headers={**headers, "Prefer": "count=exact"},
            timeout=30,
        )
        if response.status_code >= 400:
            message = response.text
            try:
                data = response.json()
                message = data.get("message") or data.get("hint") or message
            except Exception:
                pass
            return "skipped", rows, message

        batch = response.json()
        if not isinstance(batch, list):
            return "skipped", rows, f"Resposta inesperada: {type(batch).__name__}"
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return count_status, rows, None


def dump_with_rest(output_dir: Path, stamp: str) -> Path:
    config = supabase_rest_config()
    if not config:
        raise RuntimeError("configure SUPABASE_URL e SUPABASE_KEY para o fallback REST.")

    url, headers = config
    page_size = int(os.getenv("BACKUP_PAGE_SIZE", "1000"))
    backup = {
        "metadata": {
            "app": "madame_do_luar",
            "format": "supabase_rest_json",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": url,
            "page_size": page_size,
            "tables_requested": REST_TABLES,
        },
        "tables": {},
        "summary": {},
    }

    print("Gerando backup via Supabase REST.")
    for table in REST_TABLES:
        status, rows, error = fetch_table(url, headers, table, page_size)
        backup["tables"][table] = rows
        backup["summary"][table] = {
            "status": status,
            "rows": len(rows),
            "error": error,
        }
        label = "ok" if status == "ok" else "ignorado"
        print(f"- {table}: {label}, {len(rows)} registros")

    output_file = output_dir / f"madame_do_luar_{stamp}.rest.json"
    output_file.write_text(json.dumps(backup, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return output_file


def write_manifest(output_dir: Path, backup_file: Path, mode: str) -> Path:
    manifest = {
        "app": "madame_do_luar",
        "backup_file": str(backup_file),
        "backup_type": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": backup_file.stat().st_size,
        "sha256": sha256_file(backup_file),
    }
    manifest_file = output_dir / "latest_backup_manifest.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_file


def main() -> int:
    output_dir = Path(os.getenv("BACKUP_DIR", "backups"))
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    url = database_url()
    pg_dump_path = shutil.which("pg_dump")

    if url and pg_dump_path:
        output_file = dump_with_pg_dump(url, output_dir, stamp)
        mode = "postgres_custom_dump"
    else:
        if not url:
            print("Aviso: URL direta do Postgres ausente; usando fallback Supabase REST.")
        if url and not pg_dump_path:
            print("Aviso: pg_dump nao encontrado no PATH; usando fallback Supabase REST.")
        try:
            output_file = dump_with_rest(output_dir, stamp)
            mode = "supabase_rest_json"
        except Exception as exc:
            print(f"ERRO: backup nao gerado: {exc}")
            print("Configure pg_dump + DATABASE_URL/SUPABASE_DB_URL/POSTGRES_URL/SUPABASE_DB_PASSWORD ou SUPABASE_URL + SUPABASE_KEY.")
            return 1

    manifest_file = write_manifest(output_dir, output_file, mode)
    print(f"Backup concluido: {output_file}")
    print(f"Manifesto: {manifest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
