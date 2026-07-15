import os
from typing import Iterable

import requests
from dotenv import load_dotenv


REQUIRED_TABLES = [
    "users",
    "password_reset_tokens",
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
    "idempotency_keys",
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
    "system_logs",
    "audit_logs",
    "settings",
    "internal_alerts",
    "reprocess_queue",
]


REQUIRED_COLUMNS = {
    "users": [
        "user_id",
        "nome",
        "email",
        "whatsapp",
        "senha_hash",
        "role",
        "status",
        "plan_id",
        "credits_balance",
        "primeira_tiragem_gratis",
        "assinante",
        "last_login_at",
    ],
    "payments": [
        "payment_id",
        "user_id",
        "plan_id",
        "package_id",
        "product_type",
        "product_name",
        "status",
        "amount",
        "valor",
        "tipo",
        "method",
        "gateway",
        "gateway_ref",
        "transaction_id",
        "qr_code_url",
        "pix_copy_paste",
        "checkout_url",
        "webhook_payload",
        "gateway_payload",
        "error_message",
        "credits_to_release",
        "credits_released",
        "approved_at",
        "expires_at",
        "abandoned_at",
    ],
    "payment_webhook_events": [
        "event_id",
        "payment_id",
        "gateway",
        "event_type",
        "transaction_id",
        "payload",
        "processed",
        "idempotency_key",
    ],
    "credit_transactions": [
        "transaction_id",
        "user_id",
        "type",
        "amount",
        "related_payment_id",
        "related_reading_id",
        "idempotency_key",
        "metadata",
    ],
    "idempotency_keys": [
        "key",
        "scope",
        "status",
        "request_hash",
        "response_payload",
        "locked_until",
    ],
    "readings": [
        "reading_id",
        "question_id",
        "interpretacao",
        "prompt_id",
        "model",
        "tokens_used",
        "estimated_cost",
        "status",
        "error_message",
    ],
    "message_events": [
        "message_id",
        "user_id",
        "question_id",
        "payment_id",
        "tipo",
        "canal",
        "subject",
        "mensagem",
        "variables",
        "status",
        "error_message",
        "attempts",
        "max_attempts",
        "agendado_para",
        "enviado_em",
    ],
    "notification_logs": [
        "log_id",
        "message_event_id",
        "user_id",
        "channel",
        "type",
        "recipient",
        "subject",
        "status",
        "error_message",
        "provider_response",
        "metadata",
    ],
    "automation_rules": ["rule_id", "name", "event_type", "status", "audience_filter"],
    "automation_steps": ["step_id", "rule_id", "step_order", "delay_minutes", "channel", "subject", "template", "status"],
    "customer_tags": ["tag_id", "name", "description", "color", "status"],
    "customer_segments": ["segment_id", "name", "description", "rules", "status"],
    "system_logs": ["log_id", "user_id", "admin_id", "event_type", "description", "metadata", "severity"],
    "audit_logs": ["audit_id", "user_id", "admin_id", "action", "entity_type", "entity_id", "before_data", "after_data", "metadata", "severity"],
}


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


def _safe_message(response: requests.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data.get("message") or data.get("hint") or response.text
        return str(data)
    except Exception:
        return response.text


def _check_select(url: str, headers: dict, table: str, select: str = "*") -> tuple[bool, str]:
    response = requests.get(
        f"{url}/rest/v1/{table}?select={select}&limit=1",
        headers=headers,
        timeout=15,
    )
    if response.status_code < 400:
        return True, "ok"
    return False, _safe_message(response)


def _check_rpc(url: str, headers: dict, function_name: str) -> tuple[bool, str]:
    response = requests.post(
        f"{url}/rest/v1/rpc/{function_name}",
        headers=headers,
        json=RPC_TEST_PAYLOADS[function_name],
        timeout=15,
    )
    if response.status_code == 404:
        return False, "funcao nao encontrada no schema cache"
    message = _safe_message(response)
    if response.status_code < 500:
        return True, message or "publicada"
    return False, message


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
    ok = _print_group("Tabelas obrigatorias", tables) and ok
    ok = _print_group("Colunas criticas", columns) and ok
    ok = _print_group("Funcoes RPC", rpc) and ok

    if not ok:
        raise SystemExit("\nSchema real ainda nao esta coerente com architecture/schema.sql.")
    print("\nSchema real coerente com a Fase 3.")


if __name__ == "__main__":
    main()
