import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

import db_client
from app.core.context import clean_payload, request_context
from app.core.security import admin_atual
from app.modules.admin.security import audit_sensitive_view, mask_user, require_permission
from app.modules.admin.service import validar_status_ativo
from app.modules.analytics.use_cases import track_server_event

from .schemas import (
    AdminAssignTagRequest,
    AdminCustomerNoteRequest,
    AdminCustomerSegmentRequest,
    AdminCustomerSegmentUpdateRequest,
    AdminCustomerTagRequest,
    AdminCustomerTagUpdateRequest,
    AdminSegmentTriggerRequest,
    AdminSegmentTriggerUpdateRequest,
)
from .service import (
    crm_classificacao,
    crm_default_segmentos,
    temas_mais_perguntados,
    validar_visibilidade_nota,
)


router = APIRouter(tags=["crm"])
@router.get("/admin/crm")
@router.get("/api/admin/crm")
async def admin_crm_overview(request: Request, admin: dict = Depends(require_permission("admin.crm")), limit: int = 100, reveal: bool = False):
    usuarios = db_client.listar_registros(
        "users",
        select="user_id,nome,email,whatsapp,criado_em,assinante,plan_id,status,credits_balance,last_login_at,updated_at",
        limit=min(max(limit, 1), 300),
        order="criado_em.desc",
    )
    enriched = []
    for usuario in usuarios:
        classificacao = crm_classificacao(usuario)
        enriched.append({**mask_user(usuario, reveal=reveal), "crm": classificacao, "classes": classificacao["classes"]})
    if reveal:
        audit_sensitive_view(request, admin, "ADMIN_CRM_SENSITIVE_VIEWED", "crm", metadata={"limit": limit})
    return {
        "usuarios": enriched,
        "tags": db_client.listar_registros("customer_tags", select="*", limit=300, order="name.asc"),
        "segmentos": db_client.listar_registros("customer_segments", select="*", limit=300, order="name.asc"),
    }


@router.get("/admin/crm/users/{user_id}")
@router.get("/api/admin/crm/users/{user_id}")
async def admin_crm_user(user_id: str, request: Request, admin: dict = Depends(require_permission("admin.crm")), reveal: bool = False):
    usuario = db_client.get_user_by_id(user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    audit_sensitive_view(request, admin, "ADMIN_CRM_USER_VIEWED", "users", entity_id=user_id, metadata={"reveal": reveal})
    leituras = db_client.listar_registros("readings", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="criado_em.desc")
    perguntas = db_client.listar_registros("questions", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="criado_em.desc")
    pagamentos = db_client.listar_registros("payments", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="created_at.desc")
    mensagens = db_client.listar_registros("message_events", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="created_at.desc")
    notificacoes = db_client.listar_registros("notification_logs", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="created_at.desc")
    logs = db_client.listar_registros("system_logs", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="created_at.desc")
    notas = db_client.listar_registros("admin_customer_notes", select="*", filtros=f"user_id=eq.{user_id}", limit=100, order="created_at.desc")
    tags = db_client.listar_registros("user_customer_tags", select="*,customer_tags(*)", filtros=f"user_id=eq.{user_id}", limit=100, order="created_at.desc")
    segmentos = db_client.listar_registros("user_customer_segments", select="*,customer_segments(*)", filtros=f"user_id=eq.{user_id}", limit=100, order="assigned_at.desc")
    return {
        "usuario": mask_user(usuario, reveal=reveal),
        "classificacao": crm_classificacao(usuario, pagamentos, leituras),
        "tags": tags,
        "segmentos": segmentos,
        "notas": notas,
        "leituras": leituras,
        "perguntas": perguntas,
        "pagamentos": pagamentos,
        "mensagens": mensagens,
        "notificacoes": notificacoes,
        "interacoes": logs,
        "temas": temas_mais_perguntados(perguntas + leituras),
    }


@router.get("/admin/crm/tags")
@router.get("/api/admin/crm/tags")
async def admin_crm_tags(admin: dict = Depends(require_permission("admin.crm")), limit: int = 200):
    return {"tags": db_client.listar_registros("customer_tags", select="*", limit=min(max(limit, 1), 500), order="name.asc")}


@router.post("/admin/crm/tags")
@router.post("/api/admin/crm/tags")
async def admin_crm_create_tag(body: AdminCustomerTagRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_status_ativo(body.status)
    tag = db_client.criar_registro("customer_tags", clean_payload(body))
    if "erro" in tag:
        raise HTTPException(status_code=400, detail=tag["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Tag de cliente criada.", admin_id=admin.get("user_id"), metadata={"tag_id": tag.get("tag_id")}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"tag": tag}


@router.patch("/admin/crm/tags/{tag_id}")
@router.patch("/api/admin/crm/tags/{tag_id}")
async def admin_crm_update_tag(tag_id: str, body: AdminCustomerTagUpdateRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_status_ativo(body.status)
    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    tag = db_client.atualizar_registro("customer_tags", "tag_id", tag_id, payload)
    if "erro" in tag:
        raise HTTPException(status_code=400, detail=tag["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Tag de cliente atualizada.", admin_id=admin.get("user_id"), metadata={"tag_id": tag_id}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"tag": tag}


@router.post("/admin/crm/users/{user_id}/tags")
@router.post("/api/admin/crm/users/{user_id}/tags")
async def admin_crm_assign_tag(user_id: str, body: AdminAssignTagRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    if not db_client.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    assigned = db_client.criar_registro("user_customer_tags", {"user_id": user_id, "tag_id": body.tag_id, "assigned_by_user_id": admin.get("user_id")})
    if "erro" in assigned:
        raise HTTPException(status_code=400, detail=assigned["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Tag atribuida ao cliente.", user_id=user_id, admin_id=admin.get("user_id"), metadata={"tag_id": body.tag_id}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"tag": assigned}


@router.get("/admin/crm/segments")
@router.get("/api/admin/crm/segments")
async def admin_crm_segments(admin: dict = Depends(require_permission("admin.crm")), limit: int = 200):
    return {"segmentos": db_client.listar_registros("customer_segments", select="*", limit=min(max(limit, 1), 500), order="name.asc")}


@router.post("/admin/crm/segments")
@router.post("/api/admin/crm/segments")
async def admin_crm_create_segment(body: AdminCustomerSegmentRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_status_ativo(body.status)
    segment = db_client.criar_registro("customer_segments", clean_payload(body))
    if "erro" in segment:
        raise HTTPException(status_code=400, detail=segment["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Segmento de cliente criado.", admin_id=admin.get("user_id"), metadata={"segment_id": segment.get("segment_id")}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"segmento": segment}


@router.patch("/admin/crm/segments/{segment_id}")
@router.patch("/api/admin/crm/segments/{segment_id}")
async def admin_crm_update_segment(segment_id: str, body: AdminCustomerSegmentUpdateRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_status_ativo(body.status)
    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    segment = db_client.atualizar_registro("customer_segments", "segment_id", segment_id, payload)
    if "erro" in segment:
        raise HTTPException(status_code=400, detail=segment["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Segmento de cliente atualizado.", admin_id=admin.get("user_id"), metadata={"segment_id": segment_id}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"segmento": segment}


@router.post("/admin/crm/classify")
@router.post("/api/admin/crm/classify")
async def admin_crm_classify(request: Request, admin: dict = Depends(require_permission("admin.crm")), limit: int = 300):
    segmentos_por_classe = {}
    for item in crm_default_segmentos():
        existente = db_client.listar_registros("customer_segments", select="segment_id,name", filtros=f"name=eq.{item['name']}", limit=1)
        segmento = existente[0] if existente else db_client.criar_registro("customer_segments", item)
        if "erro" not in segmento:
            segmentos_por_classe[item["rules"]["class"]] = segmento["segment_id"]

    usuarios = db_client.listar_registros("users", select="user_id,nome,email,criado_em,last_login_at,updated_at", limit=min(max(limit, 1), 500), order="criado_em.desc")
    atribuidos = 0
    for usuario in usuarios:
        classificacao = crm_classificacao(usuario)
        for classe in classificacao["classes"]:
            segment_id = segmentos_por_classe.get(classe)
            if not segment_id:
                continue
            result = db_client.criar_registro("user_customer_segments", {"user_id": usuario["user_id"], "segment_id": segment_id})
            if "erro" not in result:
                atribuidos += 1
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Classificacao CRM executada.", admin_id=admin.get("user_id"), metadata={"usuarios": len(usuarios), "atribuicoes": atribuidos}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"usuarios": len(usuarios), "atribuicoes": atribuidos, "segmentos": segmentos_por_classe}


@router.post("/admin/crm/users/{user_id}/notes")
@router.post("/api/admin/crm/users/{user_id}/notes")
async def admin_crm_create_note(user_id: str, body: AdminCustomerNoteRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_visibilidade_nota(body.visibility)
    if not db_client.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    note = db_client.criar_registro("admin_customer_notes", {"user_id": user_id, "admin_id": admin.get("user_id"), **clean_payload(body)})
    if "erro" in note:
        raise HTTPException(status_code=400, detail=note["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Nota administrativa criada.", user_id=user_id, admin_id=admin.get("user_id"), metadata={"note_id": note.get("note_id")}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"nota": note}


@router.get("/admin/crm/triggers")
@router.get("/api/admin/crm/triggers")
async def admin_crm_triggers(admin: dict = Depends(require_permission("admin.crm")), limit: int = 200):
    return {"gatilhos": db_client.listar_registros("segment_automation_triggers", select="*,customer_segments(*)", limit=min(max(limit, 1), 500), order="created_at.desc")}


@router.post("/admin/crm/triggers")
@router.post("/api/admin/crm/triggers")
async def admin_crm_create_trigger(body: AdminSegmentTriggerRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_status_ativo(body.status)
    if body.channel and body.channel not in ("email", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canal invalido.")
    trigger = db_client.criar_registro("segment_automation_triggers", clean_payload(body))
    if "erro" in trigger:
        raise HTTPException(status_code=400, detail=trigger["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Gatilho por segmento criado.", admin_id=admin.get("user_id"), metadata={"trigger_id": trigger.get("trigger_id")}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"gatilho": trigger}


@router.patch("/admin/crm/triggers/{trigger_id}")
@router.patch("/api/admin/crm/triggers/{trigger_id}")
async def admin_crm_update_trigger(trigger_id: str, body: AdminSegmentTriggerUpdateRequest, request: Request, admin: dict = Depends(require_permission("admin.crm"))):
    validar_status_ativo(body.status)
    if body.channel and body.channel not in ("email", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canal invalido.")
    payload = clean_payload(body)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    trigger = db_client.atualizar_registro("segment_automation_triggers", "trigger_id", trigger_id, payload)
    if "erro" in trigger:
        raise HTTPException(status_code=400, detail=trigger["erro"])
    ctx = request_context(request)
    db_client.registrar_log("ADMIN_ACTION", "Gatilho por segmento atualizado.", admin_id=admin.get("user_id"), metadata={"trigger_id": trigger_id}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    return {"gatilho": trigger}


@router.get("/admin/crm/export.csv")
@router.get("/api/admin/crm/export.csv")
async def admin_crm_export_csv(request: Request, admin: dict = Depends(require_permission("admin.export")), limit: int = 500):
    audit_sensitive_view(request, admin, "ADMIN_CRM_EXPORT_CREATED", "crm_export", metadata={"limit": limit})
    track_server_event("admin_export_created", admin_id=admin.get("user_id"), entity_type="crm_export", metadata={"limit": limit, "format": "csv"})
    usuarios = db_client.listar_registros(
        "users",
        select="user_id,nome,email,whatsapp,criado_em,assinante,status,credits_balance,last_login_at,updated_at",
        limit=min(max(limit, 1), 1000),
        order="criado_em.desc",
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "nome", "email", "whatsapp", "status", "assinante", "creditos", "classes", "receita_aprovada", "pagamentos_aprovados", "leituras_total", "dias_inativo", "criado_em"])
    for usuario in usuarios:
        classificacao = crm_classificacao(usuario)
        writer.writerow([
            usuario.get("user_id"),
            usuario.get("nome"),
            usuario.get("email"),
            usuario.get("whatsapp"),
            usuario.get("status"),
            usuario.get("assinante"),
            usuario.get("credits_balance"),
            "|".join(classificacao["classes"]),
            classificacao["receita_aprovada"],
            classificacao["pagamentos_aprovados"],
            classificacao["leituras_total"],
            classificacao["dias_inativo"],
            usuario.get("criado_em"),
        ])
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=madame-do-luar-crm.csv"},
    )


