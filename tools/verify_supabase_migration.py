import os
from typing import Iterable

import requests
from dotenv import load_dotenv


REQUIRED_TABLES = [
    "plans",
    "credit_packages",
    "coupons",
    "plan_change_history",
    "credit_transactions",
    "payment_webhook_events",
    "idempotency_keys",
    "internal_alerts",
    "reprocess_queue",
    "ai_prompts",
    "settings",
    "system_logs",
    "password_reset_tokens",
]

REQUIRED_RPC = [
    "consume_user_credits",
    "refund_user_credits",
    "admin_adjust_user_credits",
    "approve_payment_once",
    "purchase_ritual_with_credits",
    "cleanup_operational_logs",
]

RPC_TEST_PAYLOADS = {
    "consume_user_credits": {
        "p_user_id": "00000000-0000-0000-0000-000000000000",
        "p_amount": 1,
        "p_reason": "verificacao de schema",
        "p_related_reading_id": None,
    },
    "refund_user_credits": {
        "p_user_id": "00000000-0000-0000-0000-000000000000",
        "p_amount": 1,
        "p_reason": "verificacao de schema",
        "p_related_reading_id": None,
    },
    "admin_adjust_user_credits": {
        "p_user_id": "00000000-0000-0000-0000-000000000000",
        "p_amount": 1,
        "p_type": "add",
        "p_reason": "verificacao de schema",
        "p_admin_id": None,
        "p_related_payment_id": None,
        "p_related_reading_id": None,
        "p_expires_at": None,
    },
    "approve_payment_once": {
        "p_payment_id": "00000000-0000-0000-0000-000000000000",
        "p_webhook_payload": {},
        "p_admin_id": None,
        "p_manual": False,
        "p_reason": "verificacao de schema",
    },
    "purchase_ritual_with_credits": {
        "p_user_id": "00000000-0000-0000-0000-000000000000",
        "p_ritual_id": "00000000-0000-0000-0000-000000000000",
        "p_amount": 1,
        "p_reason": "verificacao de schema",
        "p_coupon_code": None,
    },
    "cleanup_operational_logs": {
        "p_system_log_days": 99999,
        "p_notification_log_days": 99999,
        "p_webhook_event_days": 99999,
    },
}

REQUIRED_COLUMNS = {
    "users": ["role", "status", "credits_balance", "plan_id", "senha_hash", "last_login_at"],
    "payments": [
        "plan_id",
        "package_id",
        "product_type",
        "amount",
        "gateway",
        "transaction_id",
        "pix_copy_paste",
        "credits_to_release",
        "credits_released",
        "approved_at",
        "expires_at",
    ],
    "readings": ["prompt_id", "model", "tokens_used", "estimated_cost", "status", "error_message"],
    "credit_transactions": ["related_payment_id", "related_reading_id", "idempotency_key", "metadata"],
    "payment_webhook_events": ["idempotency_key", "processed", "processed_at"],
    "idempotency_keys": ["key", "scope", "status", "request_hash", "response_payload", "locked_until"],
}


def _headers() -> tuple[str, dict]:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL e SUPABASE_KEY precisam estar definidos no .env.")
    return url.rstrip("/"), {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _check_select(url: str, headers: dict, table: str, select: str = "*") -> tuple[bool, str]:
    response = requests.get(
        f"{url}/rest/v1/{table}?select={select}&limit=1",
        headers=headers,
        timeout=15,
    )
    if response.status_code < 400:
        return True, "ok"
    try:
        data = response.json()
        return False, data.get("message") or response.text
    except Exception:
        return False, response.text


def _check_rpc(url: str, headers: dict, function_name: str) -> tuple[bool, str]:
    response = requests.post(
        f"{url}/rest/v1/rpc/{function_name}",
        headers=headers,
        json=RPC_TEST_PAYLOADS[function_name],
        timeout=15,
    )
    if response.status_code == 404:
        return False, "funcao nao encontrada no schema cache"
    try:
        data = response.json()
        message = data.get("message") if isinstance(data, dict) else str(data)
    except Exception:
        message = response.text
    if isinstance(data, dict) and data.get("erro") == "Usuario nao encontrado.":
        return True, "ok"
    # A funcao existir mas rejeitar a chamada por regra de negocio confirma publicacao.
    return True, message or "existe"


def _print_group(title: str, rows: Iterable[tuple[str, bool, str]]) -> bool:
    print(f"\n[{title}]")
    all_ok = True
    for name, ok, detail in rows:
        status = "OK" if ok else "PENDENTE"
        print(f"- {status:8} {name}: {detail}")
        all_ok = all_ok and ok
    return all_ok


def main() -> None:
    url, headers = _headers()
    tables = [(table, *_check_select(url, headers, table)) for table in REQUIRED_TABLES]
    columns = [
        (f"{table}.{column}", *_check_select(url, headers, table, column))
        for table, columns in REQUIRED_COLUMNS.items()
        for column in columns
    ]
    rpc = [(function_name, *_check_rpc(url, headers, function_name)) for function_name in REQUIRED_RPC]

    ok = True
    ok = _print_group("Tabelas da migration", tables) and ok
    ok = _print_group("Colunas adicionadas", columns) and ok
    ok = _print_group("Funcoes RPC", rpc) and ok

    if not ok:
        raise SystemExit("\nMigration ainda nao esta aplicada por completo no Supabase.")
    print("\nMigration aplicada e visivel pelo REST schema cache.")


if __name__ == "__main__":
    main()
