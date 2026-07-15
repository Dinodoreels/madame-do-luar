import os
import sys
import uuid

from dotenv import load_dotenv

import db_client
from flow_pagamento import criar_sessao_checkout


def _test_user():
    email = f"mp-checkout-{uuid.uuid4().hex[:8]}@madamedoluar.test"
    result = db_client.criar_usuario(
        nome="Teste Mercado Pago Checkout",
        email=email,
        senha="TesteMercadoPago123!",
        whatsapp=None,
    )
    if "erro" in result:
        raise SystemExit(result["erro"])
    return result["usuario"]


def main() -> None:
    load_dotenv()
    if not os.getenv("MERCADO_PAGO_ACCESS_TOKEN"):
        raise SystemExit("MERCADO_PAGO_ACCESS_TOKEN nao configurado no .env")

    user = _test_user()
    print(f"Usuario de teste: {user['user_id']}")
    for produto in ("leitura", "assinatura_mensal", "assinatura_anual"):
        result = criar_sessao_checkout(user["user_id"], produto, user.get("email"))
        if "erro" in result:
            raise SystemExit(f"{produto}: {result['erro']}")
        payment = db_client.buscar_por_id("payments", "payment_id", result["payment_id"])
        if not payment or payment.get("status") != "pending":
            raise SystemExit(f"{produto}: pagamento pendente nao encontrado no Supabase.")
        if payment.get("gateway") != "mercado_pago":
            raise SystemExit(f"{produto}: gateway inesperado: {payment.get('gateway')}")
        print(f"OK {produto}: preference={result['session_id']} payment={result['payment_id']} status={payment.get('status')}")
        print(f"URL: {result['url']}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    main()
