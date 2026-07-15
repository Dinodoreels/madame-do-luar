import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

import db_client


def validar_visibilidade_nota(visibility: Optional[str]):
    if visibility is not None and visibility not in ("internal", "support", "sales", "marketing"):
        raise HTTPException(status_code=400, detail="Visibilidade invalida.")


def temas_mais_perguntados(leituras: list[dict], limite: int = 8) -> list[dict]:
    contagem = defaultdict(int)
    for item in leituras:
        tema = item.get("tema") or item.get("type") or item.get("tipo") or item.get("tipo_leitura")
        pergunta = item.get("pergunta") or item.get("question") or ""
        if not tema and pergunta:
            texto = pergunta.lower()
            for candidato in ("amor", "dinheiro", "trabalho", "familia", "saude", "espiritual", "relacionamento", "carreira"):
                if candidato in texto:
                    tema = candidato
                    break
        if tema:
            contagem[str(tema).lower()] += 1
    return [{"tema": tema, "total": total} for tema, total in sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:limite]]


def crm_classificacao(usuario: dict, pagamentos: list[dict] | None = None, leituras: list[dict] | None = None) -> dict:
    pagamentos = pagamentos if pagamentos is not None else db_client.listar_registros(
        "payments",
        select="payment_id,status,amount,valor,created_at",
        filtros=f"user_id=eq.{usuario['user_id']}",
        limit=200,
        order="created_at.desc",
    )
    leituras = leituras if leituras is not None else db_client.listar_registros(
        "readings",
        select="reading_id,user_id,created_at,criado_em",
        filtros=f"user_id=eq.{usuario['user_id']}",
        limit=200,
        order="criado_em.desc",
    )
    aprovados = [p for p in pagamentos if p.get("status") == "approved"]
    receita = sum(float(p.get("amount") or p.get("valor") or 0) for p in aprovados)
    criado = usuario.get("created_at") or usuario.get("criado_em")
    dias_cadastro = 999
    if criado:
        try:
            dias_cadastro = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(str(criado).replace("Z", "+00:00"))).days)
        except Exception:
            pass
    ultima_interacao = usuario.get("last_login_at") or usuario.get("updated_at") or criado
    dias_inativo = 999
    if ultima_interacao:
        try:
            dias_inativo = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(str(ultima_interacao).replace("Z", "+00:00"))).days)
        except Exception:
            pass

    classes = []
    if dias_cadastro <= 7:
        classes.append("cliente_novo")
    if len(aprovados) >= 2 or len(leituras) >= 3:
        classes.append("cliente_recorrente")
    if receita >= float(os.getenv("CRM_VIP_MIN_REVENUE", "100")) or len(aprovados) >= 5:
        classes.append("cliente_vip")
    if dias_inativo >= int(os.getenv("CRM_INACTIVE_DAYS", "30")):
        classes.append("cliente_inativo")
    if not classes:
        classes.append("cliente_em_observacao")
    return {
        "classes": classes,
        "receita_aprovada": receita,
        "pagamentos_aprovados": len(aprovados),
        "leituras_total": len(leituras),
        "dias_desde_cadastro": dias_cadastro,
        "dias_inativo": dias_inativo,
    }


def crm_default_segmentos() -> list[dict]:
    return [
        {"name": "Cliente novo", "description": "Cadastro recente, precisa de boas-vindas guiada.", "rules": {"class": "cliente_novo"}},
        {"name": "Cliente recorrente", "description": "Ja comprou ou consultou mais de uma vez.", "rules": {"class": "cliente_recorrente"}},
        {"name": "Cliente VIP", "description": "Alto valor ou alta frequencia de compra.", "rules": {"class": "cliente_vip"}},
        {"name": "Cliente inativo", "description": "Sem interacao recente e elegivel para reativacao.", "rules": {"class": "cliente_inativo"}},
    ]
