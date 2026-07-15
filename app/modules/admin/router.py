import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests as http
from fastapi import APIRouter, Depends, Header, HTTPException, Request

import automation_engine
import db_client
from app.core.context import clean_payload, request_context
from app.core.security import admin_atual
from app.modules.analytics.use_cases import analytics_summary, track_server_event
from app.modules.automation.job_queue import job_queue_service
from app.modules.rituals.service import custo_creditos_ritual
from app.modules.webhooks.service import normalize_webhook_status

from .schemas import (
    AdminAlertStatusRequest,
    AdminCampaignRequest,
    AdminCampaignUpdateRequest,
    AdminCouponRequest,
    AdminCouponUpdateRequest,
    AdminCreditPackageRequest,
    AdminCreditPackageUpdateRequest,
    AdminCreditRequest,
    AdminJobProcessRequest,
    AdminJobRetryRequest,
    AdminMaintenanceRequest,
    AdminManualPaymentRequest,
    AdminMessageResendRequest,
    AdminPaymentReprocessRequest,
    AdminPlanRequest,
    AdminPlanUpdateRequest,
    AdminPromptRequest,
    AdminPromptUpdateRequest,
    AdminQueueRequest,
    AdminRitualRequest,
    AdminRitualUpdateRequest,
    AdminSettingsUpdateRequest,
    AdminUserPlanRequest,
    AdminUserStatusRequest,
)
from .service import (
    buscar_assinatura_ativa,
    enriquecer_leituras_admin,
    validar_applies_to,
    validar_coupon,
    validar_status_ativo,
)
from .security import audit_sensitive_view, mask_user, require_permission, require_sensitive_admin_action


router = APIRouter(tags=["admin"])
logger = logging.getLogger("madame_do_luar.api.admin")
# Endpoints Admin - base operacional
# ---------------------------------------------------------------------------

@router.get("/admin/dashboard")
@router.get("/api/admin/dashboard")
async def admin_dashboard(admin: dict = Depends(require_permission("admin.dashboard"))):
    """Resumo inicial para o painel administrativo."""
    def listar_seguro(tabela: str, **kwargs):
        try:
            return db_client.listar_registros(tabela, timeout=5, **kwargs)
        except Exception as exc:
            logger.warning("Falha ao carregar bloco %s do dashboard admin: %s", tabela, exc)
            return []

    metricas, logs, pagamentos_pendentes, leituras_recentes, mensagens_recentes = await asyncio.gather(
        asyncio.to_thread(db_client.resumo_admin),
        asyncio.to_thread(listar_seguro, "system_logs", select="*", limit=10, order="created_at.desc"),
        asyncio.to_thread(listar_seguro, "payments", select="*", filtros="status=eq.pending", limit=10, order="created_at.desc"),
        asyncio.to_thread(listar_seguro, "readings", select="*", limit=10, order="criado_em.desc"),
        asyncio.to_thread(listar_seguro, "message_events", select="*", limit=10, order="created_at.desc"),
    )
    recentes = {
        "logs": logs,
        "pagamentos_pendentes": pagamentos_pendentes,
        "leituras_recentes": leituras_recentes,
        "mensagens_recentes": mensagens_recentes,
    }
    return {"metricas": metricas, "recentes": recentes}


@router.get("/admin/users")
@router.get("/api/admin/users")
async def admin_users(
    request: Request,
    admin: dict = Depends(require_permission("admin.users.read")),
    limit: int = 50,
    status: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    reveal: bool = False,
):
    filtros = []
    if status:
        filtros.append(f"status=eq.{status}")
    if role:
        filtros.append(f"role=eq.{role}")
    usuarios = db_client.listar_registros(
        "users",
        select="user_id,nome,email,whatsapp,criado_em,assinante,plan_id,role,status,credits_balance,last_login_at",
        filtros="&".join(filtros),
        limit=min(max(limit, 1), 200),
        order="criado_em.desc",
    )
    if search:
        needle = search.lower()
        usuarios = [u for u in usuarios if needle in str(u.get("nome") or "").lower() or needle in str(u.get("email") or "").lower() or needle in str(u.get("whatsapp") or "").lower()]
    if reveal:
        audit_sensitive_view(request, admin, "ADMIN_SENSITIVE_USERS_VIEWED", "users", metadata={"limit": limit, "status": status, "role": role, "search": bool(search)})
    return {"usuarios": [mask_user(usuario, reveal=reveal) for usuario in usuarios], "masked": not reveal}


@router.get("/admin/users/{user_id}")
@router.get("/api/admin/users/{user_id}")
async def admin_user_detail(user_id: str, request: Request, admin: dict = Depends(require_permission("admin.users.read")), reveal: bool = False):
    usuario = db_client.get_user_by_id(user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    audit_sensitive_view(request, admin, "ADMIN_USER_DETAIL_VIEWED", "users", entity_id=user_id, metadata={"reveal": reveal})
    return {
        "usuario": mask_user(usuario, reveal=reveal),
        "assinatura": buscar_assinatura_ativa(user_id),
        "leituras": db_client.listar_registros(
            "questions",
            select="*",
            filtros=f"user_id=eq.{user_id}",
            limit=50,
            order="criado_em.desc",
        ),
        "pagamentos": db_client.listar_registros(
            "payments",
            select="*",
            filtros=f"user_id=eq.{user_id}",
            limit=50,
            order="created_at.desc",
        ),
        "creditos": db_client.listar_registros(
            "credit_transactions",
            select="*",
            filtros=f"user_id=eq.{user_id}",
            limit=50,
            order="created_at.desc",
        ),
        "logs": db_client.listar_registros(
            "system_logs",
            select="*",
            filtros=f"user_id=eq.{user_id}",
            limit=50,
            order="created_at.desc",
        ),
    }


@router.patch("/admin/users/{user_id}/status")
@router.patch("/api/admin/users/{user_id}/status")
async def admin_update_user_status(
    user_id: str,
    body: AdminUserStatusRequest,
    request: Request,
    admin: dict = Depends(require_permission("admin.users.write")),
):
    if body.status not in ("ativo", "bloqueado", "inativo"):
        raise HTTPException(status_code=400, detail="Status invalido.")
    before_user = db_client.get_user_by_id(user_id)

    url, headers = db_client.get_supabase_headers()
    patch_headers = dict(headers)
    patch_headers["Prefer"] = "return=representation"
    r = http.patch(
        f"{url}/rest/v1/users?user_id=eq.{user_id}",
        headers=patch_headers,
        json={"status": body.status},
        timeout=10,
    )
    data = r.json() if r.text else []
    if not isinstance(data, list) or not data:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado ou migration pendente.")

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        f"Status do usuario alterado para {body.status}.",
        user_id=user_id,
        admin_id=admin.get("user_id"),
        metadata={"status": body.status},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    usuario = data[0]
    db_client.registrar_auditoria(
        "ADMIN_USER_STATUS_CHANGED",
        entity_type="users",
        entity_id=user_id,
        user_id=user_id,
        admin_id=admin.get("user_id"),
        before_data={"status": (before_user or {}).get("status")},
        after_data={"status": body.status},
        metadata={"reason": body.reason},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    usuario.pop("senha_hash", None)
    return {"usuario": usuario}


@router.post("/admin/users/{user_id}/credits")
@router.post("/api/admin/users/{user_id}/credits")
async def admin_update_user_credits(
    user_id: str,
    body: AdminCreditRequest,
    request: Request,
    admin: dict = Depends(require_permission("admin.billing.write")),
):
    resultado = db_client.ajustar_creditos(
        user_id=user_id,
        amount=body.amount,
        tipo=body.type,
        reason=body.reason,
        admin_id=admin.get("user_id"),
        related_payment_id=body.related_payment_id,
        related_reading_id=body.related_reading_id,
        expires_at=body.expires_at,
    )
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin alterou creditos de usuario.",
        user_id=user_id,
        admin_id=admin.get("user_id"),
        metadata={"type": body.type, "amount": body.amount, "reason": body.reason},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    db_client.registrar_auditoria(
        "ADMIN_USER_CREDITS_CHANGED",
        entity_type="credit_transactions",
        entity_id=resultado.get("transaction_id"),
        user_id=user_id,
        admin_id=admin.get("user_id"),
        after_data={"type": body.type, "amount": body.amount, "reason": body.reason},
        metadata={"related_payment_id": body.related_payment_id, "related_reading_id": body.related_reading_id},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return resultado


@router.patch("/api/admin/users/{user_id}/plan")
async def admin_update_user_plan(
    user_id: str,
    body: AdminUserPlanRequest,
    request: Request,
    admin: dict = Depends(require_permission("admin.billing.write")),
):
    if body.plan_id:
        plano = db_client.listar_registros("plans", select="plan_id", filtros=f"plan_id=eq.{body.plan_id}", limit=1)
        if not plano:
            raise HTTPException(status_code=404, detail="Plano nao encontrado.")

    resultado = db_client.registrar_mudanca_plano(
        user_id=user_id,
        new_plan_id=body.plan_id,
        admin_id=admin.get("user_id"),
        reason=body.reason,
    )
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin alterou plano de usuario.",
        user_id=user_id,
        admin_id=admin.get("user_id"),
        metadata={"plan_id": body.plan_id, "reason": body.reason},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return resultado


@router.get("/admin/plans")
@router.get("/api/admin/plans")
async def admin_list_plans(admin: dict = Depends(admin_atual), limit: int = 100):
    return {
        "plans": db_client.listar_registros(
            "plans",
            select="*",
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.post("/admin/plans")
@router.post("/api/admin/plans")
async def admin_create_plan(body: AdminPlanRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    if body.credits < 0 or body.price < 0:
        raise HTTPException(status_code=400, detail="Preco e creditos nao podem ser negativos.")

    payload = clean_payload(body)
    plano = db_client.criar_registro("plans", payload)
    if "erro" in plano:
        raise HTTPException(status_code=400, detail=plano["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Plano criado.",
        admin_id=admin.get("user_id"),
        metadata={"plan": plano},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"plan": plano}


@router.patch("/admin/plans/{plan_id}")
@router.patch("/api/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: str, body: AdminPlanUpdateRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    if body.credits is not None and body.credits < 0:
        raise HTTPException(status_code=400, detail="Creditos nao podem ser negativos.")
    if body.price is not None and body.price < 0:
        raise HTTPException(status_code=400, detail="Preco nao pode ser negativo.")

    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    plano = db_client.atualizar_registro("plans", "plan_id", plan_id, payload)
    if "erro" in plano:
        raise HTTPException(status_code=400, detail=plano["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Plano atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"plan_id": plan_id, "changes": payload},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"plan": plano}


@router.delete("/admin/plans/{plan_id}")
@router.delete("/api/admin/plans/{plan_id}")
async def admin_deactivate_plan(plan_id: str, request: Request, admin: dict = Depends(admin_atual)):
    plano = db_client.atualizar_registro(
        "plans",
        "plan_id",
        plan_id,
        {"status": "inactive", "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    if "erro" in plano:
        raise HTTPException(status_code=400, detail=plano["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Plano desativado.",
        admin_id=admin.get("user_id"),
        metadata={"plan_id": plan_id},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"plan": plano}


@router.get("/admin/credit-packages")
@router.get("/api/admin/credit-packages")
async def admin_list_credit_packages(admin: dict = Depends(admin_atual), limit: int = 100):
    return {
        "packages": db_client.listar_registros(
            "credit_packages",
            select="*",
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.post("/admin/credit-packages")
@router.post("/api/admin/credit-packages")
async def admin_create_credit_package(body: AdminCreditPackageRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    if body.credits <= 0 or body.price < 0 or body.bonus_credits < 0:
        raise HTTPException(status_code=400, detail="Pacote de creditos invalido.")

    pacote = db_client.criar_registro("credit_packages", clean_payload(body))
    if "erro" in pacote:
        raise HTTPException(status_code=400, detail=pacote["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Pacote de creditos criado.",
        admin_id=admin.get("user_id"),
        metadata={"package": pacote},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"package": pacote}


@router.patch("/admin/credit-packages/{package_id}")
@router.patch("/api/admin/credit-packages/{package_id}")
async def admin_update_credit_package(package_id: str, body: AdminCreditPackageUpdateRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    if body.credits is not None and body.credits <= 0:
        raise HTTPException(status_code=400, detail="Creditos do pacote devem ser maiores que zero.")
    if body.price is not None and body.price < 0:
        raise HTTPException(status_code=400, detail="Preco nao pode ser negativo.")
    if body.bonus_credits is not None and body.bonus_credits < 0:
        raise HTTPException(status_code=400, detail="Bonus nao pode ser negativo.")

    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    pacote = db_client.atualizar_registro("credit_packages", "package_id", package_id, payload)
    if "erro" in pacote:
        raise HTTPException(status_code=400, detail=pacote["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Pacote de creditos atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"package_id": package_id, "changes": payload},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"package": pacote}


@router.delete("/admin/credit-packages/{package_id}")
@router.delete("/api/admin/credit-packages/{package_id}")
async def admin_deactivate_credit_package(package_id: str, request: Request, admin: dict = Depends(admin_atual)):
    pacote = db_client.atualizar_registro(
        "credit_packages",
        "package_id",
        package_id,
        {"status": "inactive", "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    if "erro" in pacote:
        raise HTTPException(status_code=400, detail=pacote["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Pacote de creditos desativado.",
        admin_id=admin.get("user_id"),
        metadata={"package_id": package_id},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"package": pacote}


@router.get("/admin/coupons")
@router.get("/api/admin/coupons")
async def admin_list_coupons(admin: dict = Depends(admin_atual), limit: int = 100):
    return {
        "coupons": db_client.listar_registros(
            "coupons",
            select="*",
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.post("/admin/coupons")
@router.post("/api/admin/coupons")
async def admin_create_coupon(body: AdminCouponRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    validar_coupon(body.discount_type, body.discount_value)
    validar_applies_to(body.applies_to)
    payload = clean_payload(body)
    payload["code"] = db_client.normalizar_codigo_cupom(body.code)
    cupom = db_client.criar_registro("coupons", payload)
    if "erro" in cupom and any(field in str(cupom["erro"]) for field in ("applies_to", "event_type")):
        legacy_payload = {k: v for k, v in payload.items() if k not in ("applies_to", "event_type")}
        cupom = db_client.criar_registro("coupons", legacy_payload)
    if "erro" in cupom:
        raise HTTPException(status_code=400, detail=cupom["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Cupom criado.",
        admin_id=admin.get("user_id"),
        metadata={"coupon": cupom},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"coupon": cupom}


@router.patch("/admin/coupons/{coupon_id}")
@router.patch("/api/admin/coupons/{coupon_id}")
async def admin_update_coupon(coupon_id: str, body: AdminCouponUpdateRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    validar_coupon(body.discount_type, body.discount_value)
    validar_applies_to(body.applies_to)
    payload = clean_payload(body)
    if "code" in payload:
        payload["code"] = db_client.normalizar_codigo_cupom(payload["code"])
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    cupom = db_client.atualizar_registro("coupons", "coupon_id", coupon_id, payload)
    if "erro" in cupom:
        raise HTTPException(status_code=400, detail=cupom["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Cupom atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"coupon_id": coupon_id, "changes": payload},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"coupon": cupom}


@router.delete("/admin/coupons/{coupon_id}")
@router.delete("/api/admin/coupons/{coupon_id}")
async def admin_deactivate_coupon(coupon_id: str, request: Request, admin: dict = Depends(admin_atual)):
    cupom = db_client.atualizar_registro(
        "coupons",
        "coupon_id",
        coupon_id,
        {"status": "inactive", "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    if "erro" in cupom:
        raise HTTPException(status_code=400, detail=cupom["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Cupom desativado.",
        admin_id=admin.get("user_id"),
        metadata={"coupon_id": coupon_id},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"coupon": cupom}


@router.get("/admin/readings")
@router.get("/api/admin/readings")
async def admin_readings(admin: dict = Depends(admin_atual), limit: int = 50):
    leituras = db_client.listar_registros(
        "readings",
        select="*",
        limit=min(max(limit, 1), 200),
        order="criado_em.desc",
    )
    return {
        "leituras": enriquecer_leituras_admin(leituras)
    }


@router.get("/admin/payments")
@router.get("/api/admin/payments")
async def admin_payments(
    admin: dict = Depends(require_permission("admin.billing.read")),
    limit: int = 50,
    status: Optional[str] = None,
    product_type: Optional[str] = None,
    gateway: Optional[str] = None,
    user_id: Optional[str] = None,
):
    filtros = []
    if status:
        filtros.append(f"status=eq.{status}")
    if product_type:
        filtros.append(f"product_type=eq.{product_type}")
    if gateway:
        filtros.append(f"gateway=eq.{gateway}")
    if user_id:
        filtros.append(f"user_id=eq.{user_id}")
    return {
        "pagamentos": db_client.listar_registros(
            "payments",
            select="*",
            filtros="&".join(filtros),
            limit=min(max(limit, 1), 200),
            order="created_at.desc",
        )
    }


@router.get("/admin/messages")
@router.get("/api/admin/messages")
async def admin_messages(
    admin: dict = Depends(admin_atual),
    limit: int = 100,
    status: Optional[str] = None,
    canal: Optional[str] = None,
    tipo: Optional[str] = None,
    user_id: Optional[str] = None,
):
    filtros = []
    if status:
        filtros.append(f"status=eq.{status}")
    if canal:
        filtros.append(f"canal=eq.{canal}")
    if tipo:
        filtros.append(f"tipo=eq.{tipo}")
    if user_id:
        filtros.append(f"user_id=eq.{user_id}")
    eventos = db_client.listar_registros(
        "message_events",
        select="*",
        filtros="&".join(filtros),
        limit=min(max(limit, 1), 300),
        order="created_at.desc",
    )
    logs = db_client.listar_registros(
        "notification_logs",
        select="*",
        limit=min(max(limit, 1), 300),
        order="created_at.desc",
    )
    return {"eventos": eventos, "logs": logs}


@router.post("/admin/messages/{message_id}/resend")
@router.post("/api/admin/messages/{message_id}/resend")
async def admin_resend_message(
    message_id: str,
    body: AdminMessageResendRequest,
    request: Request,
    admin: dict = Depends(admin_atual),
):
    evento = db_client.buscar_por_id("message_events", "message_id", message_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Mensagem nao encontrada.")
    payload = {
        "status": "pending",
        "agendado_para": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
    }
    if body.message:
        payload["mensagem"] = body.message
    evento = db_client.atualizar_registro("message_events", "message_id", message_id, payload)
    if "erro" in evento:
        raise HTTPException(status_code=400, detail=evento["erro"])

    resultado = automation_engine.processar_evento(evento)
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin reenviou mensagem manualmente.",
        user_id=evento.get("user_id"),
        admin_id=admin.get("user_id"),
        metadata={"message_id": message_id, "resultado": resultado},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"evento": db_client.buscar_por_id("message_events", "message_id", message_id), "resultado": resultado}


@router.get("/admin/rituals")
@router.get("/api/admin/rituals")
async def admin_rituals(admin: dict = Depends(admin_atual), limit: int = 100):
    rituais = db_client.listar_registros(
        "rituals",
        select="*",
        limit=min(max(limit, 1), 300),
    )
    compras = db_client.listar_registros(
        "ritual_purchases",
        select="*",
        limit=min(max(limit, 1), 300),
        order="data.desc",
    )
    ritual_map = {r.get("ritual_id"): r for r in rituais if r.get("ritual_id")}
    user_ids = sorted({c.get("user_id") for c in compras if c.get("user_id")})
    usuarios = db_client.listar_registros(
        "users",
        select="user_id,nome,email,whatsapp",
        filtros=f"user_id=in.({','.join(user_ids)})",
        limit=max(len(user_ids), 1),
    ) if user_ids else []
    usuario_map = {u.get("user_id"): u for u in usuarios if u.get("user_id")}
    for ritual in rituais:
        ritual["custo_creditos"] = custo_creditos_ritual({"amount": ritual.get("preco")})
    for compra in compras:
        ritual = ritual_map.get(compra.get("ritual_id")) or {}
        if ritual:
            compra["ritual"] = ritual
            compra["ritual_nome"] = ritual.get("nome")
            compra["creditos"] = compra.get("credits_spent") if compra.get("credits_spent") is not None else custo_creditos_ritual({"amount": ritual.get("preco")})
        usuario = usuario_map.get(compra.get("user_id")) or {}
        if usuario:
            compra["usuario"] = usuario
    return {
        "rituais": rituais,
        "compras": compras,
    }


@router.post("/admin/rituals")
@router.post("/api/admin/rituals")
async def admin_create_ritual(body: AdminRitualRequest, request: Request, admin: dict = Depends(admin_atual)):
    if body.preco < 0:
        raise HTTPException(status_code=400, detail="Custo em creditos do ritual nao pode ser negativo.")
    payload = clean_payload(body)
    payload["preco"] = custo_creditos_ritual({"amount": payload.get("preco")})
    ritual = db_client.criar_registro("rituals", payload)
    if "erro" in ritual:
        raise HTTPException(status_code=400, detail=ritual["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Ritual criado.",
        admin_id=admin.get("user_id"),
        metadata={"ritual_id": ritual.get("ritual_id")},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"ritual": ritual}


@router.patch("/admin/rituals/{ritual_id}")
@router.patch("/api/admin/rituals/{ritual_id}")
async def admin_update_ritual(ritual_id: str, body: AdminRitualUpdateRequest, request: Request, admin: dict = Depends(admin_atual)):
    if body.preco is not None and body.preco < 0:
        raise HTTPException(status_code=400, detail="Custo em creditos do ritual nao pode ser negativo.")
    payload = clean_payload(body)
    if "preco" in payload:
        payload["preco"] = custo_creditos_ritual({"amount": payload.get("preco")})
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    ritual = db_client.atualizar_registro("rituals", "ritual_id", ritual_id, payload)
    if "erro" in ritual:
        raise HTTPException(status_code=400, detail=ritual["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Ritual atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"ritual_id": ritual_id, "changes": payload},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"ritual": ritual}


@router.get("/admin/campaigns")
@router.get("/api/admin/campaigns")
async def admin_campaigns(admin: dict = Depends(admin_atual), limit: int = 100):
    rules = db_client.listar_registros(
        "automation_rules",
        select="*",
        limit=min(max(limit, 1), 300),
        order="created_at.desc",
    )
    steps = db_client.listar_registros(
        "automation_steps",
        select="*",
        limit=500,
        order="step_order.asc",
    )
    return {"campanhas": rules, "etapas": steps}


@router.post("/admin/campaigns")
@router.post("/api/admin/campaigns")
async def admin_create_campaign(body: AdminCampaignRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    if body.channel not in ("email", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canal invalido.")
    if body.delay_minutes < 0:
        raise HTTPException(status_code=400, detail="Delay nao pode ser negativo.")
    rule = db_client.criar_registro("automation_rules", {
        "name": body.name,
        "event_type": body.event_type,
        "status": body.status,
        "audience_filter": {},
    })
    if "erro" in rule:
        raise HTTPException(status_code=400, detail=rule["erro"])
    step = db_client.criar_registro("automation_steps", {
        "rule_id": rule["rule_id"],
        "step_order": 1,
        "delay_minutes": body.delay_minutes,
        "channel": body.channel,
        "subject": body.subject,
        "template": body.template,
        "status": body.status,
    })
    if "erro" in step:
        raise HTTPException(status_code=400, detail=step["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Campanha criada.",
        admin_id=admin.get("user_id"),
        metadata={"rule_id": rule.get("rule_id"), "step_id": step.get("step_id")},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"campanha": rule, "etapa": step}


@router.patch("/admin/campaigns/{rule_id}")
@router.patch("/api/admin/campaigns/{rule_id}")
async def admin_update_campaign(rule_id: str, body: AdminCampaignUpdateRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    rule = db_client.atualizar_registro("automation_rules", "rule_id", rule_id, payload)
    if "erro" in rule:
        raise HTTPException(status_code=400, detail=rule["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Campanha atualizada.",
        admin_id=admin.get("user_id"),
        metadata={"rule_id": rule_id, "changes": payload},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"campanha": rule}


@router.patch("/admin/payments/{payment_id}/manual-approve")
@router.patch("/api/admin/payments/{payment_id}/manual-approve")
async def admin_manual_approve_payment(
    payment_id: str,
    body: AdminManualPaymentRequest,
    request: Request,
    admin: dict = Depends(require_permission("admin.billing.approve")),
    x_admin_confirm_password: Optional[str] = Header(None),
    x_admin_2fa_code: Optional[str] = Header(None),
):
    await require_sensitive_admin_action(
        request,
        admin,
        "admin.billing.approve",
        x_admin_confirm_password=x_admin_confirm_password,
        x_admin_2fa_code=x_admin_2fa_code,
    )
    resultado = db_client.aprovar_pagamento_pix(
        payment_id=payment_id,
        webhook_payload={"manual": True, "reason": body.reason},
        admin_id=admin.get("user_id"),
        manual=True,
    )
    if "erro" in resultado:
        raise HTTPException(status_code=404, detail=resultado["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Pagamento aprovado manualmente.",
        admin_id=admin.get("user_id"),
        metadata={"payment_id": payment_id, "reason": body.reason},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning",
    )
    pagamento = resultado.get("pagamento") if isinstance(resultado, dict) else {}
    track_server_event("admin_payment_manual_approved", user_id=pagamento.get("user_id"), admin_id=admin.get("user_id"), entity_type="payments", entity_id=payment_id, metadata={"reason": body.reason})
    track_server_event("payment_approved", user_id=pagamento.get("user_id"), admin_id=admin.get("user_id"), entity_type="payments", entity_id=payment_id, metadata={"manual": True})
    if pagamento.get("product_type") == "plan" or pagamento.get("tipo") == "assinatura":
        track_server_event("subscription_started", user_id=pagamento.get("user_id"), admin_id=admin.get("user_id"), entity_type="payments", entity_id=payment_id, metadata={"manual": True, "reason": body.reason, "product_name": pagamento.get("product_name")})
    return resultado


@router.post("/admin/payments/{payment_id}/reprocess")
@router.post("/api/admin/payments/{payment_id}/reprocess")
async def admin_reprocess_payment(
    payment_id: str,
    body: AdminPaymentReprocessRequest,
    request: Request,
    admin: dict = Depends(require_permission("admin.billing.write")),
):
    payment = db_client.buscar_por_id("payments", "payment_id", payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")

    payload = body.webhook_payload or payment.get("webhook_payload") or {}
    status, _, _ = normalize_webhook_status(payload) if payload else (payment.get("status"), "manual.reprocess", payment.get("transaction_id"))

    if status == "approved" or payment.get("status") == "approved":
        resultado = db_client.aprovar_pagamento_pix(
            payment_id=payment_id,
            webhook_payload=payload or {"manual_reprocess": True, "reason": body.reason},
            admin_id=admin.get("user_id"),
            manual=True,
        )
    else:
        resultado = {"pagamento": db_client.atualizar_registro("payments", "payment_id", payment_id, {
            "status": status or "pending",
            "webhook_payload": payload,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })}

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin reprocessou pagamento/webhook.",
        user_id=payment.get("user_id"),
        admin_id=admin.get("user_id"),
        metadata={"payment_id": payment_id, "reason": body.reason, "result": resultado},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning",
    )
    return resultado


@router.post("/admin/payments/{payment_id}/resend")
@router.post("/api/admin/payments/{payment_id}/resend")
async def admin_resend_pix_payment(payment_id: str, request: Request, admin: dict = Depends(require_permission("admin.billing.write"))):
    payment = db_client.buscar_por_id("payments", "payment_id", payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    if payment.get("status") == "approved":
        raise HTTPException(status_code=400, detail="Pagamento ja aprovado nao pode ser reenviado.")

    produto = {
        "product_type": payment.get("product_type"),
        "plan_id": payment.get("plan_id"),
        "package_id": payment.get("package_id"),
        "product_name": payment.get("product_name"),
        "amount": float(payment.get("amount") or payment.get("valor") or 0),
        "credits_to_release": int(payment.get("credits_to_release") or 0),
    }
    user = db_client.get_user_by_id(payment.get("user_id"))
    from datetime import timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv("PIX_EXPIRATION_MINUTES", "30")))).isoformat()
    from tools.flow_pagamento import criar_cobranca_pix_gateway
    cobranca = criar_cobranca_pix_gateway(payment.get("user_id"), produto, email=(user or {}).get("email"), expires_at=expires_at)
    if "erro" in cobranca:
        db_client.atualizar_registro("payments", "payment_id", payment_id, {
            "status": "error",
            "error_message": cobranca["erro"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=502, detail=cobranca["erro"])

    atualizado = db_client.atualizar_registro("payments", "payment_id", payment_id, {
        "status": "pending",
        "transaction_id": cobranca["transaction_id"],
        "qr_code_url": cobranca.get("qr_code_url"),
        "pix_copy_paste": cobranca.get("pix_copy_paste"),
        "checkout_url": cobranca.get("checkout_url"),
        "expires_at": cobranca.get("expires_at") or expires_at,
        "gateway": cobranca.get("gateway"),
        "gateway_payload": cobranca.get("payload"),
        "error_message": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin reenviou cobranca PIX.",
        user_id=payment.get("user_id"),
        admin_id=admin.get("user_id"),
        metadata={"payment_id": payment_id, "transaction_id": atualizado.get("transaction_id")},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"pagamento": atualizado}


@router.post("/admin/payments/mark-abandoned")
@router.post("/api/admin/payments/mark-abandoned")
async def admin_mark_abandoned_payments(request: Request, admin: dict = Depends(require_permission("admin.billing.write"))):
    resultado = db_client.marcar_pagamentos_pix_abandonados()
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin executou marcacao de PIX abandonado.",
        admin_id=admin.get("user_id"),
        metadata=resultado,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return resultado


@router.get("/admin/logs")
@router.get("/api/admin/logs")
async def admin_logs(admin: dict = Depends(admin_atual), limit: int = 100):
    return {
        "logs": db_client.listar_registros(
            "system_logs",
            select="*",
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.get("/admin/audit")
@router.get("/api/admin/audit")
async def admin_audit_logs(
    admin: dict = Depends(admin_atual),
    limit: int = 100,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    user_id: Optional[str] = None,
    severity: Optional[str] = None,
):
    filtros = []
    if action:
        filtros.append(f"action=eq.{action}")
    if entity_type:
        filtros.append(f"entity_type=eq.{entity_type}")
    if user_id:
        filtros.append(f"user_id=eq.{user_id}")
    if severity:
        filtros.append(f"severity=eq.{severity}")
    return {
        "audit_logs": db_client.listar_registros(
            "audit_logs",
            select="*",
            filtros="&".join(filtros),
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.get("/admin/errors")
@router.get("/api/admin/errors")
async def admin_errors(admin: dict = Depends(require_permission("admin.logs")), limit: int = 100, event_type: Optional[str] = None, severity: Optional[str] = None):
    filtros = [f"severity=eq.{severity}" if severity else "severity=in.(error,critical)"]
    if event_type:
        filtros.append(f"event_type=eq.{event_type}")
    return {
        "falhas": db_client.listar_registros(
            "system_logs",
            select="*",
            filtros="&".join(filtros),
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.get("/admin/errors/summary")
@router.get("/api/admin/errors/summary")
async def admin_errors_summary(admin: dict = Depends(require_permission("admin.logs")), limit: int = 300):
    falhas = db_client.listar_registros(
        "system_logs",
        select="event_type,severity,created_at,description",
        filtros="severity=in.(error,critical)",
        limit=min(max(limit, 1), 1000),
        order="created_at.desc",
    )
    por_tipo = {}
    por_severidade = {}
    for item in falhas:
        por_tipo[item.get("event_type") or "unknown"] = por_tipo.get(item.get("event_type") or "unknown", 0) + 1
        por_severidade[item.get("severity") or "unknown"] = por_severidade.get(item.get("severity") or "unknown", 0) + 1
    return {"total": len(falhas), "por_tipo": por_tipo, "por_severidade": por_severidade, "recentes": falhas[:20]}


@router.get("/admin/prompts")
@router.get("/api/admin/prompts")
async def admin_prompts(admin: dict = Depends(admin_atual), limit: int = 50):
    return {
        "prompts": db_client.listar_registros(
            "ai_prompts",
            select="*",
            limit=min(max(limit, 1), 200),
            order="updated_at.desc",
        )
    }


@router.post("/admin/prompts")
@router.post("/api/admin/prompts")
async def admin_create_prompt(body: AdminPromptRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    payload = clean_payload(body)
    payload["created_by_admin_id"] = admin.get("user_id")
    prompt = db_client.criar_registro("ai_prompts", payload)
    if "erro" in prompt:
        raise HTTPException(status_code=400, detail=prompt["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "PROMPT_UPDATED",
        "Prompt de IA criado.",
        admin_id=admin.get("user_id"),
        metadata={"prompt_id": prompt.get("prompt_id"), "reading_type": prompt.get("reading_type")},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"prompt": prompt}


@router.patch("/admin/prompts/{prompt_id}")
@router.patch("/api/admin/prompts/{prompt_id}")
async def admin_update_prompt(prompt_id: str, body: AdminPromptUpdateRequest, request: Request, admin: dict = Depends(admin_atual)):
    validar_status_ativo(body.status)
    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    prompt = db_client.atualizar_registro("ai_prompts", "prompt_id", prompt_id, payload)
    if "erro" in prompt:
        raise HTTPException(status_code=400, detail=prompt["erro"])

    ctx = request_context(request)
    db_client.registrar_log(
        "PROMPT_UPDATED",
        "Prompt de IA atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"prompt_id": prompt_id, "changes": {k: ("***" if k == "content" else v) for k, v in payload.items()}},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"prompt": prompt}


@router.get("/admin/settings")
@router.get("/api/admin/settings")
async def admin_settings(admin: dict = Depends(require_permission("admin.settings")), limit: int = 200):
    settings = db_client.listar_registros(
        "settings",
        select="*",
        limit=min(max(limit, 1), 500),
        order="key.asc",
    )
    for item in settings:
        if item.get("is_secret"):
            item["value"] = "***"
    return {"settings": settings}


@router.patch("/admin/settings")
@router.patch("/api/admin/settings")
async def admin_update_settings(body: AdminSettingsUpdateRequest, request: Request, admin: dict = Depends(require_permission("admin.settings"))):
    atualizados = []
    for key, raw in body.values.items():
        value = raw.get("value") if isinstance(raw, dict) else raw
        is_secret = bool(raw.get("is_secret")) if isinstance(raw, dict) else False
        existing = db_client.listar_registros("settings", select="setting_id,key", filtros=f"key=eq.{key}", limit=1)
        payload = {
            "key": key,
            "value": json.dumps(value) if isinstance(value, (dict, list)) else str(value),
            "is_secret": is_secret,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing:
            result = db_client.atualizar_registro("settings", "setting_id", existing[0]["setting_id"], payload)
        else:
            result = db_client.criar_registro("settings", payload)
        if "erro" in result:
            raise HTTPException(status_code=400, detail=result["erro"])
        if result.get("is_secret"):
            result["value"] = "***"
        atualizados.append(result)

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Configuracoes atualizadas.",
        admin_id=admin.get("user_id"),
        metadata={"keys": list(body.values.keys())},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"settings": atualizados}


@router.get("/admin/intelligence/engagement")
@router.get("/api/admin/intelligence/engagement")
async def admin_engagement_report(admin: dict = Depends(admin_atual), limit: int = 100):
    return db_client.relatorio_engajamento(limit=min(max(limit, 1), 300))


@router.get("/admin/intelligence/hot-users")
@router.get("/api/admin/intelligence/hot-users")
async def admin_hot_users(admin: dict = Depends(admin_atual), limit: int = 100):
    return db_client.usuarios_quentes(limit=min(max(limit, 1), 300))


@router.post("/admin/payments/recover-abandoned")
@router.post("/api/admin/payments/recover-abandoned")
async def admin_recover_abandoned_pix(request: Request, admin: dict = Depends(admin_atual)):
    marked = db_client.marcar_pagamentos_pix_abandonados()
    alerts = []
    for payment in marked.get("pagamentos", []):
        automation_engine.agendar_pix_abandonado(payment)
        alert = db_client.criar_alerta_interno(
            "pix_recovery",
            "Recuperar PIX abandonado",
            "Cliente gerou PIX e nao concluiu o pagamento. Acione lembrete por WhatsApp ou email.",
            "warning",
            user_id=payment.get("user_id"),
            payment_id=payment.get("payment_id"),
            metadata={
                "transaction_id": payment.get("transaction_id"),
                "amount": payment.get("amount") or payment.get("valor"),
                "product_name": payment.get("product_name"),
            },
        )
        alerts.append(alert)

    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin executou recuperacao de PIX abandonado.",
        admin_id=admin.get("user_id"),
        metadata={"marked": marked, "alerts": len(alerts)},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"pagamentos": marked, "alertas": alerts}


@router.get("/admin/reports/financial")
@router.get("/api/admin/reports/financial")
async def admin_financial_report(admin: dict = Depends(require_permission("admin.billing.read"))):
    return db_client.relatorio_financeiro()


@router.get("/admin/dashboard/financial")
@router.get("/api/admin/dashboard/financial")
async def admin_financial_dashboard(admin: dict = Depends(require_permission("admin.billing.read")), limit: int = 1000):
    payments = db_client.listar_registros(
        "payments",
        select="status,amount,valor,product_type,gateway,created_at",
        limit=min(max(limit, 1), 3000),
        order="created_at.desc",
    )
    summary = {"total": len(payments), "receita_aprovada": 0.0, "pendente": 0.0, "por_status": {}, "por_produto": {}, "por_gateway": {}}
    for payment in payments:
        amount = float(payment.get("amount") or payment.get("valor") or 0)
        status = payment.get("status") or "unknown"
        product_type = payment.get("product_type") or "unknown"
        gateway = payment.get("gateway") or "unknown"
        summary["por_status"][status] = summary["por_status"].get(status, 0) + 1
        summary["por_produto"][product_type] = summary["por_produto"].get(product_type, 0) + amount
        summary["por_gateway"][gateway] = summary["por_gateway"].get(gateway, 0) + amount
        if status == "approved":
            summary["receita_aprovada"] += amount
        if status == "pending":
            summary["pendente"] += amount
    return summary


@router.get("/admin/reports/ai")
@router.get("/api/admin/reports/ai")
async def admin_ai_report(admin: dict = Depends(admin_atual)):
    return db_client.relatorio_ia()


@router.get("/admin/status")
@router.get("/api/admin/status")
async def admin_status_panel(admin: dict = Depends(admin_atual)):
    return db_client.painel_status_operacional()


@router.get("/admin/metrics/conversion")
@router.get("/api/admin/metrics/conversion")
async def admin_conversion_metrics(admin: dict = Depends(admin_atual)):
    base = db_client.metricas_conversao()
    analytics = analytics_summary(days=30)
    return {**base, "analytics": analytics, "funnel": analytics.get("funnel", {})}


@router.get("/admin/metrics/retention")
@router.get("/api/admin/metrics/retention")
async def admin_retention_metrics(admin: dict = Depends(admin_atual)):
    base = db_client.metricas_retencao()
    analytics_retention = analytics_summary(days=30).get("retention", {})
    return {**base, "analytics_retention": analytics_retention}


@router.get("/admin/metrics/revenue")
@router.get("/api/admin/metrics/revenue")
async def admin_revenue_metrics(admin: dict = Depends(admin_atual)):
    return db_client.metricas_receita()


@router.post("/admin/operations/daily-check")
@router.post("/api/admin/operations/daily-check")
async def admin_daily_operation_check(request: Request, admin: dict = Depends(admin_atual)):
    resultado = db_client.rotina_diaria_verificacao()
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin executou rotina diaria de verificacao operacional.",
        admin_id=admin.get("user_id"),
        metadata=resultado.get("resultado", {}),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning" if resultado.get("resultado", {}).get("health_status") != "ok" else "info",
    )
    return resultado


@router.get("/admin/maintenance")
@router.get("/api/admin/maintenance")
async def admin_get_maintenance(admin: dict = Depends(admin_atual)):
    return {
        "enabled": bool(db_client.get_setting("maintenance_mode", False)),
        "message": db_client.get_setting("maintenance_message", "Sistema em manutencao. Tente novamente em instantes."),
    }


@router.patch("/admin/maintenance")
@router.patch("/api/admin/maintenance")
async def admin_set_maintenance(body: AdminMaintenanceRequest, request: Request, admin: dict = Depends(admin_atual)):
    mode = db_client.set_setting("maintenance_mode", body.enabled)
    message = db_client.set_setting("maintenance_message", body.message or "Sistema em manutencao. Tente novamente em instantes.")
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Modo manutencao atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"enabled": body.enabled},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning" if body.enabled else "info",
    )
    return {"enabled": body.enabled, "mode": mode, "message": message}


@router.get("/admin/reprocess-queue")
@router.get("/api/admin/reprocess-queue")
async def admin_reprocess_queue(admin: dict = Depends(admin_atual), limit: int = 100):
    return {
        "queue": db_client.listar_registros(
            "reprocess_queue",
            select="*",
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.get("/admin/jobs")
@router.get("/api/admin/jobs")
async def admin_jobs(admin: dict = Depends(admin_atual), status: Optional[str] = None, type: Optional[str] = None, limit: int = 100):
    return {"jobs": job_queue_service.list_jobs(status=status, type_=type, limit=limit)}


@router.post("/admin/jobs/process")
@router.post("/api/admin/jobs/process")
async def admin_process_jobs(body: AdminJobProcessRequest, request: Request, admin: dict = Depends(admin_atual)):
    resultado = job_queue_service.process_due(limit=body.limit, dry_run=body.dry_run)
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin executou worker de jobs manualmente.",
        admin_id=admin.get("user_id"),
        metadata={"result": resultado, "dry_run": body.dry_run},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    db_client.registrar_auditoria(
        "ADMIN_JOB_WORKER_RUN",
        entity_type="reprocess_queue",
        admin_id=admin.get("user_id"),
        after_data={"processed": resultado.get("processed"), "done": resultado.get("done"), "failed": resultado.get("failed")},
        metadata={"dry_run": body.dry_run},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return resultado


@router.post("/admin/jobs/{queue_id}/retry")
@router.post("/api/admin/jobs/{queue_id}/retry")
async def admin_retry_job(queue_id: str, body: AdminJobRetryRequest, request: Request, admin: dict = Depends(admin_atual)):
    resultado = job_queue_service.retry_job(queue_id, admin_id=admin.get("user_id"), reason=body.reason)
    if "erro" in resultado:
        raise HTTPException(status_code=404, detail=resultado["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin reprocessou job da fila.",
        admin_id=admin.get("user_id"),
        metadata={"queue_id": queue_id, "reason": body.reason},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning",
    )
    return {"job": resultado}


@router.post("/admin/jobs/alerts/check")
@router.post("/api/admin/jobs/alerts/check")
async def admin_check_job_alerts(request: Request, admin: dict = Depends(admin_atual)):
    resultado = job_queue_service.alert_if_stalled()
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Admin checou fila de jobs travada.",
        admin_id=admin.get("user_id"),
        metadata=resultado,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return resultado


@router.post("/admin/reprocess-queue")
@router.post("/api/admin/reprocess-queue")
async def admin_create_reprocess_queue(body: AdminQueueRequest, request: Request, admin: dict = Depends(admin_atual)):
    if body.type not in ("webhook", "reading", "payment", "notification", "automation", "ai_reading"):
        raise HTTPException(status_code=400, detail="Tipo de fila invalido.")
    item = job_queue_service.enqueue(
        body.type,
        payload=body.payload,
        related_payment_id=body.related_payment_id,
        related_reading_id=body.related_reading_id,
        delay_minutes=body.delay_minutes,
        max_attempts=body.max_attempts,
    )
    if "erro" in item:
        raise HTTPException(status_code=400, detail=item["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Item criado na fila de reprocessamento.",
        admin_id=admin.get("user_id"),
        metadata={"queue_id": item.get("queue_id"), "type": body.type, "error_message": body.error_message},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"item": item}


@router.patch("/admin/reprocess-queue/{queue_id}/status")
@router.patch("/api/admin/reprocess-queue/{queue_id}/status")
async def admin_update_reprocess_queue_status(queue_id: str, body: AdminUserStatusRequest, request: Request, admin: dict = Depends(admin_atual)):
    if body.status not in ("pending", "processing", "done", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Status de fila invalido.")
    payload = {"status": body.status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if body.status in ("done", "failed", "cancelled"):
        payload["processed_at"] = datetime.now(timezone.utc).isoformat()
    item = db_client.atualizar_registro("reprocess_queue", "queue_id", queue_id, payload)
    if "erro" in item:
        raise HTTPException(status_code=400, detail=item["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Status da fila de reprocessamento atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"queue_id": queue_id, "status": body.status},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"item": item}


@router.get("/admin/alerts")
@router.get("/api/admin/alerts")
async def admin_alerts(admin: dict = Depends(require_permission("admin.alerts")), limit: int = 100, status: Optional[str] = None, severity: Optional[str] = None, type: Optional[str] = None):
    filtros = []
    if status:
        filtros.append(f"status=eq.{status}")
    if severity:
        filtros.append(f"severity=eq.{severity}")
    if type:
        filtros.append(f"type=eq.{type}")
    return {
        "alerts": db_client.listar_registros(
            "internal_alerts",
            select="*",
            filtros="&".join(filtros),
            limit=min(max(limit, 1), 300),
            order="created_at.desc",
        )
    }


@router.post("/admin/alerts/generate")
@router.post("/api/admin/alerts/generate")
async def admin_generate_alerts(request: Request, admin: dict = Depends(require_permission("admin.alerts"))):
    resultado = db_client.gerar_alertas_operacionais()
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Alertas internos gerados.",
        admin_id=admin.get("user_id"),
        metadata=resultado,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return resultado


@router.patch("/admin/alerts/{alert_id}/status")
@router.patch("/api/admin/alerts/{alert_id}/status")
async def admin_update_alert_status(alert_id: str, body: AdminAlertStatusRequest, request: Request, admin: dict = Depends(require_permission("admin.alerts"))):
    if body.status not in ("open", "acknowledged", "resolved"):
        raise HTTPException(status_code=400, detail="Status de alerta invalido.")
    payload = {"status": body.status}
    if body.status == "resolved":
        payload["resolved_at"] = datetime.now(timezone.utc).isoformat()
    alert = db_client.atualizar_registro("internal_alerts", "alert_id", alert_id, payload)
    if "erro" in alert:
        raise HTTPException(status_code=400, detail=alert["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ADMIN_ACTION",
        "Status de alerta interno atualizado.",
        admin_id=admin.get("user_id"),
        metadata={"alert_id": alert_id, "status": body.status},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"alert": alert}


