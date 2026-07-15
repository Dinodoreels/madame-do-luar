"""
Valida matriz de variaveis por ambiente antes de deploy.

Uso:
  python -B tools/validate_environment.py --env-file .env.example --environment local --allow-placeholders
  python -B tools/validate_environment.py --env-file .env.homologation.example --environment homologation --allow-placeholders
  python -B tools/validate_environment.py --env-file .env.production --environment production
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_WEBHOOK_PATHS = (
    "/api/webhook/mercado-pago",
    "/api/webhooks/pix",
)

PLACEHOLDER_FRAGMENTS = (
    "<",
    ">",
    "troque-",
    "placeholder",
    "changeme",
    "change-me",
    "secret",
    "sua-chave",
    "seu-",
)

BASE_REQUIRED = [
    "APP_ENV",
    "ENVIRONMENT_NAME",
    "APP_BASE_URL",
    "APP_CORS_ORIGINS",
    "APP_TIMEZONE",
    "ADMIN_DIRECT_ACCESS",
    "ADMIN_EMAILS",
    "JWT_SECRET",
    "JWT_ISSUER",
    "JWT_EXPIRES_SECONDS",
    "LOG_LEVEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "PIX_GATEWAY",
    "PIX_CURRENCY",
    "ALLOW_MOCK_PAYMENTS",
    "MERCADO_PAGO_ENV",
    "MERCADO_PAGO_PUBLIC_KEY",
    "MERCADO_PAGO_ACCESS_TOKEN",
    "MERCADO_PAGO_WEBHOOK_SECRET",
    "MERCADO_PAGO_NOTIFICATION_URL",
    "WHATSAPP_PROVIDER",
    "WHATSAPP_API_URL",
    "WHATSAPP_API_TOKEN",
    "ALLOW_SIMULATED_NOTIFICATIONS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "AUTOMATION_WORKER_INTERVAL_SECONDS",
    "AUTOMATION_SYNC_RULES_ON_START",
    "AUTOMATION_RETRY_DELAY_MINUTES",
    "PENDING_MESSAGES_ALERT_THRESHOLD",
    "BACKUP_DIR",
]

LOCAL_OPTIONAL = {
    "GEMINI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "MERCADO_PAGO_PUBLIC_KEY",
    "MERCADO_PAGO_ACCESS_TOKEN",
    "MERCADO_PAGO_WEBHOOK_SECRET",
    "MERCADO_PAGO_NOTIFICATION_URL",
    "WHATSAPP_API_URL",
    "WHATSAPP_API_TOKEN",
    "SMTP_USER",
    "SMTP_PASS",
}

SECRET_KEYS = [
    "JWT_SECRET",
    "GEMINI_API_KEY",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_PASSWORD",
    "MERCADO_PAGO_ACCESS_TOKEN",
    "MERCADO_PAGO_WEBHOOK_SECRET",
    "WHATSAPP_API_TOKEN",
    "SMTP_PASS",
    "DATABASE_URL",
    "SUPABASE_DB_URL",
    "RESTORE_DATABASE_URL",
]


def normalize_bool(value: str | None) -> str:
    return str(value or "").strip().lower()


def is_false(value: str | None) -> bool:
    return normalize_bool(value) in {"false", "0", "no", "nao", "não"}


def is_true(value: str | None) -> bool:
    return normalize_bool(value) in {"true", "1", "yes", "sim"}


def is_placeholder(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lower = text.lower()
    return any(fragment in lower for fragment in PLACEHOLDER_FRAGMENTS)


def parse_url(value: str | None):
    try:
        return urlparse(str(value or "").strip())
    except Exception:
        return urlparse("")


def is_public_https_url(value: str | None) -> bool:
    parsed = parse_url(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return host not in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} and not host.endswith(".local")


def has_local_origin(value: str | None) -> bool:
    text = str(value or "").lower()
    return any(item in text for item in ("localhost", "127.0.0.1", "0.0.0.0", "null", "*"))


def same_host(url_a: str, url_b: str) -> bool:
    return (parse_url(url_a).hostname or "").lower() == (parse_url(url_b).hostname or "").lower()


def infer_environment(env: dict, explicit: str | None) -> str:
    if explicit:
        return explicit
    value = str(env.get("ENVIRONMENT_NAME") or env.get("APP_ENV") or "local").strip().lower()
    if value in {"prod", "production"}:
        return "production"
    if value in {"homolog", "homologacao", "homologação", "staging", "stage"}:
        return "homologation"
    return "local"


def required_for(environment: str) -> list[str]:
    if environment == "local":
        return [key for key in BASE_REQUIRED if key not in LOCAL_OPTIONAL]
    return BASE_REQUIRED


def validate_required(env: dict, environment: str, allow_placeholders: bool) -> list[str]:
    errors = []
    for key in required_for(environment):
        if key not in env or (is_placeholder(env.get(key)) and not allow_placeholders):
            errors.append(f"{key} ausente ou placeholder para {environment}.")
    return errors


def validate_common(env: dict, environment: str, allow_placeholders: bool) -> list[str]:
    errors = []
    app_env = str(env.get("APP_ENV") or "").strip().lower()
    expected_app_env = {
        "local": {"local", "development", "dev"},
        "homologation": {"staging", "stage", "homologation", "homologacao", "homologação"},
        "production": {"production"},
    }[environment]
    if app_env and app_env not in expected_app_env:
        errors.append(f"APP_ENV={app_env} nao corresponde ao ambiente {environment}.")

    jwt_secret = str(env.get("JWT_SECRET") or "")
    if environment != "local" and not allow_placeholders and len(jwt_secret) < 32:
        errors.append("JWT_SECRET precisa ter pelo menos 32 caracteres fora do ambiente local.")

    if environment != "local" and not is_public_https_url(env.get("APP_BASE_URL")):
        errors.append("APP_BASE_URL precisa ser uma URL publica HTTPS em homologacao/producao.")

    cors = str(env.get("APP_CORS_ORIGINS") or "")
    if environment != "local" and has_local_origin(cors):
        errors.append("APP_CORS_ORIGINS nao pode conter *, null, localhost ou IP local fora do ambiente local.")

    webhook = str(env.get("MERCADO_PAGO_NOTIFICATION_URL") or "")
    if environment != "local" and not is_public_https_url(webhook):
        errors.append("MERCADO_PAGO_NOTIFICATION_URL precisa ser URL publica HTTPS.")
    if environment != "local" and webhook and not same_host(webhook, str(env.get("APP_BASE_URL") or "")):
        errors.append("Webhook PIX/Mercado Pago deve apontar para o mesmo dominio publico de APP_BASE_URL.")
    if environment != "local" and webhook and not any(parse_url(webhook).path == path for path in PUBLIC_WEBHOOK_PATHS):
        errors.append("Webhook PIX/Mercado Pago deve usar /api/webhook/mercado-pago ou /api/webhooks/pix.")

    return errors


def validate_local(env: dict) -> list[str]:
    errors = []
    if str(env.get("APP_BASE_URL") or "").startswith("https://"):
        errors.append("Ambiente local deve usar URL local HTTP, nao URL publica.")
    if not has_local_origin(env.get("APP_CORS_ORIGINS")):
        errors.append("Ambiente local deve listar origem local em APP_CORS_ORIGINS.")
    return errors


def validate_homologation(env: dict, allow_placeholders: bool) -> list[str]:
    errors = []
    if not is_false(env.get("ADMIN_DIRECT_ACCESS")):
        errors.append("ADMIN_DIRECT_ACCESS deve ser false em homologacao.")
    if is_true(env.get("ALLOW_MOCK_PAYMENTS")):
        errors.append("ALLOW_MOCK_PAYMENTS nao deve ser true em homologacao compartilhada.")
    if normalize_bool(env.get("MERCADO_PAGO_ENV")) not in {"sandbox", "test", "teste"} and not allow_placeholders:
        errors.append("MERCADO_PAGO_ENV deve ser sandbox/test em homologacao.")
    if is_true(env.get("ALLOW_SIMULATED_NOTIFICATIONS")):
        errors.append("ALLOW_SIMULATED_NOTIFICATIONS deve ser false em homologacao compartilhada.")
    return errors


def validate_production(env: dict, allow_placeholders: bool) -> list[str]:
    errors = []
    if not is_false(env.get("ADMIN_DIRECT_ACCESS")):
        errors.append("ADMIN_DIRECT_ACCESS=false obrigatorio em producao.")
    if not is_false(env.get("ALLOW_MOCK_PAYMENTS")):
        errors.append("ALLOW_MOCK_PAYMENTS=false obrigatorio em producao.")
    if not is_false(env.get("ALLOW_SIMULATED_NOTIFICATIONS")):
        errors.append("ALLOW_SIMULATED_NOTIFICATIONS=false obrigatorio em producao.")
    if normalize_bool(env.get("MERCADO_PAGO_ENV")) != "production":
        errors.append("MERCADO_PAGO_ENV=production obrigatorio em producao.")

    public_url = str(env.get("APP_BASE_URL") or "")
    if public_url and any(item in public_url.lower() for item in ("render.com", "onrender.com", "localhost", "127.0.0.1")):
        errors.append("APP_BASE_URL de producao deve ser o dominio publico final, nao Render temporario/localhost.")

    if not allow_placeholders:
        for key in SECRET_KEYS:
            value = env.get(key)
            if value and is_placeholder(value):
                errors.append(f"{key} parece placeholder; producao exige segredo real separado.")
            if value and any(marker in str(value).lower() for marker in ("local", "homolog", "staging", "sandbox", "test_")):
                errors.append(f"{key} parece pertencer a outro ambiente.")
    return errors


def validate_env_file(path: Path, environment: str | None, allow_placeholders: bool) -> tuple[str, list[str]]:
    env = {k: v for k, v in dotenv_values(path).items() if k}
    resolved = infer_environment(env, environment)
    errors = validate_required(env, resolved, allow_placeholders)
    errors.extend(validate_common(env, resolved, allow_placeholders))
    if resolved == "local":
        errors.extend(validate_local(env))
    elif resolved == "homologation":
        errors.extend(validate_homologation(env, allow_placeholders))
    elif resolved == "production":
        errors.extend(validate_production(env, allow_placeholders))
    else:
        errors.append(f"Ambiente desconhecido: {resolved}")
    return resolved, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida variaveis obrigatorias por ambiente.")
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--environment", choices=["local", "homologation", "production"])
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()

    path = (ROOT / args.env_file).resolve()
    if not path.exists():
        print(f"[FAIL] Arquivo de ambiente nao encontrado: {path}")
        return 1

    environment, errors = validate_env_file(path, args.environment, args.allow_placeholders)
    print(f"Ambiente: {environment}")
    print(f"Arquivo: {path.relative_to(ROOT)}")
    if errors:
        print("\nVALIDACAO DE AMBIENTE BLOQUEADA:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALIDACAO DE AMBIENTE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
