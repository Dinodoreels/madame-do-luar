"""
Checklist executavel de pre-deploy.

Uso:
  python tools/predeploy_check.py --env-file .env.production.example --allow-placeholders
  python tools/predeploy_check.py --env-file .env.production
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PRODUCTION_KEYS = [
    "APP_ENV",
    "APP_BASE_URL",
    "APP_CORS_ORIGINS",
    "ADMIN_EMAILS",
    "JWT_SECRET",
    "GEMINI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "MERCADO_PAGO_ACCESS_TOKEN",
    "MERCADO_PAGO_WEBHOOK_SECRET",
    "MERCADO_PAGO_NOTIFICATION_URL",
    "WHATSAPP_API_URL",
    "WHATSAPP_API_TOKEN",
    "SMTP_USER",
    "SMTP_PASS",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"APP_USR-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"TEST-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{20,}"),
]


def run(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, output.strip()
    except Exception as exc:
        return False, str(exc)


def load_env(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Arquivo de ambiente nao encontrado: {path}")
    return {k: v for k, v in dotenv_values(path).items() if k}


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.startswith("<") or "troque-" in text or "secret" == text.lower()


def validate_env(env: dict, allow_placeholders: bool) -> list[str]:
    errors = []
    for key in REQUIRED_PRODUCTION_KEYS:
        if key not in env or is_placeholder(env.get(key)):
            if not allow_placeholders:
                errors.append(f"{key} ausente ou placeholder.")

    if env.get("APP_ENV") != "production" and not allow_placeholders:
        errors.append("APP_ENV precisa ser production.")

    cors = env.get("APP_CORS_ORIGINS", "")
    if "*" in cors or "localhost" in cors or "127.0.0.1" in cors or "null" in cors:
        errors.append("APP_CORS_ORIGINS de producao nao pode conter *, null, localhost ou 127.0.0.1.")
    if "https://" not in env.get("APP_BASE_URL", ""):
        errors.append("APP_BASE_URL de producao precisa usar HTTPS.")
    if "https://" not in env.get("MERCADO_PAGO_NOTIFICATION_URL", ""):
        errors.append("MERCADO_PAGO_NOTIFICATION_URL precisa usar HTTPS em producao.")
    return errors


def scan_public_secrets() -> list[str]:
    findings = []
    targets = [ROOT / "frontend", ROOT / "architecture", ROOT / "prompts"]
    for base in targets:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".html", ".js", ".css", ".md", ".json"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in SECRET_PATTERNS:
                    if pattern.search(text):
                        findings.append(str(path.relative_to(ROOT)))
                        break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida readiness de deploy do Madame do Luar.")
    parser.add_argument("--env-file", default=".env.production.example")
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()

    env = load_env(ROOT / args.env_file)
    errors = validate_env(env, args.allow_placeholders)

    checks = [
        ("environment matrix", [sys.executable, "-B", "tools/validate_environment.py", "--env-file", args.env_file, "--environment", "production"] + (["--allow-placeholders"] if args.allow_placeholders else [])),
        ("python compile", [sys.executable, "-B", "-m", "py_compile", "api.py", "tools/db_client.py", "tools/automation_worker.py", "tools/daily_operation_check.py"]),
        ("import api", [sys.executable, "-B", "-c", "import api; print(len(api.app.routes))"]),
        ("admin js", ["node", "--check", "frontend/admin.js"]),
    ]
    for label, command in checks:
        ok, output = run(command)
        print(f"[{'OK' if ok else 'FAIL'}] {label}")
        if output:
            print(output[:1000])
        if not ok:
            errors.append(f"Falha em {label}.")

    leaked = scan_public_secrets()
    if leaked:
        errors.append("Possiveis segredos encontrados em arquivos publicos: " + ", ".join(leaked))
    else:
        print("[OK] scan de segredos em frontend/docs")

    if errors:
        print("\nPRE-DEPLOY BLOQUEADO:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nPRE-DEPLOY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
