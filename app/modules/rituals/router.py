from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

import db_client
from app.core.context import request_context
from app.modules.analytics.use_cases import track_server_event
from app.core.security import usuario_atual, usuario_atual_opcional

from .schemas import RitualPurchaseRequest
from .service import criar_compra_ritual_creditos, custo_creditos_ritual, ritual_public_payload, selecionar_ofertas_pos_leitura


router = APIRouter(tags=["rituals"])


@router.get("/rituals")
@router.get("/api/rituals")
async def public_rituals(tema: Optional[str] = None, tipo: Optional[str] = None, limit: int = 50):
    filtros = "ativo=eq.true"
    if tema:
        filtros += f"&tema=eq.{tema}"
    rituais = db_client.listar_registros("rituals", select="*", filtros=filtros, limit=min(max(limit, 1), 100))
    items = [ritual_public_payload(r) for r in rituais]
    if tipo == "gratuito":
        items = [r for r in items if r["gratuito"]]
    elif tipo == "pago":
        items = [r for r in items if not r["gratuito"]]
    temas = sorted({r.get("tema") for r in items if r.get("tema")})
    return {"rituais": items, "temas": temas}


@router.get("/rituals/{ritual_id}")
@router.get("/api/rituals/{ritual_id}")
async def public_ritual_detail(ritual_id: str, usuario: dict = Depends(usuario_atual_opcional)):
    ritual = db_client.buscar_por_id("rituals", "ritual_id", ritual_id)
    if not ritual or not ritual.get("ativo", True):
        raise HTTPException(status_code=404, detail="Ritual nao encontrado.")
    payload = ritual_public_payload(ritual)
    compra = None
    if usuario:
        compras = db_client.listar_registros("ritual_purchases", select="*", filtros=f"user_id=eq.{usuario['user_id']}&ritual_id=eq.{ritual_id}&status=eq.approved", limit=1)
        compra = compras[0] if compras else None
    if compra or payload["gratuito"]:
        payload["pdf_url"] = ritual.get("pdf_url")
        payload["audio_url"] = ritual.get("audio_url")
    track_server_event("ritual_viewed", user_id=usuario.get("user_id") if usuario else None, entity_type="rituals", entity_id=ritual_id, metadata={"gratuito": payload.get("gratuito")})
    return {"ritual": payload, "compra": compra}


@router.post("/rituals/{ritual_id}/purchase")
@router.post("/api/rituals/{ritual_id}/purchase")
async def purchase_ritual(ritual_id: str, body: RitualPurchaseRequest, request: Request, usuario: dict = Depends(usuario_atual)):
    produto = db_client.calcular_produto_pagamento("ritual", ritual_id)
    if "erro" in produto:
        raise HTTPException(status_code=404, detail=produto["erro"])
    produto = db_client.aplicar_cupom_produto(produto, body.coupon_code)
    if "erro" in produto:
        if body.coupon_code:
            track_server_event("coupon_failed", user_id=usuario["user_id"], entity_type="rituals", entity_id=ritual_id, metadata={"coupon_code": body.coupon_code, "erro": produto["erro"]})
        raise HTTPException(status_code=400, detail=produto["erro"])
    if body.coupon_code and produto.get("coupon_code"):
        track_server_event("coupon_applied", user_id=usuario["user_id"], entity_type="rituals", entity_id=ritual_id, metadata={"coupon_code": produto.get("coupon_code"), "discount_amount": produto.get("discount_amount") or 0})
    compras = db_client.listar_registros("ritual_purchases", select="*", filtros=f"user_id=eq.{usuario['user_id']}&ritual_id=eq.{ritual_id}&status=eq.approved", limit=1)
    if compras:
        track_server_event("ritual_purchased", user_id=usuario["user_id"], entity_type="rituals", entity_id=ritual_id, metadata={"ja_comprado": True})
        return {"status": "approved", "ritual": ritual_public_payload(produto["ritual"]), "compra": compras[0], "ja_comprado": True}

    custo_creditos = custo_creditos_ritual(produto)
    if custo_creditos <= 0:
        compra = criar_compra_ritual_creditos(usuario["user_id"], ritual_id, "approved", credits_spent=0, coupon_code=produto.get("coupon_code"))
        if "erro" in compra:
            raise HTTPException(status_code=400, detail=compra["erro"])
        track_server_event("ritual_purchased", user_id=usuario["user_id"], entity_type="rituals", entity_id=ritual_id, metadata={"credits_spent": 0, "coupon_code": produto.get("coupon_code")})
        return {"status": "approved", "ritual": ritual_public_payload(produto["ritual"]), "compra": compra}

    compra_atomica = db_client.comprar_ritual_com_creditos(usuario["user_id"], ritual_id, amount=custo_creditos, reason=f"Compra de ritual: {produto.get('product_name') or ritual_id}", coupon_code=produto.get("coupon_code"))
    if "fallback_required" not in compra_atomica:
        if "erro" in compra_atomica:
            raise HTTPException(status_code=402, detail=compra_atomica.get("erro") or "Creditos insuficientes.")
        compra_id = compra_atomica.get("purchase_id")
        compra = db_client.buscar_por_id("ritual_purchases", "purchase_id", compra_id) if compra_id else None
        if produto.get("coupon_code") and not compra_atomica.get("ja_comprado"):
            db_client.registrar_uso_cupom(produto.get("coupon_code"), user_id=usuario["user_id"])
        ctx = request_context(request)
        db_client.registrar_log("RITUAL_PURCHASE_APPROVED_WITH_CREDITS", "Ritual comprado com creditos de forma idempotente.", user_id=usuario["user_id"], metadata={"ritual_id": ritual_id, "credits_spent": custo_creditos, "offer_context": body.offer_context, "coupon_code": produto.get("coupon_code"), "idempotent": True}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
        track_server_event("ritual_purchased", user_id=usuario["user_id"], entity_type="rituals", entity_id=ritual_id, metadata={"credits_spent": custo_creditos, "coupon_code": produto.get("coupon_code"), "idempotent": True})
        return {"status": "approved", "ritual": ritual_public_payload(produto["ritual"]), "compra": compra or compra_atomica, "ja_comprado": bool(compra_atomica.get("ja_comprado")), "saldo_atual": compra_atomica.get("saldo_atual")}

    consumo_credito = db_client.consumir_creditos(usuario["user_id"], amount=custo_creditos, reason=f"Compra de ritual: {produto.get('product_name') or ritual_id}")
    if "erro" in consumo_credito:
        raise HTTPException(status_code=402, detail=consumo_credito.get("erro") or "Creditos insuficientes.")
    compra = criar_compra_ritual_creditos(usuario["user_id"], ritual_id, "pending", credits_spent=custo_creditos, coupon_code=produto.get("coupon_code"))
    if "erro" in compra:
        db_client.estornar_creditos(usuario["user_id"], custo_creditos, "Estorno: falha ao liberar ritual")
        raise HTTPException(status_code=400, detail=compra["erro"])
    compra = db_client.atualizar_registro("ritual_purchases", "purchase_id", compra["purchase_id"], {"status": "approved", "updated_at": datetime.now(timezone.utc).isoformat()})
    if "erro" in compra:
        db_client.estornar_creditos(usuario["user_id"], custo_creditos, "Estorno: falha ao aprovar ritual")
        raise HTTPException(status_code=400, detail=compra["erro"])
    if produto.get("coupon_code"):
        db_client.registrar_uso_cupom(produto.get("coupon_code"), user_id=usuario["user_id"])
    ctx = request_context(request)
    db_client.registrar_log("RITUAL_PURCHASE_APPROVED_WITH_CREDITS", "Ritual comprado com creditos.", user_id=usuario["user_id"], metadata={"ritual_id": ritual_id, "credits_spent": custo_creditos, "offer_context": body.offer_context, "coupon_code": produto.get("coupon_code")}, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"])
    track_server_event("ritual_purchased", user_id=usuario["user_id"], entity_type="rituals", entity_id=ritual_id, metadata={"credits_spent": custo_creditos, "coupon_code": produto.get("coupon_code")})
    return {"status": "approved", "ritual": ritual_public_payload(produto["ritual"]), "credits_spent": custo_creditos, "saldo_atual": consumo_credito.get("saldo_atual"), "discount_amount": produto.get("discount_amount") or 0, "compra": compra}


@router.get("/offers/after-reading")
@router.get("/api/offers/after-reading")
async def offers_after_reading(usuario: dict = Depends(usuario_atual)):
    return selecionar_ofertas_pos_leitura(usuario["user_id"])
