import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from app.modules.analytics.use_cases import track_server_event
from tools.flow_pagamento import processar_webhook_mercado_pago

from .repository import WebhooksRepository
from .service import normalize_webhook_status, pix_event_id, pix_gateway


router = APIRouter(tags=["webhooks"])
repository = WebhooksRepository()


@router.post("/webhooks/pix")
@router.post("/api/webhooks/pix")
async def webhook_pix(request: Request, x_pix_webhook_secret: Optional[str] = Header(None)):
    expected_secret = os.getenv("PIX_WEBHOOK_SECRET")
    if expected_secret and x_pix_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Webhook PIX nao autorizado.")

    payload = await request.json()
    status, event_type, parsed_transaction_id = normalize_webhook_status(payload)
    transaction_id = payload.get("transaction_id") or parsed_transaction_id or payload.get("id") or payload.get("payment_id")
    event_id = pix_event_id(transaction_id, event_type, status, payload)
    gateway = pix_gateway(payload)
    payment = repository.get_payment_by_transaction(transaction_id) if transaction_id else None

    evento = repository.register_payment_webhook(event_id=event_id, payload=payload, gateway=gateway, event_type=event_type, transaction_id=transaction_id, payment_id=payment.get("payment_id") if payment else None)
    if evento.get("duplicado"):
        return {"status": "ok", "duplicado": True, "event_id": event_id}

    if not payment:
        repository.log("WEBHOOK_FAILED", "Webhook PIX recebido sem pagamento correspondente.", metadata={"event_id": event_id, "transaction_id": transaction_id, "payload": payload}, severity="error")
        return {"status": "ignored", "reason": "payment_not_found", "event_id": event_id}

    if status == "approved":
        resultado = repository.approve_pix_payment(payment["payment_id"], payload)
        track_server_event("payment_approved", user_id=payment.get("user_id"), entity_type="payments", entity_id=payment.get("payment_id"), metadata={"gateway": gateway, "transaction_id": transaction_id, "event_id": event_id})
        if payment.get("product_type") == "plan" or payment.get("tipo") == "assinatura":
            track_server_event("subscription_started", user_id=payment.get("user_id"), entity_type="payments", entity_id=payment.get("payment_id"), metadata={"gateway": gateway, "transaction_id": transaction_id, "event_id": event_id, "product_name": payment.get("product_name")})
    else:
        update = {"status": status, "webhook_payload": payload, "updated_at": datetime.now(timezone.utc).isoformat()}
        if status in ("error", "failed", "refused"):
            update["error_message"] = str(payload.get("error") or payload.get("message") or "Falha informada por webhook")[:500]
        resultado = {"pagamento": repository.update_payment(payment["payment_id"], update)}
        event_name = "PIX_EXPIRED" if status == "expired" else "WEBHOOK_RECEIVED"
        repository.log(event_name, f"Webhook PIX atualizou pagamento para {status}.", user_id=payment.get("user_id"), metadata={"payment_id": payment.get("payment_id"), "event_id": event_id, "payload": payload}, severity="warning" if status != "pending" else "info")
        if status in ("expired", "cancelled"):
            track_server_event("payment_abandoned", user_id=payment.get("user_id"), entity_type="payments", entity_id=payment.get("payment_id"), metadata={"gateway": gateway, "status": status, "transaction_id": transaction_id, "event_id": event_id})
        elif status in ("error", "failed", "refused"):
            track_server_event("payment_failed", user_id=payment.get("user_id"), entity_type="payments", entity_id=payment.get("payment_id"), metadata={"gateway": gateway, "status": status, "transaction_id": transaction_id, "event_id": event_id})

    repository.mark_event_processed(event_id, {"processed": True, "processed_at": datetime.now(timezone.utc).isoformat()})
    return {"status": "ok", "event_id": event_id, "payment_status": status, "resultado": resultado}


@router.post("/api/webhook/stripe")
async def webhook_stripe(request: Request, stripe_signature: str = Header(None)):
    raise HTTPException(status_code=410, detail="Stripe desativado. Use /api/webhook/mercado-pago.")


@router.post("/api/webhook/mercado-pago")
async def webhook_mercado_pago(
    request: Request,
    x_signature: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None),
):
    if not os.getenv("MERCADO_PAGO_ACCESS_TOKEN"):
        raise HTTPException(status_code=501, detail="Mercado Pago nao configurado.")
    payload = await request.body()
    try:
        body = json.loads(payload.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    resultado = processar_webhook_mercado_pago(body, x_signature or "", x_request_id or "", request.scope.get("query_string", b""))
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    return resultado
