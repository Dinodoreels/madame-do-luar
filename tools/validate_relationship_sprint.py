"""
Valida a Sprint 3 - Relacionamento.

Cobertura:
- WhatsApp configurado e envio real/simulado explicito pelo provedor ativo.
- `notification_logs` recebe registro do envio.
- automacao de boas-vindas agenda e processa evento WhatsApp.
- automacao de retorno 24h agenda evento apos uma leitura/pergunta.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

import automation_engine
import db_client
from notificacoes import whatsapp_configurado


def _require_env() -> None:
    load_dotenv()
    missing = []
    for key in ("WHATSAPP_API_URL", "WHATSAPP_API_TOKEN", "WHATSAPP_TEST_NUMBER"):
        if not os.getenv(key):
            missing.append(key)
    if missing:
        raise SystemExit("Variaveis WhatsApp ausentes no .env: " + ", ".join(missing))
    if not whatsapp_configurado():
        raise SystemExit("WhatsApp nao esta completamente configurado para o provedor ativo.")


def _create_user() -> dict:
    email = f"relacionamento-{uuid.uuid4().hex[:8]}@madamedoluar.test"
    result = db_client.criar_usuario(
        nome="Teste Relacionamento",
        email=email,
        senha="TesteRelacionamento123!",
        whatsapp=os.getenv("WHATSAPP_TEST_NUMBER"),
        whatsapp_opt_in=True,
        email_opt_in=False,
        terms_accepted=True,
        privacy_accepted=True,
        ai_notice_accepted=True,
    )
    if "erro" in result:
        raise SystemExit(result["erro"])
    return result["usuario"]


def _must_have_event(events: list[dict], tipo: str, canal: str) -> dict:
    for event in events:
        if event.get("tipo") == tipo and event.get("canal") == canal and not event.get("erro"):
            return event
    raise SystemExit(f"Evento {tipo}/{canal} nao foi agendado: {events}")


def _notification_log_for(message_id: str) -> dict:
    logs = db_client.listar_registros(
        "notification_logs",
        select="*",
        filtros=f"message_event_id=eq.{message_id}",
        limit=5,
        order="created_at.desc",
    )
    if not logs:
        raise SystemExit(f"notification_logs nao registrou message_event_id={message_id}")
    return logs[0]


def main() -> None:
    _require_env()
    rules = automation_engine.sincronizar_regras_padrao()
    if rules.get("skipped"):
        raise SystemExit(f"Regras de automacao nao sincronizadas: {rules}")

    user = _create_user()
    welcome_events = automation_engine.agendar_boas_vindas(user)
    welcome_whatsapp = _must_have_event(welcome_events, "welcome", "whatsapp")
    processed = automation_engine.processar_evento(welcome_whatsapp)
    if not processed.get("sent"):
        raise SystemExit(f"Boas-vindas WhatsApp nao enviada: {processed}")

    welcome_log = _notification_log_for(welcome_whatsapp["message_id"])
    if welcome_log.get("status") not in {"sent", "simulated"}:
        raise SystemExit(f"notification_logs registrou status inesperado: {welcome_log.get('status')}")

    question_id = db_client.insert_question(
        user["user_id"],
        "Como posso fortalecer minha energia nas proximas 24 horas?",
        tema="relacionamento_sprint_3",
    )
    if not question_id:
        raise SystemExit("Nao foi possivel criar pergunta de teste.")

    retorno_events = automation_engine.agendar_retorno_leitura(user["user_id"], question_id)
    retorno_24h = _must_have_event(retorno_events, "24h", "whatsapp")

    db_client.registrar_log(
        "RELATIONSHIP_SPRINT_VALIDATED",
        "Sprint 3 de relacionamento validada.",
        user_id=user["user_id"],
        metadata={
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "welcome_message_id": welcome_whatsapp["message_id"],
            "welcome_log_id": welcome_log.get("log_id"),
            "retorno_24h_message_id": retorno_24h["message_id"],
            "rules": rules,
        },
    )

    print("OK Sprint 3 relacionamento validada.")
    print(f"Usuario: {user['user_id']}")
    print(f"WhatsApp welcome: {welcome_whatsapp['message_id']} -> {processed['status']}")
    print(f"Notification log: {welcome_log.get('log_id')} / {welcome_log.get('status')}")
    print(f"Retorno 24h WhatsApp: {retorno_24h['message_id']} / {retorno_24h.get('status')}")
    print(f"Regras sincronizadas: rules={rules.get('rules')} steps={rules.get('steps')}")


if __name__ == "__main__":
    main()
