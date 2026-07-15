from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

import db_client
from app.core.context import request_context
from app.core.security import usuario_atual
from app.modules.analytics.use_cases import track_server_event

from .schemas import AccountDeleteRequest, PerfilUpdateRequest, SenhaUpdateRequest
from .service import export_payload, listar_leituras_usuario, montar_resumo_perfil


router = APIRouter(tags=["users"])


@router.get("/lgpd/export")
@router.get("/api/lgpd/export")
async def exportar_meus_dados(request: Request, usuario: dict = Depends(usuario_atual)):
    dados = db_client.exportar_dados_usuario(usuario["user_id"])
    ctx = request_context(request)
    db_client.registrar_auditoria(
        "DATA_EXPORT_REQUESTED",
        entity_type="users",
        entity_id=usuario["user_id"],
        user_id=usuario["user_id"],
        metadata={"sections": list(dados.keys())},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return JSONResponse(
        content=export_payload(dados),
        headers={"Content-Disposition": "attachment; filename=madame-do-luar-dados.json"},
    )


@router.delete("/lgpd/account")
@router.delete("/api/lgpd/account")
async def excluir_minha_conta(body: AccountDeleteRequest, request: Request, usuario: dict = Depends(usuario_atual)):
    if body.confirmation.strip().upper() != "EXCLUIR":
        raise HTTPException(status_code=400, detail="Digite EXCLUIR para confirmar a exclusao da conta.")
    resultado = db_client.anonimizar_usuario(usuario["user_id"], reason=body.reason)
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    ctx = request_context(request)
    db_client.registrar_log(
        "ACCOUNT_DELETED",
        "Usuario solicitou exclusao/anominizacao da propria conta.",
        user_id=usuario["user_id"],
        metadata={"reason": body.reason},
        severity="warning",
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    return {"status": "ok", "mensagem": "Conta anonimizada e acesso desativado."}


@router.get("/me")
@router.get("/api/auth/me")
async def auth_me(usuario: dict = Depends(usuario_atual)):
    return {"usuario": usuario}


@router.get("/api/me")
@router.get("/me/profile")
@router.get("/api/perfil")
async def perfil(usuario: dict = Depends(usuario_atual)):
    return montar_resumo_perfil(usuario)


@router.get("/me/credits")
@router.get("/api/me/credits")
async def me_credits(usuario: dict = Depends(usuario_atual)):
    user_id = usuario["user_id"]
    return {
        "credits_balance": int(usuario.get("credits_balance") or 0),
        "transactions": db_client.listar_registros(
            "credit_transactions",
            select="*",
            filtros=f"user_id=eq.{user_id}",
            limit=100,
            order="created_at.desc",
        ),
    }


@router.get("/me/readings")
@router.get("/api/me/readings")
async def me_readings(usuario: dict = Depends(usuario_atual), limit: int = 50):
    return listar_leituras_usuario(usuario, limit)


@router.get("/me/payments")
@router.get("/api/me/payments")
async def me_payments(usuario: dict = Depends(usuario_atual), limit: int = 50):
    return {
        "payments": db_client.listar_registros(
            "payments",
            select="*",
            filtros=f"user_id=eq.{usuario['user_id']}",
            limit=min(max(limit, 1), 200),
            order="created_at.desc",
        )
    }


@router.patch("/me")
@router.patch("/api/me")
@router.patch("/api/perfil")
async def atualizar_perfil(body: PerfilUpdateRequest, usuario: dict = Depends(usuario_atual)):
    nome = body.nome.strip() if body.nome is not None else None
    avatar_url = body.avatar_url.strip() if body.avatar_url is not None else None
    whatsapp = body.whatsapp.strip() if body.whatsapp is not None else None

    if nome is not None and len(nome) < 2:
        raise HTTPException(status_code=400, detail="Informe um nome com pelo menos 2 caracteres.")

    resultado = db_client.atualizar_usuario(
        usuario["user_id"],
        nome=nome,
        avatar_url=avatar_url,
        whatsapp=whatsapp,
        whatsapp_opt_in=body.whatsapp_opt_in,
        email_opt_in=body.email_opt_in,
    )
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    track_server_event("profile_updated", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])
    if body.whatsapp_opt_in is True:
        track_server_event("whatsapp_opt_in", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])
    elif body.whatsapp_opt_in is False:
        track_server_event("whatsapp_opt_out", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])
    if body.email_opt_in is True:
        track_server_event("email_opt_in", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])

    return montar_resumo_perfil(resultado["usuario"])


@router.post("/me/whatsapp/opt-in")
@router.post("/api/me/whatsapp/opt-in")
async def whatsapp_opt_in(usuario: dict = Depends(usuario_atual)):
    if not usuario.get("whatsapp"):
        raise HTTPException(status_code=400, detail="Informe um WhatsApp no perfil antes de ativar mensagens.")
    resultado = db_client.atualizar_usuario(usuario["user_id"], whatsapp_opt_in=True)
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    track_server_event("whatsapp_opt_in", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])
    return {"status": "ok", "whatsapp_opt_in": True, "usuario": resultado["usuario"]}


@router.post("/me/whatsapp/opt-out")
@router.post("/api/me/whatsapp/opt-out")
async def whatsapp_opt_out(usuario: dict = Depends(usuario_atual)):
    resultado = db_client.atualizar_usuario(usuario["user_id"], whatsapp_opt_in=False)
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    db_client.atualizar_registro(
        "message_events",
        "user_id",
        usuario["user_id"],
        {"status": "cancelled", "error_message": "Usuario realizou opt-out de WhatsApp."},
    )
    track_server_event("whatsapp_opt_out", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])
    return {"status": "ok", "whatsapp_opt_in": False, "usuario": resultado["usuario"]}


@router.post("/me/email/opt-in")
@router.post("/api/me/email/opt-in")
async def email_opt_in(usuario: dict = Depends(usuario_atual)):
    resultado = db_client.atualizar_usuario(usuario["user_id"], email_opt_in=True)
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    track_server_event("email_opt_in", user_id=usuario["user_id"], entity_type="users", entity_id=usuario["user_id"])
    return {"status": "ok", "email_opt_in": True, "usuario": resultado["usuario"]}


@router.post("/me/email/opt-out")
@router.post("/api/me/email/opt-out")
async def email_opt_out(usuario: dict = Depends(usuario_atual)):
    resultado = db_client.atualizar_usuario(usuario["user_id"], email_opt_in=False)
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])
    return {"status": "ok", "email_opt_in": False, "usuario": resultado["usuario"]}


@router.post("/api/perfil/senha")
async def alterar_senha(body: SenhaUpdateRequest, usuario: dict = Depends(usuario_atual)):
    if len(body.nova_senha or "") < 8:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 8 caracteres.")

    resultado = db_client.alterar_senha(usuario["user_id"], body.senha_atual, body.nova_senha)
    if "erro" in resultado:
        raise HTTPException(status_code=400, detail=resultado["erro"])

    return {"status": "ok", "mensagem": "Senha atualizada com sucesso."}
