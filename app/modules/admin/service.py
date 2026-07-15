from typing import Optional

import requests as http
from fastapi import HTTPException

import db_client


def contar_registros(tabela: str, filtro: str = "") -> int:
    try:
        url, headers = db_client.get_supabase_headers()
        r = http.get(
            f"{url}/rest/v1/{tabela}?select=*&{filtro}" if filtro else f"{url}/rest/v1/{tabela}?select=*",
            headers={**headers, "Prefer": "count=exact"},
            timeout=10,
        )
        return int(r.headers.get("content-range", "0/0").split("/")[-1])
    except Exception:
        return 0


def buscar_assinatura_ativa(user_id: str) -> Optional[dict]:
    try:
        url, headers = db_client.get_supabase_headers()
        r = http.get(
            f"{url}/rest/v1/subscriptions"
            f"?user_id=eq.{user_id}&status=eq.ativo&order=renovacao.desc&limit=1&select=*",
            headers=headers,
            timeout=10,
        )
        data = r.json()
        return data[0] if isinstance(data, list) and data else None
    except Exception:
        return None


def validar_status_ativo(status: Optional[str]):
    if status is not None and status not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="Status invalido.")


def enriquecer_leituras_admin(leituras: list[dict]) -> list[dict]:
    question_ids = sorted({r.get("question_id") for r in leituras if r.get("question_id")})
    if not question_ids:
        return leituras

    questions = db_client.listar_registros(
        "questions",
        select="question_id,user_id,pergunta,tema,criado_em,created_at",
        filtros=f"question_id=in.({','.join(question_ids)})",
        limit=max(len(question_ids), 1),
    )
    question_map = {q.get("question_id"): q for q in questions if q.get("question_id")}

    user_ids = sorted({q.get("user_id") for q in questions if q.get("user_id")})
    users = db_client.listar_registros(
        "users",
        select="user_id,nome,email,whatsapp,status,role",
        filtros=f"user_id=in.({','.join(user_ids)})",
        limit=max(len(user_ids), 1),
    ) if user_ids else []
    user_map = {u.get("user_id"): u for u in users if u.get("user_id")}

    for leitura in leituras:
        pergunta = question_map.get(leitura.get("question_id")) or {}
        usuario = user_map.get(pergunta.get("user_id")) or {}
        if pergunta:
            leitura["question"] = pergunta
            leitura["pergunta"] = leitura.get("pergunta") or pergunta.get("pergunta")
            leitura["tema"] = leitura.get("tema") or pergunta.get("tema")
            leitura["user_id"] = leitura.get("user_id") or pergunta.get("user_id")
        if usuario:
            leitura["usuario"] = usuario
    return leituras


def validar_coupon(discount_type: Optional[str], discount_value: Optional[float]):
    if discount_type is not None and discount_type not in ("percent", "fixed"):
        raise HTTPException(status_code=400, detail="Tipo de desconto invalido.")
    if discount_value is not None and discount_value < 0:
        raise HTTPException(status_code=400, detail="Valor de desconto invalido.")
    if discount_type == "percent" and discount_value is not None and discount_value > 100:
        raise HTTPException(status_code=400, detail="Desconto percentual nao pode passar de 100.")


def validar_applies_to(applies_to: Optional[str]):
    if applies_to and applies_to not in ("all", "package", "plan", "ritual", "reading"):
        raise HTTPException(status_code=400, detail="Aplicacao do cupom invalida.")
