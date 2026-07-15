import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.context import request_context
from app.core.errors import erro_http
from app.core.security import usuario_atual
from app.modules.analytics.use_cases import track_server_event
from services import PaymentService
from tools.flow_pagamento import cancelar_assinatura, criar_cobranca_pix_gateway, criar_sessao_checkout

from .repository import PaymentsRepository
from .schemas import CheckoutRequest, PixCreateRequest, SubscriptionCancelRequest
from .service import montar_status_pagamento


router = APIRouter(tags=["payments"])
payment_service = PaymentService()
repository = PaymentsRepository()


@router.post("/payments/pix/create")
@router.post("/api/payments/pix/create")
async def criar_pagamento_pix(body: PixCreateRequest, request: Request, usuario: dict = Depends(usuario_atual)):
    if body.product_type == "ritual":
        raise HTTPException(status_code=400, detail="Rituais agora sao comprados com creditos. Use /api/rituals/{ritual_id}/purchase.")
    produto = payment_service.calcular_produto_pix(body.product_type, body.product_id)
    produto = repository.apply_coupon(produto, body.coupon_code)
    if "erro" in produto:
        if body.coupon_code:
            track_server_event("coupon_failed", user_id=usuario["user_id"], metadata={"coupon_code": body.coupon_code, "product_type": body.product_type, "product_id": body.product_id, "erro": produto["erro"]})
        raise HTTPException(status_code=400, detail=produto["erro"])
    if body.coupon_code and produto.get("coupon_code"):
        track_server_event("coupon_applied", user_id=usuario["user_id"], metadata={"coupon_code": produto.get("coupon_code"), "product_type": produto.get("product_type"), "product_id": body.product_id, "discount_amount": produto.get("discount_amount") or 0})

    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("PIX_EXPIRATION_MINUTES", "30")))).isoformat()
    cobranca = criar_cobranca_pix_gateway(user_id=usuario["user_id"], produto=produto, email=usuario.get("email"), expires_at=expires_at)

    if "erro" in cobranca:
        falha = repository.create_payment({
            "user_id": usuario["user_id"],
            "plan_id": produto.get("plan_id"),
            "package_id": produto.get("package_id"),
            "product_type": produto.get("product_type"),
            "product_name": produto.get("product_name"),
            "valor": produto.get("amount"),
            "amount": produto.get("amount"),
            "status": "error",
            "tipo": "assinatura" if produto.get("product_type") == "plan" else "leitura",
            "method": "PIX",
            "gateway": os.getenv("PIX_GATEWAY", "mercado_pago"),
            "error_message": cobranca["erro"],
            "expires_at": expires_at,
            "credits_to_release": produto.get("credits_to_release", 0),
        })
        track_server_event("payment_failed", user_id=usuario["user_id"], entity_type="payments", entity_id=falha.get("payment_id"), metadata={"produto": produto, "erro": cobranca["erro"], "method": "PIX"})
        repository.log("API_ERROR", "Falha ao gerar cobranca PIX.", user_id=usuario["user_id"], metadata={"produto": produto, "erro": cobranca["erro"], "payment": falha}, severity="error")
        raise HTTPException(status_code=502, detail=cobranca["erro"])

    pagamento = payment_service.registrar_pix(usuario["user_id"], produto, cobranca, expires_at)
    ctx = request_context(request)
    repository.log("PIX_CREATED", "Cobranca PIX criada.", user_id=usuario["user_id"], metadata={"payment_id": pagamento.get("payment_id"), "transaction_id": pagamento.get("transaction_id")}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    track_server_event("checkout_started", user_id=usuario["user_id"], entity_type="payments", entity_id=pagamento.get("payment_id"), metadata={"product_type": produto.get("product_type"), "amount": produto.get("amount"), "method": "PIX"})
    track_server_event("checkout_pix_generated", user_id=usuario["user_id"], entity_type="payments", entity_id=pagamento.get("payment_id"), metadata={"transaction_id": pagamento.get("transaction_id"), "expires_at": pagamento.get("expires_at")})
    return {
        "payment_id": pagamento.get("payment_id"),
        "status": pagamento.get("status"),
        "gateway": pagamento.get("gateway"),
        "transaction_id": pagamento.get("transaction_id"),
        "qr_code_url": pagamento.get("qr_code_url"),
        "pix_copy_paste": pagamento.get("pix_copy_paste"),
        "checkout_url": pagamento.get("checkout_url"),
        "expires_at": pagamento.get("expires_at"),
        "credits_to_release": pagamento.get("credits_to_release"),
        "amount": pagamento.get("amount") or pagamento.get("valor"),
    }


@router.get("/payments/{payment_id}")
@router.get("/api/payments/{payment_id}")
async def consultar_pagamento(payment_id: str, usuario: dict = Depends(usuario_atual)):
    pagamento = repository.get_payment(payment_id)
    if not pagamento or pagamento.get("user_id") != usuario.get("user_id"):
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    return {"pagamento": pagamento}


@router.post("/api/checkout")
async def criar_checkout(req: CheckoutRequest, request: Request, usuario: dict = Depends(usuario_atual)):
    try:
        track_server_event("checkout_started", user_id=usuario["user_id"], metadata={"plano": req.plano, "method": "checkout"})
        resultado = criar_sessao_checkout(usuario["user_id"], req.plano, usuario.get("email"))
        if "erro" in resultado:
            track_server_event("payment_failed", user_id=usuario["user_id"], metadata={"plano": req.plano, "erro": resultado["erro"]})
            raise HTTPException(status_code=400, detail=resultado["erro"])
        return {"url": resultado["url"], "session_id": resultado.get("session_id"), "payment_id": resultado.get("payment_id"), "status": resultado.get("status", "pending")}
    except HTTPException:
        raise
    except Exception as exc:
        request_id = str(uuid.uuid4())
        ctx = request_context(request)
        repository.log("PAYMENT_ERROR", "Falha inesperada ao criar checkout.", user_id=usuario.get("user_id"), metadata={"request_id": request_id, "produto": req.plano, "erro": str(exc)[:500]}, severity="error", ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
        track_server_event("payment_failed", user_id=usuario.get("user_id"), metadata={"request_id": request_id, "plano": req.plano, "erro": str(exc)[:500]})
        raise erro_http(502, "PAYMENT_CHECKOUT_FAILED", "Nao foi possivel iniciar o checkout agora. Tente novamente em instantes.", {"request_id": request_id})


@router.get("/api/payments/{payment_id}/status")
async def status_pagamento_usuario(payment_id: str, usuario: dict = Depends(usuario_atual)):
    payment = repository.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    if payment.get("user_id") != usuario.get("user_id") and usuario.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Pagamento pertence a outro usuario.")
    usuario_atualizado = repository.get_user(payment.get("user_id")) or usuario
    return montar_status_pagamento(payment, usuario_atualizado)


@router.post("/api/subscription/cancel")
async def cancelar_assinatura_usuario(body: SubscriptionCancelRequest, request: Request, usuario: dict = Depends(usuario_atual)):
    resultado = cancelar_assinatura(usuario["user_id"])
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    ctx = request_context(request)
    repository.log("SUBSCRIPTION_CANCEL_REQUESTED", "Usuario solicitou cancelamento de assinatura.", user_id=usuario.get("user_id"), metadata={"reason": body.reason, "result": resultado}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"], severity="warning")
    track_server_event("subscription_cancel_requested", user_id=usuario.get("user_id"), metadata={"reason": body.reason})
    track_server_event("subscription_cancelled", user_id=usuario.get("user_id"), metadata={"reason": body.reason, "result": resultado})
    return resultado
