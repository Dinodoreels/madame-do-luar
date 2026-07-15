from datetime import datetime, timezone
from typing import Optional

from .repository import UsersRepository


repository = UsersRepository()


def contar_registros(tabela: str, filtro: str = "") -> int:
    return repository.count(tabela, filtro)


def buscar_assinatura_ativa(user_id: str) -> Optional[dict]:
    return repository.active_subscription(user_id)


def montar_resumo_perfil(usuario: dict) -> dict:
    user_id = usuario["user_id"]
    assinatura = buscar_assinatura_ativa(user_id)
    return {
        "usuario": usuario,
        "assinatura": assinatura,
        "metricas": {
            "leituras": contar_registros("questions", f"user_id=eq.{user_id}"),
            "cartas_do_dia": contar_registros("daily_cards", f"user_id=eq.{user_id}"),
            "mensagens": contar_registros("message_events", f"user_id=eq.{user_id}"),
            "mensagens_pendentes": contar_registros("message_events", f"user_id=eq.{user_id}&status=eq.pending"),
            "pagamentos_aprovados": contar_registros("payments", f"user_id=eq.{user_id}&status=eq.approved"),
        },
    }


def listar_leituras_usuario(usuario: dict, limit: int = 50) -> dict:
    user_id = usuario["user_id"]
    perguntas = repository.questions.list(
        select="question_id,user_id,pergunta,tema,emocao,criado_em",
        filters=f"user_id=eq.{user_id}",
        limit=min(max(limit, 1), 200),
        order="criado_em.desc",
    )
    return {"readings": perguntas}


def export_payload(dados: dict) -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": "json",
        "data": dados,
    }
