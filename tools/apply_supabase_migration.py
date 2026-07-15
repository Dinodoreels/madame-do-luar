import os
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATION = ROOT / "architecture" / "migration_admin_operacional.sql"


def _database_url_from_supabase_password():
    supabase_url = os.getenv("SUPABASE_URL")
    password = os.getenv("SUPABASE_DB_PASSWORD")
    if not supabase_url or not password:
        return None

    host = urlparse(supabase_url).hostname or ""
    project_ref = host.split(".")[0] if host.endswith(".supabase.co") else ""
    if not project_ref:
        return None

    encoded_password = quote_plus(password)
    return f"postgresql://postgres:{encoded_password}@db.{project_ref}.supabase.co:5432/postgres"


def get_database_url():
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
        or os.getenv("POSTGRES_URL")
        or _database_url_from_supabase_password()
    )
    if database_url:
        return database_url

    raise SystemExit(
        "Conexao Postgres do Supabase ausente.\n\n"
        "Resolva adicionando UMA destas opcoes no .env:\n\n"
        "1) Connection string completa:\n"
        "   DATABASE_URL=postgresql://postgres:<senha>@db.<project-ref>.supabase.co:5432/postgres\n\n"
        "2) Apenas a senha do banco do projeto Supabase:\n"
        "   SUPABASE_DB_PASSWORD=<senha-do-banco>\n\n"
        "A SUPABASE_URL/SUPABASE_KEY servem para REST, mas nao aplicam migration SQL/DDL."
    )


def main():
    load_dotenv(ROOT / ".env")
    database_url = get_database_url()
    migration = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_MIGRATION
    if not migration.exists():
        raise SystemExit(f"Migration nao encontrada: {migration}")

    sql = migration.read_text(encoding="utf-8")
    print(f"Aplicando migration: {migration.name}")
    try:
        with psycopg2.connect(database_url, connect_timeout=20) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
    except psycopg2.OperationalError as exc:
        raise SystemExit(
            "Nao foi possivel conectar ao Postgres do Supabase.\n"
            "Confira senha, host, liberacao de rede e se o projeto esta ativo.\n\n"
            f"Detalhe tecnico: {exc}"
        ) from exc
    print("Migration aplicada com sucesso.")


if __name__ == "__main__":
    main()
