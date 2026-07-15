import argparse
import os
import time
import uuid

from dotenv import load_dotenv

import db_client
from flow_pagamento import criar_sessao_checkout


def _ensure_env() -> None:
    load_dotenv()
    missing = []
    for key in ("MERCADO_PAGO_ACCESS_TOKEN", "MERCADO_PAGO_WEBHOOK_SECRET"):
        if not os.getenv(key):
            missing.append(key)
    if missing:
        raise SystemExit("Variaveis ausentes no .env: " + ", ".join(missing))


def _create_test_user() -> dict:
    email = f"mp-webhook-{uuid.uuid4().hex[:8]}@madamedoluar.test"
    result = db_client.criar_usuario(
        nome="Teste Mercado Pago Webhook",
        email=email,
        senha="TesteMercadoPago123!",
        whatsapp=None,
    )
    if "erro" in result:
        raise SystemExit(result["erro"])
    return result["usuario"]


def _wait_for_status(payment_id: str, timeout_seconds: int, interval_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_payment = {}

    while time.monotonic() < deadline:
        payment = db_client.buscar_por_id("payments", "payment_id", payment_id) or {}
        last_payment = payment
        status = payment.get("status")
        print(f"Status atual: {status or 'desconhecido'}")

        if status == "approved":
            return payment
        if status in {"failed", "expired", "cancelled", "refused", "refunded", "error", "abandoned"}:
            raise SystemExit(f"Pagamento terminou com status inesperado: {status}")

        time.sleep(interval_seconds)

    raise SystemExit(
        "Tempo esgotado aguardando webhook Mercado Pago. "
        f"Ultimo status: {last_payment.get('status') or 'desconhecido'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida Mercado Pago checkout + webhook de ponta a ponta.")
    parser.add_argument("--timeout", type=int, default=900, help="Tempo maximo de espera em segundos.")
    parser.add_argument("--interval", type=int, default=10, help="Intervalo de consulta em segundos.")
    args = parser.parse_args()

    _ensure_env()
    user = _create_test_user()
    checkout = criar_sessao_checkout(user["user_id"], "leitura", user.get("email"))
    if "erro" in checkout:
        raise SystemExit(checkout["erro"])

    print("Checkout Mercado Pago de teste criado.")
    print(f"Usuario: {user['user_id']}")
    print(f"Pagamento: {checkout['payment_id']}")
    print(f"Preferencia: {checkout['session_id']}")
    print(f"URL para pagar:\n{checkout['url']}")
    print("Aguardando webhook atualizar o pagamento para approved...")

    payment = _wait_for_status(checkout["payment_id"], args.timeout, args.interval)
    print(f"OK webhook Mercado Pago validado. Status final: {payment.get('status')}")


if __name__ == "__main__":
    main()
