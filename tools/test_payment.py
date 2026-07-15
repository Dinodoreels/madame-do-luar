import os

import requests
from dotenv import load_dotenv


load_dotenv()


def test_mercado_pago_config() -> bool:
    token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
    if not token:
        print("FAIL MERCADO_PAGO_ACCESS_TOKEN nao configurado.")
        return False
    if not os.getenv("MERCADO_PAGO_WEBHOOK_SECRET"):
        print("SKIP MERCADO_PAGO_WEBHOOK_SECRET ausente. Checkout pode ser criado, mas webhook real deve ser validado no painel.")

    missing_amounts = [
        name
        for name in (
            "MERCADO_PAGO_LEITURA_AMOUNT",
            "MERCADO_PAGO_ASSINATURA_MENSAL_AMOUNT",
            "MERCADO_PAGO_ASSINATURA_ANUAL_AMOUNT",
        )
        if not os.getenv(name)
    ]
    if missing_amounts:
        print("WARN valores Mercado Pago ausentes; defaults locais serao usados: " + ", ".join(missing_amounts))

    try:
        response = requests.get(
            "https://api.mercadopago.com/users/me",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=20,
        )
        data = response.json()
    except requests.RequestException as exc:
        print(f"FAIL Mercado Pago API: {exc}")
        return False
    except ValueError:
        print("FAIL Mercado Pago API retornou JSON invalido.")
        return False

    if response.status_code >= 400:
        print(f"FAIL Mercado Pago API HTTP {response.status_code}: {data.get('message') or data.get('error') or data}")
        return False

    print(f"OK Mercado Pago conectado: {data.get('email') or data.get('nickname') or data.get('id')} / {data.get('site_id') or 'site desconhecido'}")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if test_mercado_pago_config() else 1)
