"""
Valida o processamento de webhook Mercado Pago sem depender de clique manual.

O script cria uma assinatura pendente real no Supabase, assina um payload no
mesmo formato esperado pelo endpoint e simula a consulta aprovada do Mercado
Pago dentro do processo local.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time
import uuid

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

import db_client
import flow_pagamento


def _ensure_env() -> str:
    load_dotenv()
    secret = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise SystemExit("MERCADO_PAGO_WEBHOOK_SECRET ausente no .env.")
    return secret


def _signature(secret: str, payment_id: str, request_id: str, ts: str) -> str:
    manifest = f"id:{payment_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def _create_user() -> dict:
    email = f"mp-local-webhook-{uuid.uuid4().hex[:8]}@madamedoluar.test"
    result = db_client.criar_usuario(
        nome="Teste Webhook Local Mercado Pago",
        email=email,
        senha="TesteMercadoPago123!",
        whatsapp=None,
    )
    if "erro" in result:
        raise SystemExit(result["erro"])
    return result["usuario"]


def main() -> None:
    secret = _ensure_env()
    user = _create_user()
    checkout = flow_pagamento.criar_sessao_checkout(user["user_id"], "assinatura_mensal", user.get("email"))
    if "erro" in checkout:
        raise SystemExit(checkout["erro"])

    mp_payment_id = str(10_000_000_000 + int(time.time()))
    request_id = str(uuid.uuid4())
    ts = str(int(time.time()))
    payload = {"type": "payment", "data": {"id": mp_payment_id}}

    original_fetch_payment = flow_pagamento._fetch_payment

    def fake_fetch_payment(payment_id: str) -> dict:
        if str(payment_id) != mp_payment_id:
            return {"erro": f"Pagamento Mercado Pago inesperado: {payment_id}"}
        return {
            "id": mp_payment_id,
            "status": "approved",
            "status_detail": "accredited",
            "external_reference": checkout["payment_id"],
            "order": {"id": checkout["session_id"]},
        }

    flow_pagamento._fetch_payment = fake_fetch_payment
    try:
        result = flow_pagamento.processar_webhook_mercado_pago(
            payload,
            _signature(secret, mp_payment_id, request_id, ts),
            request_id,
        )
        duplicate_result = flow_pagamento.processar_webhook_mercado_pago(
            payload,
            _signature(secret, mp_payment_id, request_id, ts),
            request_id,
        )
    finally:
        flow_pagamento._fetch_payment = original_fetch_payment

    if result.get("payment_status") != "approved":
        raise SystemExit(f"Webhook nao aprovou pagamento: {result}")
    if duplicate_result.get("status") != "ignored" and not duplicate_result.get("resultado", {}).get("creditos", {}).get("ja_liberado"):
        raise SystemExit(f"Webhook duplicado nao foi idempotente: {duplicate_result}")

    payment = db_client.buscar_por_id("payments", "payment_id", checkout["payment_id"]) or {}
    credit_transactions = db_client.listar_registros(
        "credit_transactions",
        select="transaction_id,type,amount,related_payment_id",
        filtros=f"related_payment_id=eq.{checkout['payment_id']}&type=eq.add",
        limit=10,
    )
    assinatura = flow_pagamento.requests.get(
        f"{db_client.get_supabase_headers()[0]}/rest/v1/subscriptions"
        f"?user_id=eq.{user['user_id']}&status=eq.ativo&select=*&limit=1",
        headers=db_client.get_supabase_headers()[1],
        timeout=15,
    ).json()

    if payment.get("status") != "approved":
        raise SystemExit(f"Pagamento local nao ficou approved: {payment.get('status')}")
    if len(credit_transactions) > 1:
        raise SystemExit(f"Credito foi liberado mais de uma vez: {len(credit_transactions)} transacoes.")
    if not assinatura:
        raise SystemExit("Assinatura ativa nao foi criada.")

    print("OK webhook Mercado Pago local assinado validado.")
    print(f"Usuario: {user['user_id']}")
    print(f"Pagamento local: {checkout['payment_id']}")
    print(f"Evento: {result.get('event_id')}")
    print(f"Duplicado: {duplicate_result.get('status') or duplicate_result.get('payment_status')}")
    print(f"Transacoes de credito do pagamento: {len(credit_transactions)}")
    print(f"Assinatura: {assinatura[0].get('status')} / {assinatura[0].get('plano')}")


if __name__ == "__main__":
    main()
