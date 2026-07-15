"""
Integracao Mercado Pago para checkout, webhooks e cancelamento local.

Modelo adotado:
- Checkout Pro para leitura avulsa e planos mensal/anual.
- Registro `payments.pending` antes do redirecionamento.
- Liberacao/ativacao somente apos webhook + consulta do pagamento na API.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import requests
from dotenv import load_dotenv

import db_client


load_dotenv()

MP_API_BASE = "https://api.mercadopago.com"
BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")

PRODUCTS = {
    "leitura": {
        "tipo": "leitura",
        "method": "mercado_pago",
        "product_type": "reading",
        "product_name": "Leitura Avulsa",
        "amount": float(os.getenv("MERCADO_PAGO_LEITURA_AMOUNT", "19.90")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_LEITURA_CREDITS", "100")),
        "plano": None,
    },
    "recarga_100": {
        "tipo": "leitura",
        "method": "mercado_pago",
        "product_type": "package",
        "product_name": "Recarga 100 creditos",
        "amount": float(os.getenv("MERCADO_PAGO_RECARGA_100_AMOUNT", "19.90")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_RECARGA_100_CREDITS", "100")),
        "plano": None,
    },
    "recarga_300": {
        "tipo": "leitura",
        "method": "mercado_pago",
        "product_type": "package",
        "product_name": "Recarga 300 creditos",
        "amount": float(os.getenv("MERCADO_PAGO_RECARGA_300_AMOUNT", "49.90")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_RECARGA_300_CREDITS", "300")),
        "plano": None,
    },
    "recarga_500": {
        "tipo": "leitura",
        "method": "mercado_pago",
        "product_type": "package",
        "product_name": "Recarga 500 creditos",
        "amount": float(os.getenv("MERCADO_PAGO_RECARGA_500_AMOUNT", "79.90")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_RECARGA_500_CREDITS", "500")),
        "plano": None,
    },
    "recarga_1500": {
        "tipo": "leitura",
        "method": "mercado_pago",
        "product_type": "package",
        "product_name": "Recarga 1.500 creditos",
        "amount": float(os.getenv("MERCADO_PAGO_RECARGA_1500_AMOUNT", "199.90")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_RECARGA_1500_CREDITS", "1500")),
        "plano": None,
    },
    "assinatura_mensal": {
        "tipo": "assinatura",
        "method": "mercado_pago",
        "product_type": "subscription",
        "product_name": "Portal Premium Mensal",
        "amount": float(os.getenv("MERCADO_PAGO_ASSINATURA_MENSAL_AMOUNT", "49.90")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_ASSINATURA_MENSAL_CREDITS", "1500")),
        "plano": "mensal",
    },
    "assinatura_anual": {
        "tipo": "assinatura",
        "method": "mercado_pago",
        "product_type": "subscription",
        "product_name": "Portal Premium Anual",
        "amount": float(os.getenv("MERCADO_PAGO_ASSINATURA_ANUAL_AMOUNT", "397.00")),
        "credits_to_release": int(os.getenv("MERCADO_PAGO_ASSINATURA_ANUAL_CREDITS", "18250")),
        "plano": "anual",
    },
}

STATUS_MAP = {
    "approved": "approved",
    "authorized": "approved",
    "pending": "pending",
    "in_process": "pending",
    "in_mediation": "pending",
    "rejected": "failed",
    "cancelled": "cancelled",
    "refunded": "refunded",
    "charged_back": "refunded",
}


def _access_token() -> str:
    return os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "").strip()


def _mp_env() -> str:
    return os.getenv("MERCADO_PAGO_ENV", "sandbox").strip().lower()


def _using_sandbox() -> bool:
    return _mp_env() in {"sandbox", "test", "teste"}


def _app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower()


def _allow_mock_payments() -> bool:
    if _app_env() == "production":
        return False
    return os.getenv("ALLOW_MOCK_PAYMENTS", "false").strip().lower() == "true"


def _validate_environment_credentials() -> dict | None:
    return None


def _headers() -> dict:
    token = _access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _require_config() -> dict | None:
    if not _access_token():
        return {"erro": "MERCADO_PAGO_ACCESS_TOKEN nao configurado no .env"}
    env_error = _validate_environment_credentials()
    if env_error:
        return env_error
    return None


def _checkout_url(preference: dict) -> str | None:
    if _using_sandbox():
        return preference.get("sandbox_init_point") or preference.get("init_point")
    return preference.get("init_point") or preference.get("sandbox_init_point")


def _public_base_url() -> str:
    base_url = (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        return ""
    local_hosts = ("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")
    if base_url.startswith(local_hosts):
        return ""
    return base_url


def _request(method: str, path: str, **kwargs) -> dict:
    config_error = _require_config()
    if config_error:
        return config_error
    try:
        response = requests.request(
            method,
            f"{MP_API_BASE}{path}",
            headers=_headers(),
            timeout=25,
            **kwargs,
        )
        data = response.json() if response.content else {}
    except requests.RequestException as exc:
        return {"erro": f"Falha de conexao Mercado Pago: {exc}"}
    except ValueError:
        return {"erro": "Mercado Pago retornou resposta invalida."}

    if response.status_code >= 400:
        message = data.get("message") or data.get("error") or response.text
        return {"erro": f"Mercado Pago HTTP {response.status_code}: {message}", "payload": data}
    return data


def _product_from_pix_payload(produto: dict) -> dict:
    return {
        "tipo": produto.get("tipo") or ("assinatura" if produto.get("product_type") in ("subscription", "plan") else ("ritual" if produto.get("product_type") == "ritual" else "leitura")),
        "method": "mercado_pago",
        "product_type": produto.get("product_type") or "reading",
        "product_name": produto.get("product_name") or "Creditos Madame do Luar",
        "amount": float(produto.get("amount") or produto.get("valor") or 0),
        "original_amount": float(produto.get("original_amount") or produto.get("amount") or produto.get("valor") or 0),
        "discount_amount": float(produto.get("discount_amount") or 0),
        "coupon_code": produto.get("coupon_code") or "",
        "credits_to_release": int(produto.get("credits_to_release") or 0),
        "plano": produto.get("plano") or "",
        "plan_id": produto.get("plan_id") or "",
        "package_id": produto.get("package_id") or "",
        "ritual_id": produto.get("ritual_id") or "",
    }


def _create_pending_payment(user_id: str, product: dict, produto_key: str = None, expires_at: str = None) -> dict:
    payload = {
        "user_id": user_id,
        "status": "pending",
        "valor": product["amount"],
        "amount": product["amount"],
        "original_amount": product.get("original_amount") or product["amount"],
        "discount_amount": product.get("discount_amount") or 0,
        "coupon_code": product.get("coupon_code") or "",
        "tipo": product["tipo"],
        "product_type": product["product_type"],
        "product_name": product["product_name"],
        "method": product["method"],
        "gateway": "mercado_pago",
        "credits_to_release": product["credits_to_release"],
        "expires_at": expires_at,
        "gateway_payload": {
            "produto": produto_key or product.get("product_type"),
            "plano": product.get("plano") or "",
            "plan_id": product.get("plan_id") or "",
            "package_id": product.get("package_id") or "",
            "ritual_id": product.get("ritual_id") or "",
            "original_amount": product.get("original_amount") or product["amount"],
            "coupon_code": product.get("coupon_code") or "",
            "discount_amount": product.get("discount_amount") or 0,
        },
    }
    payment = db_client.criar_registro("payments", payload)
    if "erro" in payment and any(field in str(payment["erro"]) for field in ("coupon_code", "original_amount", "discount_amount")):
        for field in ("coupon_code", "original_amount", "discount_amount"):
            payload.pop(field, None)
        payment = db_client.criar_registro("payments", payload)
    if "erro" in payment:
        return {"erro": payment["erro"]}
    return payment


def _create_preference(user_id: str, product: dict, payment_id: str, email: str = None) -> dict:
    notification_url = os.getenv("MERCADO_PAGO_NOTIFICATION_URL") or f"{BASE_URL}/api/webhook/mercado-pago"
    payload = {
        "items": [{
            "id": product.get("product_type") or "madame-do-luar",
            "title": product["product_name"],
            "description": product["product_name"],
            "quantity": 1,
            "currency_id": os.getenv("MERCADO_PAGO_CURRENCY", "BRL"),
            "unit_price": float(product["amount"]),
        }],
        "payer": {"email": email} if email else {},
        "external_reference": payment_id,
        "notification_url": notification_url,
        "metadata": {
            "user_id": user_id,
            "payment_id": payment_id,
            "tipo": product["tipo"],
            "plano": product.get("plano") or "",
            "ritual_id": product.get("ritual_id") or "",
            "coupon_code": product.get("coupon_code") or "",
            "discount_amount": product.get("discount_amount") or 0,
            "credits_to_release": product["credits_to_release"],
        },
    }
    public_base_url = _public_base_url()
    if public_base_url:
        payload["back_urls"] = {
            "success": f"{public_base_url}/pagamento/sucesso?payment_id={payment_id}",
            "failure": f"{public_base_url}/pagamento/cancelado?payment_id={payment_id}",
            "pending": f"{public_base_url}/pagamento/sucesso?status=pending&payment_id={payment_id}",
        }
        payload["auto_return"] = "approved"
    return _request("POST", "/checkout/preferences", json=payload)


def criar_sessao_checkout(user_id: str, produto: str, email: str = None) -> dict:
    product = PRODUCTS.get(produto)
    if not product:
        return {"erro": f"Produto Mercado Pago invalido: {produto}"}

    config_error = _require_config()
    if config_error:
        return config_error

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    payment = _create_pending_payment(user_id, product, produto_key=produto, expires_at=expires_at)
    if "erro" in payment:
        return payment

    preference = _create_preference(user_id, product, payment["payment_id"], email=email)
    if "erro" in preference:
        db_client.atualizar_registro("payments", "payment_id", payment["payment_id"], {
            "status": "error",
            "error_message": preference["erro"][:500],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        db_client.registrar_log(
            "PAYMENT_FAILED",
            "Falha ao criar preferencia no Mercado Pago.",
            user_id=user_id,
            metadata={"produto": produto, "erro": preference["erro"]},
            severity="error",
        )
        return {"erro": preference["erro"]}

    checkout_url = _checkout_url(preference)
    preference_id = preference.get("id")
    updated = db_client.atualizar_registro("payments", "payment_id", payment["payment_id"], {
        "gateway_ref": preference_id,
        "transaction_id": preference_id,
        "checkout_url": checkout_url,
        "gateway_payload": preference,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    if "erro" in updated:
        return {"erro": updated["erro"]}

    db_client.registrar_log(
        "PAYMENT_CHECKOUT_CREATED",
        "Checkout Mercado Pago criado e pagamento pendente registrado.",
        user_id=user_id,
        metadata={"preference_id": preference_id, "produto": produto, "payment_id": payment["payment_id"]},
    )
    return {
        "url": checkout_url,
        "session_id": preference_id,
        "payment_id": payment["payment_id"],
        "status": "pending",
        "gateway": "mercado_pago",
    }


def criar_cobranca_pix_gateway(user_id: str, produto: dict, email: str = None, expires_at: str = None) -> dict:
    gateway = os.getenv("PIX_GATEWAY", "mercado_pago").strip().lower()
    expires_at = expires_at or (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    if gateway in {"mercado_pago", "mercadopago", "mp"}:
        product = _product_from_pix_payload(produto)
        if product["amount"] <= 0:
            return {"erro": "Valor do produto invalido para Mercado Pago."}
        payment = _create_pending_payment(user_id, product, expires_at=expires_at)
        if "erro" in payment:
            return payment
        preference = _create_preference(user_id, product, payment["payment_id"], email=email)
        if "erro" in preference:
            db_client.atualizar_registro("payments", "payment_id", payment["payment_id"], {
                "status": "error",
                "error_message": preference["erro"][:500],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            return preference
        checkout_url = _checkout_url(preference)
        preference_id = preference.get("id")
        updated = db_client.atualizar_registro("payments", "payment_id", payment["payment_id"], {
            "gateway_ref": preference_id,
            "transaction_id": preference_id,
            "checkout_url": checkout_url,
            "gateway_payload": preference,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        if "erro" in updated:
            return {"erro": updated["erro"]}
        return {
            "gateway": "mercado_pago",
            "payment_id": payment["payment_id"],
            "transaction_id": preference_id,
            "checkout_url": checkout_url,
            "qr_code_url": None,
            "pix_copy_paste": None,
            "expires_at": expires_at,
            "payload": preference,
        }

    if not _allow_mock_payments():
        db_client.registrar_log(
            "PAYMENT_ERROR",
            "Gateway PIX nao suportado ou mock nao habilitado.",
            user_id=user_id,
            metadata={"gateway": gateway, "allow_mock_payments": False, "app_env": _app_env()},
            severity="error",
        )
        return {
            "erro": (
                f"Gateway PIX '{gateway}' nao esta configurado. "
                "Use PIX_GATEWAY=mercado_pago ou habilite ALLOW_MOCK_PAYMENTS=true apenas em ambiente local."
            )
        }

    transaction_id = "pix_dev_" + os.urandom(12).hex()
    pix_code = f"PIX-MDL-{transaction_id}"
    return {
        "gateway": "mock",
        "transaction_id": transaction_id,
        "checkout_url": None,
        "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={pix_code}",
        "pix_copy_paste": pix_code,
        "expires_at": expires_at,
        "payload": {"provider": "mock", "transaction_id": transaction_id},
    }


def _parse_signature_header(x_signature: str) -> dict:
    parts = {}
    for item in (x_signature or "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    return parts


def _payload_data_id(payload: dict, query_string: bytes = b"") -> str:
    query = parse_qs((query_string or b"").decode("utf-8", errors="ignore"))
    for key in ("data.id", "id"):
        if query.get(key):
            return query[key][0]
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    if payload.get("id"):
        return str(payload["id"])
    return ""


def _signature_data_ids(payload: dict, query_string: bytes = b"") -> list[str]:
    query = parse_qs((query_string or b"").decode("utf-8", errors="ignore"))
    candidates = []
    for key in ("data.id", "id"):
        if query.get(key):
            candidates.append(query[key][0])
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        candidates.append(str(data["id"]))
    if payload.get("id"):
        candidates.append(str(payload["id"]))
    seen = set()
    expanded = []
    for item in candidates:
        value = str(item)
        expanded.append(value)
        lower_value = value.lower()
        if lower_value != value:
            expanded.append(lower_value)
    return [item for item in expanded if item and not (item in seen or seen.add(item))]


def validar_assinatura_webhook(payload: dict, x_signature: str, x_request_id: str, query_string: bytes = b"") -> bool:
    secret = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET", "").strip()
    if not secret:
        return False
    parts = _parse_signature_header(x_signature)
    ts = parts.get("ts")
    received = parts.get("v1")
    data_ids = _signature_data_ids(payload, query_string)
    if not ts or not received or not data_ids or not x_request_id:
        return False
    for data_id in data_ids:
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, received):
            return True
    print(
        "Mercado Pago webhook signature mismatch",
        {
            "query_string": (query_string or b"").decode("utf-8", errors="ignore"),
            "data_id_candidates": data_ids,
            "has_x_signature": bool(x_signature),
            "has_x_request_id": bool(x_request_id),
            "has_ts": bool(ts),
            "has_v1": bool(received),
        },
    )
    return False


def _fetch_payment(mp_payment_id: str) -> dict:
    return _request("GET", f"/v1/payments/{mp_payment_id}")


def _fetch_merchant_order(order_id: str) -> dict:
    return _request("GET", f"/merchant_orders/{order_id}")


def _payment_id_from_merchant_order(order: dict) -> str:
    payments = order.get("payments")
    if isinstance(payments, list):
        for payment in payments:
            payment_id = payment.get("id") if isinstance(payment, dict) else None
            if payment_id:
                return str(payment_id)
    return ""


def _local_payment_from_merchant_order(order: dict) -> dict | None:
    external_reference = str(order.get("external_reference") or "")
    if external_reference:
        payment = db_client.buscar_por_id("payments", "payment_id", external_reference)
        if payment:
            return payment
    preference_id = str(order.get("preference_id") or "")
    if preference_id:
        return db_client.buscar_pagamento_por_transacao(preference_id)
    return None


def _local_payment_from_mp(mp_payment: dict) -> dict | None:
    external_reference = str(mp_payment.get("external_reference") or "")
    if external_reference:
        payment = db_client.buscar_por_id("payments", "payment_id", external_reference)
        if payment:
            return payment
    preference_id = str((mp_payment.get("order") or {}).get("id") or "")
    if preference_id:
        return db_client.buscar_pagamento_por_transacao(preference_id)
    return None


def _approve_or_update_payment(local_payment: dict, mp_payment: dict, payload: dict) -> dict:
    mp_status = str(mp_payment.get("status") or "").lower()
    status = STATUS_MAP.get(mp_status, "pending")
    webhook_payload = {"mercado_pago_payment": mp_payment, "notification": payload}

    if status == "approved":
        result = db_client.aprovar_pagamento_pix(local_payment["payment_id"], webhook_payload=webhook_payload)
        db_client.atualizar_registro("payments", "payment_id", local_payment["payment_id"], {
            "gateway_ref": str(mp_payment.get("id")),
            "gateway_payload": mp_payment,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        if local_payment.get("tipo") == "assinatura":
            gateway_id = str(mp_payment.get("id"))
            saved_payload = local_payment.get("gateway_payload") or {}
            plano = (
                saved_payload.get("plano")
                or (saved_payload.get("metadata") or {}).get("plano")
                or local_payment.get("product_name")
                or ""
            )
            db_client.atualizar_status_assinatura(local_payment["user_id"], "ativo", plano, gateway_id)
        db_client.registrar_log(
            "PAYMENT_APPROVED",
            "Pagamento Mercado Pago confirmado por webhook.",
            user_id=local_payment.get("user_id"),
            metadata={"payment_id": local_payment["payment_id"], "mp_payment_id": mp_payment.get("id"), "result": result},
        )
        return {"status": "ok", "payment_status": status, "resultado": result}

    updated = db_client.atualizar_registro("payments", "payment_id", local_payment["payment_id"], {
        "status": status,
        "gateway_ref": str(mp_payment.get("id")),
        "webhook_payload": webhook_payload,
        "gateway_payload": mp_payment,
        "error_message": str(mp_payment.get("status_detail") or "")[:500],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    if status in {"failed", "cancelled", "refunded"}:
        db_client.registrar_log(
            "PAYMENT_FAILED",
            "Mercado Pago informou pagamento nao aprovado.",
            user_id=local_payment.get("user_id"),
            metadata={"payment_id": local_payment["payment_id"], "mp_payment_id": mp_payment.get("id"), "status": mp_status},
            severity="warning",
        )
    return {"status": "ok", "payment_status": status, "resultado": {"pagamento": updated}}


def processar_webhook_mercado_pago(payload: dict, x_signature: str, x_request_id: str, query_string: bytes = b"") -> dict:
    secret = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET", "").strip()
    if secret and not validar_assinatura_webhook(payload, x_signature, x_request_id, query_string):
        return {"erro": "Webhook Mercado Pago invalido: assinatura nao confere."}

    event_type = str(payload.get("type") or payload.get("topic") or payload.get("action") or "payment.updated")
    mp_payment_id = _payload_data_id(payload, query_string)
    if not mp_payment_id:
        return {"erro": "Webhook Mercado Pago sem data.id do pagamento."}

    event_id = f"mercado_pago:{event_type}:{mp_payment_id}:{x_request_id or 'sem-request-id'}"
    if event_type in {"merchant_order", "merchant_order.updated"}:
        order = _fetch_merchant_order(mp_payment_id)
        if "erro" in order:
            return order
        local_payment = _local_payment_from_merchant_order(order)
        evento = db_client.registrar_webhook_pagamento(
            event_id=event_id,
            payload=payload,
            gateway="mercado_pago",
            event_type=event_type,
            transaction_id=str(mp_payment_id),
            payment_id=local_payment.get("payment_id") if local_payment else None,
        )
        if isinstance(evento, dict) and evento.get("duplicado"):
            return {"status": "ignored", "reason": "duplicate_webhook", "event_id": event_id}
        resolved_payment_id = _payment_id_from_merchant_order(order)
        if not resolved_payment_id:
            return {
                "status": "ignored",
                "reason": "merchant_order_without_payment",
                "event_id": event_id,
            }
        mp_payment = _fetch_payment(resolved_payment_id)
        if "erro" in mp_payment:
            return mp_payment
        local_payment = local_payment or _local_payment_from_mp(mp_payment)
        if not local_payment:
            db_client.registrar_log(
                "WEBHOOK_IGNORED",
                "Webhook Mercado Pago merchant_order sem pagamento local correspondente.",
                metadata={"merchant_order_id": mp_payment_id, "payload": payload, "order": order},
                severity="warning",
            )
            return {"status": "ignored", "reason": "payment_not_found", "event_id": event_id}
        result = _approve_or_update_payment(local_payment, mp_payment, payload)
        db_client.atualizar_registro("payment_webhook_events", "event_id", event_id, {
            "processed": True,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        })
        result["event_id"] = event_id
        result["merchant_order_id"] = mp_payment_id
        return result

    mp_payment = _fetch_payment(mp_payment_id)
    if "erro" in mp_payment:
        return mp_payment

    local_payment = _local_payment_from_mp(mp_payment)
    evento = db_client.registrar_webhook_pagamento(
        event_id=event_id,
        payload=payload,
        gateway="mercado_pago",
        event_type=event_type,
        transaction_id=str(mp_payment_id),
        payment_id=local_payment.get("payment_id") if local_payment else None,
    )
    if isinstance(evento, dict) and evento.get("duplicado"):
        return {"status": "ignored", "reason": "duplicate_webhook", "event_id": event_id}
    if not local_payment:
        db_client.registrar_log(
            "WEBHOOK_IGNORED",
            "Webhook Mercado Pago sem pagamento local correspondente.",
            metadata={"mp_payment_id": mp_payment_id, "payload": payload},
            severity="warning",
        )
        return {"status": "ignored", "reason": "payment_not_found", "event_id": event_id}

    result = _approve_or_update_payment(local_payment, mp_payment, payload)
    db_client.atualizar_registro("payment_webhook_events", "event_id", event_id, {
        "processed": True,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    result["event_id"] = event_id
    return result


def cancelar_assinatura(user_id: str) -> dict:
    url, headers = db_client.get_supabase_headers()
    response = requests.get(
        f"{url}/rest/v1/subscriptions?user_id=eq.{user_id}&status=eq.ativo&select=*&limit=1",
        headers=headers,
        timeout=15,
    )
    subscriptions = response.json()
    if not subscriptions:
        return {"erro": "Nenhuma assinatura ativa encontrada para este usuario."}

    gateway_id = subscriptions[0].get("gateway_id")
    db_client.atualizar_status_assinatura(user_id, "cancelado", subscriptions[0].get("plano") or "", gateway_id)
    db_client.registrar_log(
        "SUBSCRIPTION_CANCELLED",
        "Assinatura Mercado Pago cancelada localmente.",
        user_id=user_id,
        metadata={"gateway_id": gateway_id},
        severity="warning",
    )
    return {"status": "cancelado", "gateway_id": gateway_id, "gateway": "mercado_pago"}


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  MERCADO PAGO - TESTE DE CONFIGURACAO")
    print("=" * 55)
    if not _access_token():
        print("\n  MERCADO_PAGO_ACCESS_TOKEN nao configurado no .env")
    else:
        account = _request("GET", "/users/me")
        if "erro" in account:
            print(f"\n  Erro ao conectar: {account['erro']}")
        else:
            print("\n  Mercado Pago conectado.")
            print(f"  Conta: {account.get('email') or account.get('nickname') or account.get('id')}")
            print(f"  Pais:  {account.get('site_id') or 'desconhecido'}")
    print("\n" + "=" * 55 + "\n")
