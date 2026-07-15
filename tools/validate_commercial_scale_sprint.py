"""
Valida a Sprint 5 - Escala comercial.

Confere CRM/segmentos, cupons, rituais pagos e oferta pos-leitura com
upsell/downsell contextual. Tambem prova que o ritual pago e liberado por
consumo de creditos, sem checkout em reais.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import api
import db_client
import seed_phase9_monetization


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _route_paths() -> set[str]:
    return {route.path for route in api.app.routes}


def _ensure_segment_defaults() -> dict:
    created = 0
    segmentos = {}
    for item in api.crm_default_segmentos():
        current = db_client.listar_registros("customer_segments", select="*", filtros=f"name=eq.{item['name']}", limit=1)
        segment = current[0] if current else db_client.criar_registro("customer_segments", item)
        _require("erro" not in segment, f"Falha ao garantir segmento {item['name']}: {segment}")
        created += 0 if current else 1
        segmentos[item["rules"]["class"]] = segment
    return {"created": created, "segmentos": segmentos}


def _create_test_user() -> dict:
    suffix = uuid.uuid4().hex[:12]
    email = f"sprint5-{suffix}@madamedoluar.local"
    result = db_client.criar_usuario(
        nome="Cliente Sprint 5",
        email=email,
        senha="SenhaSprint5!2026",
        whatsapp=f"+55119{suffix[:8]}",
        whatsapp_opt_in=True,
        email_opt_in=True,
        terms_accepted=True,
        privacy_accepted=True,
        ai_notice_accepted=True,
    )
    _require("erro" not in result and result.get("usuario"), f"Falha ao criar usuario teste: {result}")
    return result["usuario"]


def _validate_crm_and_segments(user: dict, segmentos: dict) -> dict:
    question_id = db_client.insert_question(
        user["user_id"],
        "Quero entender se esse amor ainda tem caminho para voltar.",
        tema="amor",
    )
    _require(bool(question_id), "Falha ao registrar pergunta para segmentacao comercial.")

    classificacao = api.crm_classificacao(user)
    _require("cliente_novo" in classificacao["classes"], f"Classificacao CRM inesperada: {classificacao}")
    segment_id = segmentos["cliente_novo"]["segment_id"]
    assigned = db_client.criar_registro("user_customer_segments", {"user_id": user["user_id"], "segment_id": segment_id})
    _require("erro" not in assigned or "duplicate" in str(assigned.get("erro")).lower(), f"Falha ao atribuir segmento: {assigned}")
    return {"question_id": question_id, "classificacao": classificacao, "segment_id": segment_id}


def _active_rituals() -> tuple[dict, dict]:
    paid = db_client.listar_registros("rituals", select="*", filtros="ativo=eq.true&preco=gt.0", limit=20)
    free = db_client.listar_registros("rituals", select="*", filtros="ativo=eq.true&preco=lte.0", limit=20)
    _require(bool(paid), "Nenhum ritual pago ativo encontrado.")
    _require(bool(free), "Nenhum ritual gratuito ativo encontrado.")
    return paid[0], free[0]


def _validate_coupon(paid_ritual: dict) -> dict:
    produto = db_client.calcular_produto_pagamento("ritual", paid_ritual["ritual_id"])
    _require("erro" not in produto, f"Falha ao calcular ritual pago: {produto}")
    discounted = db_client.aplicar_cupom_produto(produto, "RITUAL10")
    _require("erro" not in discounted, f"Falha ao aplicar cupom RITUAL10: {discounted}")
    _require(float(discounted.get("discount_amount") or 0) > 0, "Cupom RITUAL10 nao gerou desconto.")
    _require(float(discounted["amount"]) < float(discounted["original_amount"]), "Valor com cupom nao reduziu.")
    return discounted


def _validate_paid_ritual_credits(user: dict, produto: dict) -> dict:
    custo_creditos = api.custo_creditos_ritual(produto)
    credito = db_client.ajustar_creditos(
        user["user_id"],
        amount=custo_creditos,
        tipo="add",
        reason="Auditoria Sprint 5 - saldo para ritual",
    )
    _require("erro" not in credito, f"Falha ao adicionar creditos para teste: {credito}")
    consumo = db_client.consumir_creditos(
        user["user_id"],
        amount=custo_creditos,
        reason=f"Auditoria Sprint 5 - compra de ritual {produto['ritual_id']}",
    )
    _require("erro" not in consumo, f"Falha ao consumir creditos do ritual: {consumo}")
    compra = db_client.criar_registro("ritual_purchases", {
        "user_id": user["user_id"],
        "ritual_id": produto["ritual_id"],
        "status": "approved",
        "credits_spent": custo_creditos,
        "coupon_code": produto.get("coupon_code"),
    })
    if "erro" in compra and any(field in str(compra["erro"]) for field in ("credits_spent", "coupon_code")):
        compra = db_client.criar_registro("ritual_purchases", {
            "user_id": user["user_id"],
            "ritual_id": produto["ritual_id"],
            "status": "approved",
        })
    _require("erro" not in compra, f"Falha ao registrar compra de ritual: {compra}")
    return {"compra": compra, "consumo": consumo, "credits_spent": custo_creditos}


def _validate_offers(user: dict) -> dict:
    offers = api.selecionar_ofertas_pos_leitura(user["user_id"])
    _require(offers.get("tema") == "amor", f"Tema comercial inesperado: {offers}")
    _require(offers.get("upsell") and not offers["upsell"]["gratuito"], f"Upsell pago ausente: {offers}")
    _require(offers.get("downsell") and offers["downsell"]["gratuito"], f"Downsell gratuito ausente: {offers}")
    _require(offers.get("coupon_hint") == "RITUAL10", f"Cupom de oferta inesperado: {offers}")
    return offers


def main() -> None:
    load_dotenv()
    _require(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"), "SUPABASE_URL/SUPABASE_KEY ausentes.")
    missing = {
        "/admin/crm",
        "/admin/crm/segments",
        "/admin/coupons",
        "/api/rituals",
        "/api/offers/after-reading",
    } - _route_paths()
    _require(not missing, "Rotas comerciais ausentes: " + ", ".join(sorted(missing)))

    seed_result = seed_phase9_monetization.main()
    _require(seed_result == 0, "Seed de monetizacao falhou.")
    segment_result = _ensure_segment_defaults()
    user = _create_test_user()
    crm = _validate_crm_and_segments(user, segment_result["segmentos"])
    paid_ritual, free_ritual = _active_rituals()
    produto_com_cupom = _validate_coupon(paid_ritual)
    compra_creditos = _validate_paid_ritual_credits(user, produto_com_cupom)
    offers = _validate_offers(user)

    print("OK Sprint 5 escala comercial validada.")
    print(f"Usuario CRM: {user['user_id']} / classe={','.join(crm['classificacao']['classes'])}")
    print(f"Segmentos padrao: {len(segment_result['segmentos'])} / novos={segment_result['created']}")
    print(f"Cupom RITUAL10: desconto={produto_com_cupom.get('discount_amount')} / creditos={api.custo_creditos_ritual(produto_com_cupom)}")
    print(f"Ritual pago: {paid_ritual.get('nome')} / creditos_consumidos={compra_creditos['credits_spent']}")
    print(f"Downsell: {free_ritual.get('nome')} / oferta_tema={offers.get('tema')}")


if __name__ == "__main__":
    main()
