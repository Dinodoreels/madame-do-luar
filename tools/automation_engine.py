import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from dotenv import load_dotenv

import db_client
from notificacoes import destinatario_email, enviar_email, enviar_whatsapp_result

try:
    from app.modules.analytics.use_cases import track_server_event
except Exception:
    def track_server_event(*args, **kwargs):
        return None


load_dotenv()

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

DEFAULT_AUTOMATION_RULES = [
    {
        "name": "Boas-vindas",
        "event_type": "welcome",
        "steps": [
            {"delay_minutes": 0, "channel": "email", "subject": "Bem-vinda ao Portal da Madame do Luar"},
            {"delay_minutes": 0, "channel": "whatsapp", "subject": "Bem-vinda ao Madame do Luar"},
        ],
    },
    {
        "name": "Retorno pos leitura",
        "event_type": "reading_completed",
        "steps": [
            {"delay_minutes": 24 * 60, "channel": "email", "subject": SUBJECTS["24h"] if "SUBJECTS" in globals() else "Sua leitura ainda esta ecoando"},
            {"delay_minutes": 24 * 60, "channel": "whatsapp", "subject": "Sua leitura ainda esta ecoando"},
            {"delay_minutes": 3 * 24 * 60, "channel": "email", "subject": "As cartas ainda querem conversar com voce"},
            {"delay_minutes": 7 * 24 * 60, "channel": "email", "subject": "Um novo ciclo pode estar se abrindo"},
            {"delay_minutes": 30 * 24 * 60, "channel": "email", "subject": "A Lua sentiu sua ausencia"},
        ],
    },
    {
        "name": "Carrinho abandonado",
        "event_type": "cart_abandoned",
        "steps": [
            {"delay_minutes": 15, "channel": "whatsapp", "subject": "Seu pagamento ficou pendente"},
            {"delay_minutes": 60, "channel": "email", "subject": "Seu pagamento ficou pendente"},
        ],
    },
    {
        "name": "Pos-venda",
        "event_type": "post_sale",
        "steps": [
            {"delay_minutes": 10, "channel": "whatsapp", "subject": "Seu acesso foi liberado"},
            {"delay_minutes": 24 * 60, "channel": "email", "subject": "Como foi sua experiencia?"},
        ],
    },
    {
        "name": "Recompra",
        "event_type": "repurchase",
        "steps": [
            {"delay_minutes": 14 * 24 * 60, "channel": "whatsapp", "subject": "Uma nova leitura pode clarear seu momento"},
        ],
    },
    {
        "name": "Reativacao",
        "event_type": "reactivation",
        "steps": [
            {"delay_minutes": 30 * 24 * 60, "channel": "email", "subject": "A Lua sentiu sua ausencia"},
            {"delay_minutes": 30 * 24 * 60, "channel": "whatsapp", "subject": "A Lua sentiu sua ausencia"},
        ],
    },
]

FOLLOW_UPS = {
    "24h": ("3d", timedelta(days=3)),
    "3d": ("7d", timedelta(days=7)),
    "7d": ("30d", timedelta(days=30)),
}

SUBJECTS = {
    "welcome": "Bem-vinda ao Portal da Madame do Luar",
    "24h": "Sua leitura ainda esta ecoando",
    "3d": "As cartas ainda querem conversar com voce",
    "7d": "Um novo ciclo pode estar se abrindo",
    "30d": "A Lua sentiu sua ausencia",
    "marketing": "Um recado da Madame do Luar",
    "carrinho_abandonado": "Seu pagamento ficou pendente",
    "pos_venda": "Seu acesso foi liberado",
    "recompra": "Uma nova leitura pode clarear seu momento",
    "reativacao": "A Lua sentiu sua ausencia",
    "daily_card_renewed": "Sua carta do dia foi renovada",
}

PREMIUM_WHATSAPP_OPENING = (
    "O Portal de Expansao foi aberto. Eu sou Madame do Luar, tua guia nesta travessia. "
    "Seu acesso a {{produto}} foi liberado. Pergunte com clareza o que deseja saber; "
    "respondo com verdade, cuidado e orientacao. Voce pode pedir leitura geral, amor, "
    "financas, carreira ou fazer uma pergunta direta. Que a Lua te envolva: {{link}}"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _due_at(delay: timedelta | None = None) -> str:
    return (datetime.now(timezone.utc) + (delay or timedelta())).isoformat()


def _render(template: str, variables: dict[str, Any]) -> str:
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value or ""))
    return rendered


def _base_variables(user: dict, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    variables = {
        "nome": _user_name(user),
        "email": user.get("email") or "",
        "telefone": user.get("whatsapp") or "",
        "cupom": os.getenv("DEFAULT_RETENTION_COUPON", "LUA10"),
        "link": APP_BASE_URL,
        "ultima_leitura": "sua jornada",
        "total": "",
        "produto": "sua leitura",
    }
    variables.update(extra or {})
    return variables


def _user_name(user: dict) -> str:
    return user.get("nome") or user.get("name") or "filha da Lua"


def _channels_for(user: dict) -> list[str]:
    channels = []
    if user.get("email"):
        channels.append("email")
    whatsapp_opt_in = user.get("whatsapp_opt_in")
    if user.get("whatsapp") and whatsapp_opt_in is not False:
        channels.append("whatsapp")
    return channels


def _marketing_channels_for(user: dict) -> list[str]:
    channels = []
    if user.get("email") and user.get("email_opt_in"):
        channels.append("email")
    if user.get("whatsapp") and user.get("whatsapp_opt_in"):
        channels.append("whatsapp")
    return channels


def _local_date_key() -> str:
    tz_name = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date().isoformat()


def _event_exists(user_id: str, tipo: str, canal: str, question_id: str | None = None, payment_id: str | None = None) -> bool:
    filtros = f"user_id=eq.{user_id}&tipo=eq.{tipo}&canal=eq.{canal}&status=eq.pending"
    if question_id:
        filtros += f"&question_id=eq.{question_id}"
    if payment_id:
        filtros += f"&payment_id=eq.{payment_id}"
    rows = db_client.listar_registros("message_events", select="message_id", filtros=filtros, limit=1)
    return bool(rows)


def registrar_notification_log(
    user_id: str,
    canal: str,
    tipo: str,
    status: str,
    destinatario: str | None = None,
    subject: str | None = None,
    message_id: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
    provider_response: dict[str, Any] | None = None,
) -> None:
    payload = {
        "user_id": user_id,
        "channel": canal,
        "type": tipo,
        "status": status,
        "recipient": destinatario,
        "subject": subject,
        "message_event_id": message_id,
        "error_message": error_message,
        "provider_response": provider_response or {},
        "metadata": metadata or {},
    }
    result = db_client.criar_registro("notification_logs", payload)
    if isinstance(result, dict) and "erro" in result:
        db_client.registrar_log(
            "NOTIFICATION_LOG",
            f"Notificacao {tipo}/{canal}: {status}.",
            user_id=user_id,
            metadata={**payload, "notification_log_error": result["erro"]},
            severity="error" if status == "failed" else "info",
        )


def sincronizar_regras_padrao() -> dict:
    """Cria regras/etapas padrao quando as tabelas de automacao estiverem aplicadas."""
    result = {"rules": 0, "steps": 0, "skipped": False, "errors": []}
    for rule in DEFAULT_AUTOMATION_RULES:
        existing = db_client.listar_registros(
            "automation_rules",
            select="rule_id,name",
            filtros=f"name=eq.{rule['name']}",
            limit=1,
        )
        if isinstance(existing, dict) and existing.get("erro"):
            result["skipped"] = True
            result["errors"].append(existing["erro"])
            return result

        if existing:
            rule_id = existing[0]["rule_id"]
        else:
            created = db_client.criar_registro(
                "automation_rules",
                {
                    "name": rule["name"],
                    "event_type": rule["event_type"],
                    "status": "active",
                    "audience_filter": {},
                },
            )
            if isinstance(created, dict) and created.get("erro"):
                result["skipped"] = True
                result["errors"].append(created["erro"])
                return result
            rule_id = created["rule_id"]
            result["rules"] += 1

        existing_steps = db_client.listar_registros(
            "automation_steps",
            select="step_id",
            filtros=f"rule_id=eq.{rule_id}",
            limit=50,
        )
        if existing_steps:
            continue
        for index, step in enumerate(rule["steps"], start=1):
            created_step = db_client.criar_registro(
                "automation_steps",
                {
                    "rule_id": rule_id,
                    "step_order": index,
                    "delay_minutes": step["delay_minutes"],
                    "channel": step["channel"],
                    "subject": step.get("subject"),
                    "template": step.get("template") or "{{nome}}, acesse o portal: {{link}}",
                    "status": "active",
                },
            )
            if isinstance(created_step, dict) and created_step.get("erro"):
                result["errors"].append(created_step["erro"])
            else:
                result["steps"] += 1
    return result


def agendar_evento(
    user_id: str,
    tipo: str,
    canal: str,
    delay: timedelta | None = None,
    question_id: str | None = None,
    payment_id: str | None = None,
    mensagem: str | None = None,
    subject: str | None = None,
    variables: dict[str, Any] | None = None,
    max_attempts: int | None = None,
) -> dict:
    if canal not in ("email", "whatsapp"):
        return {"erro": "Canal invalido."}
    if _event_exists(user_id, tipo, canal, question_id, payment_id):
        return {"ok": True, "duplicado": True, "tipo": tipo, "canal": canal}
    payload = {
        "user_id": user_id,
        "question_id": question_id,
        "payment_id": payment_id,
        "tipo": tipo,
        "canal": canal,
        "subject": subject,
        "mensagem": mensagem,
        "variables": variables or {},
        "status": "pending",
        "agendado_para": _due_at(delay),
    }
    if max_attempts is not None:
        payload["max_attempts"] = max(1, int(max_attempts))
    evento = db_client.criar_registro("message_events", payload)
    return evento if "erro" not in evento else {"erro": evento["erro"], "payload": payload}


def agendar_boas_vindas(user: dict) -> list[dict]:
    variables = _base_variables(user)
    templates = {
        "email": (
            "Saudacoes, {{nome}}!\n\n"
            "Sua conta foi criada com sucesso. Entre no portal e faca sua primeira consulta gratuita.\n\n"
            "Acesse: {{link}}\n\nQue a Lua ilumine seu caminho.\nMadame do Luar"
        ),
        "whatsapp": (
            "Ola, {{nome}}. Sua conta no Madame do Luar foi criada. "
            "Sua primeira consulta gratuita ja esta esperando: {{link}}"
        ),
    }
    return [
        agendar_evento(user["user_id"], "welcome", canal, mensagem=_render(templates[canal], variables))
        for canal in _channels_for(user)
    ]


def agendar_retorno_leitura(user_id: str, question_id: str | None = None) -> list[dict]:
    user = db_client.get_user_by_id(user_id) or {}
    question = _question_text(question_id)
    scheduled = []
    for canal in _channels_for(user):
        for tipo, delay in (
            ("24h", timedelta(hours=24)),
            ("3d", timedelta(days=3)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
        ):
            scheduled.append(
                agendar_evento(
                    user_id,
                    tipo,
                    canal,
                    delay=delay,
                    question_id=question_id,
                    variables=_base_variables(user, {"ultima_leitura": question}),
                )
            )
    return scheduled


def agendar_pix_abandonado(payment: dict) -> list[dict]:
    user = db_client.get_user_by_id(payment.get("user_id")) or {}
    amount = payment.get("amount") or payment.get("valor") or 0
    variables = _base_variables(user, {
        "produto": payment.get("product_name") or payment.get("tipo") or "sua leitura",
        "total": amount,
    })
    message = _render(
        "{{nome}}, seu PIX de {{produto}} ficou pendente. "
        "Se ainda fizer sentido para voce, conclua pelo portal: {{link}}",
        variables,
    )
    return [
        agendar_evento(
            payment["user_id"],
            "carrinho_abandonado",
            canal,
            delay=timedelta(minutes=15),
            payment_id=payment.get("payment_id"),
            mensagem=message,
            variables=variables,
        )
        for canal in _channels_for(user)
    ]


def agendar_pos_venda(payment: dict) -> list[dict]:
    user = db_client.get_user_by_id(payment.get("user_id")) or {}
    variables = _base_variables(user, {
        "produto": payment.get("product_name") or payment.get("tipo") or "sua leitura",
        "total": payment.get("amount") or payment.get("valor") or "",
    })
    return [
        agendar_evento(
            payment["user_id"],
            "pos_venda",
            canal,
            delay=timedelta(minutes=10),
            payment_id=payment.get("payment_id"),
            variables=variables,
        )
        for canal in _channels_for(user)
    ]


def agendar_recompra(user_id: str, delay_days: int = 14) -> list[dict]:
    user = db_client.get_user_by_id(user_id) or {}
    return [
        agendar_evento(
            user_id,
            "recompra",
            canal,
            delay=timedelta(days=delay_days),
            variables=_base_variables(user),
        )
        for canal in _channels_for(user)
    ]


def agendar_reativacao(user_id: str, delay_days: int = 30) -> list[dict]:
    user = db_client.get_user_by_id(user_id) or {}
    return [
        agendar_evento(
            user_id,
            "reativacao",
            canal,
            delay=timedelta(days=delay_days),
            variables=_base_variables(user),
        )
        for canal in _channels_for(user)
    ]


def _daily_card_notice_exists(user_id: str, canal: str, date_key: str) -> bool:
    try:
        rows = db_client.listar_registros(
            "message_events",
            select="message_id,variables,created_at,status",
            filtros=f"user_id=eq.{user_id}&tipo=eq.marketing&canal=eq.{canal}",
            limit=80,
            order="created_at.desc",
        )
    except Exception:
        return False
    if isinstance(rows, dict) and rows.get("erro"):
        return False
    for row in rows or []:
        variables = row.get("variables") if isinstance(row.get("variables"), dict) else {}
        if variables.get("campaign") == "daily_card_renewed" and variables.get("daily_date") == date_key:
            return True
    return False


def agendar_carta_do_dia_renovada(user: dict, date_key: str | None = None) -> list[dict]:
    date_key = date_key or _local_date_key()
    user_id = user.get("user_id")
    if not user_id or user.get("status") == "bloqueado":
        return []

    variables = _base_variables(
        user,
        {
            "campaign": "daily_card_renewed",
            "daily_date": date_key,
            "produto": "carta do dia",
        },
    )
    message = _render(
        "{{nome}}, sua carta do dia foi renovada no Madame do Luar. "
        "Entre no portal para receber a orientacao de hoje: {{link}}",
        variables,
    )
    scheduled = []
    for canal in _marketing_channels_for(user):
        if _daily_card_notice_exists(user_id, canal, date_key):
            scheduled.append({"ok": True, "duplicado": True, "tipo": "daily_card_renewed", "canal": canal})
            continue
        scheduled.append(
            agendar_evento(
                user_id,
                "marketing",
                canal,
                mensagem=message,
                subject=SUBJECTS["daily_card_renewed"],
                variables=variables,
                max_attempts=2,
            )
        )
    return scheduled


def agendar_cartas_do_dia_renovadas(limit: int = 1000, dry_run: bool = False) -> dict:
    date_key = _local_date_key()
    try:
        users = db_client.listar_registros(
            "users",
            select="user_id,nome,email,whatsapp,email_opt_in,whatsapp_opt_in,status",
            limit=limit,
            order="criado_em.desc",
        )
    except Exception as exc:
        return {"erro": f"Falha ao listar usuarios para campanha diaria: {exc}", "date": date_key}
    if isinstance(users, dict) and users.get("erro"):
        return {"erro": users["erro"], "date": date_key}

    result = {"date": date_key, "usuarios": 0, "agendados": 0, "duplicados": 0, "sem_opt_in": 0, "eventos": []}
    for user in users or []:
        if user.get("status") in ("bloqueado", "inativo"):
            continue
        channels = _marketing_channels_for(user)
        if not channels:
            result["sem_opt_in"] += 1
            continue
        result["usuarios"] += 1
        if dry_run:
            result["eventos"].append({"user_id": user.get("user_id"), "channels": channels, "dry_run": True})
            continue
        for item in agendar_carta_do_dia_renovada(user, date_key=date_key):
            if item.get("duplicado"):
                result["duplicados"] += 1
            elif item.get("erro"):
                result["eventos"].append(item)
            else:
                result["agendados"] += 1
                result["eventos"].append({"message_id": item.get("message_id"), "canal": item.get("canal")})
    return result


def _question_text(question_id: str | None) -> str:
    if not question_id:
        return "sua jornada"
    row = db_client.buscar_por_id("questions", "question_id", question_id, select="pergunta")
    return (row or {}).get("pergunta") or "sua jornada"


def _message_for_event(evento: dict, user: dict) -> tuple[str, str]:
    tipo = evento.get("tipo") or "marketing"
    subject = evento.get("subject") or SUBJECTS.get(tipo, SUBJECTS["marketing"])
    stored_variables = evento.get("variables") if isinstance(evento.get("variables"), dict) else {}
    variables = _base_variables(
        user,
        {
            **stored_variables,
            "ultima_leitura": stored_variables.get("ultima_leitura") or _question_text(evento.get("question_id")),
        },
    )
    if variables.get("campaign") == "daily_card_renewed":
        return SUBJECTS["daily_card_renewed"], _render(
            "{{nome}}, sua carta do dia foi renovada no Madame do Luar. "
            "Entre no portal para receber a orientacao de hoje: {{link}}",
            variables,
        )
    if evento.get("mensagem"):
        return subject, _render(evento["mensagem"], variables)
    if tipo == "pos_venda" and evento.get("canal") == "whatsapp":
        return subject, _render(PREMIUM_WHATSAPP_OPENING, variables)

    templates = {
        "welcome": (
            "Ola, {{nome}}. Sua conta no Madame do Luar foi criada. "
            "Sua primeira consulta gratuita ja esta esperando: {{link}}"
        ),
        "24h": (
            "{{nome}}, ontem as cartas tocaram em \"{{ultima_leitura}}\". "
            "Volte ao portal para continuar esse fio de resposta: {{link}}"
        ),
        "3d": (
            "{{nome}}, tres dias se passaram desde sua leitura. "
            "Talvez agora a resposta esteja mais clara. Volte quando sentir: {{link}}"
        ),
        "7d": (
            "{{nome}}, uma semana muda muita energia. "
            "Se quiser uma nova orientacao, o portal esta aberto: {{link}}"
        ),
        "30d": (
            "{{nome}}, faz um ciclo inteiro que nao nos encontramos. "
            "Quando quiser reabrir as cartas, estou aqui: {{link}}"
        ),
        "carrinho_abandonado": (
            "{{nome}}, seu pagamento de {{produto}} ficou pendente. "
            "Finalize pelo portal quando quiser continuar: {{link}}"
        ),
        "pos_venda": (
            "{{nome}}, seu acesso a {{produto}} foi liberado. "
            "Entre no portal e aproveite sua experiencia: {{link}}"
        ),
        "recompra": (
            "{{nome}}, talvez seja hora de uma nova leitura. "
            "Use {{cupom}} se ele ainda estiver disponivel e volte pelo portal: {{link}}"
        ),
        "reativacao": (
            "{{nome}}, a Lua sentiu sua ausencia. "
            "Quando quiser retomar sua jornada, seu portal esta aqui: {{link}}"
        ),
        "marketing": "{{nome}}, a Madame do Luar tem um novo recado para voce: {{link}}",
    }
    return subject, _render(templates.get(tipo, templates["marketing"]), variables)


def _send(canal: str, user: dict, subject: str, message: str) -> tuple[bool, str | None, dict[str, Any]]:
    if canal == "email":
        recipient = user.get("email")
        if not recipient:
            return False, "Usuario sem e-mail.", {}
        return enviar_email(recipient, subject, message), destinatario_email(recipient), {}
    if canal == "whatsapp":
        recipient = user.get("whatsapp")
        if not recipient:
            return False, "Usuario sem WhatsApp.", {}
        if user.get("whatsapp_opt_in") is False:
            return False, "Usuario sem opt-in de WhatsApp.", {}
        result = enviar_whatsapp_result(recipient, message)
        return bool(result.get("ok")), result.get("recipient") or recipient, result
    return False, "Canal invalido.", {}


def _patch_event(message_id: str, status: str, message: str | None = None, error: str | None = None) -> None:
    payload = {"status": status, "updated_at": _now_iso()}
    if status == "sent":
        payload["enviado_em"] = _now_iso()
    if message:
        payload["mensagem"] = message
    if error:
        payload["error_message"] = error[:500]
    db_client.atualizar_registro("message_events", "message_id", message_id, payload)


def _mark_processing(evento: dict) -> int:
    attempts = int(evento.get("attempts") or 0) + 1
    db_client.atualizar_registro(
        "message_events",
        "message_id",
        evento["message_id"],
        {"status": "processing", "attempts": attempts, "updated_at": _now_iso()},
    )
    return attempts


def _schedule_retry_or_fail(evento: dict, attempts: int, error: str | None) -> str:
    max_attempts = int(evento.get("max_attempts") or 3)
    if attempts < max_attempts:
        delay_minutes = int(os.getenv("AUTOMATION_RETRY_DELAY_MINUTES", "15"))
        db_client.atualizar_registro(
            "message_events",
            "message_id",
            evento["message_id"],
            {
                "status": "pending",
                "error_message": (error or "Falha no envio; reenvio agendado.")[:500],
                "agendado_para": _due_at(timedelta(minutes=delay_minutes)),
                "updated_at": _now_iso(),
            },
        )
        return "retry_scheduled"
    _patch_event(evento["message_id"], "failed", error=error or "Falha definitiva no envio.")
    return "failed"


def processar_evento(evento: dict, dry_run: bool = False) -> dict:
    message_id = evento["message_id"]
    user = db_client.get_user_by_id(evento.get("user_id")) or {}
    subject, message = _message_for_event(evento, user)
    if dry_run:
        return {
            "message_id": message_id,
            "status": "dry_run",
            "canal": evento.get("canal"),
            "tipo": evento.get("tipo"),
            "subject": subject,
        }

    attempts = _mark_processing(evento)
    ok, recipient_or_error, provider_result = _send(evento.get("canal"), user, subject, message)
    notification_status = provider_result.get("status") if provider_result else ("sent" if ok else "failed")
    status = "sent" if ok else _schedule_retry_or_fail(evento, attempts, recipient_or_error)
    if ok:
        _patch_event(message_id, "sent", message=message)
    registrar_notification_log(
        user_id=evento.get("user_id"),
        canal=evento.get("canal"),
        tipo=evento.get("tipo"),
        status=notification_status if notification_status in ("sent", "failed", "skipped", "simulated") else status,
        destinatario=recipient_or_error if ok else None,
        subject=subject,
        message_id=message_id,
        error_message=None if ok else recipient_or_error,
        provider_response=provider_result.get("provider_response") if provider_result else {},
        metadata={
            "question_id": evento.get("question_id"),
            "provider": provider_result.get("provider") if provider_result else None,
            "attempts": attempts,
            "event_status": status,
        },
    )
    if ok and evento.get("tipo") in FOLLOW_UPS:
        next_tipo, delay = FOLLOW_UPS[evento["tipo"]]
        agendar_evento(
            evento["user_id"],
            next_tipo,
            evento["canal"],
            delay=delay,
            question_id=evento.get("question_id"),
        )
    track_server_event(
        "automation_sent" if ok else "automation_failed",
        user_id=evento.get("user_id"),
        entity_type="message_events",
        entity_id=message_id,
        metadata={
            "tipo": evento.get("tipo"),
            "canal": evento.get("canal"),
            "status": status,
            "attempts": attempts,
            "provider": provider_result.get("provider") if provider_result else None,
            "error": None if ok else recipient_or_error,
        },
        source="worker",
    )
    return {"message_id": message_id, "status": status, "sent": ok, "attempts": attempts}


def processar_pendentes(limit: int = 100, dry_run: bool = False) -> dict:
    due = datetime.now(timezone.utc).isoformat()
    eventos = db_client.listar_registros(
        "message_events",
        select="*",
        filtros=f"status=eq.pending&agendado_para=lte.{due}",
        limit=limit,
        order="agendado_para.asc",
    )
    resultado = {"processados": 0, "enviados": 0, "falhas": 0, "eventos": []}

    for evento in eventos:
        processed = processar_evento(evento, dry_run=dry_run)
        resultado["processados"] += 1
        if dry_run:
            resultado["eventos"].append(processed)
            continue
        resultado["enviados" if processed.get("sent") else "falhas"] += 1
        resultado["eventos"].append({"message_id": processed["message_id"], "status": processed["status"]})

    return resultado


if __name__ == "__main__":
    print(processar_pendentes())
