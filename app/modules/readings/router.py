from datetime import date

import requests as http
from fastapi import APIRouter, Depends, HTTPException

import automation_engine
import db_client
from app.core.errors import erro_http
from app.core.security import usuario_atual
from app.modules.analytics.use_cases import track_server_event
from app.modules.automation.job_queue import job_queue_service
from app.modules.users.service import listar_leituras_usuario

from .schemas import CartaDoDiaRequest, LeituraRequest
from .service import extrair_simbolo, gemini_model, gerar_carta_do_dia, gerar_interpretacao, sanitize_question, sortear_cartas


router = APIRouter(tags=["readings"])


@router.post("/api/carta-do-dia")
async def carta_do_dia(body: CartaDoDiaRequest, usuario: dict = Depends(usuario_atual)):
    user_id = usuario["user_id"]
    track_server_event("daily_card_started", user_id=user_id)
    if db_client.has_daily_card_today(user_id):
        url, headers = db_client.get_supabase_headers()
        hoje = str(date.today())
        r = http.get(f"{url}/rest/v1/daily_cards?user_id=eq.{user_id}&criado_em=eq.{hoje}&select=*&limit=1", headers=headers)
        data = r.json()
        if data:
            card = data[0]
            track_server_event("daily_card_completed", user_id=user_id, entity_type="daily_cards", entity_id=card.get("daily_card_id"), metadata={"carta": card.get("carta"), "ja_tirou": True})
            return {
                "carta": card["carta"],
                "invertida": card["inverted"],
                "simbolo": extrair_simbolo(card["carta"]),
                "mensagem": card["mensagem"],
                "ja_tirou": True,
            }

    carta = sortear_cartas(1)[0]
    try:
        mensagem = gerar_carta_do_dia(carta)
    except Exception as exc:
        db_client.registrar_log(
            "AI_ERROR",
            "Falha de IA ao gerar carta do dia.",
            user_id=user_id,
            metadata={"carta": carta.get("nome"), "erro": str(exc)[:500]},
            severity="error",
        )
        raise erro_http(503, "AI_UNAVAILABLE", "A IA esta indisponivel para gerar a carta do dia. Tente novamente em instantes.")

    db_client.insert_daily_card(user_id, carta["nome"], carta["invertida"], mensagem)
    track_server_event("daily_card_completed", user_id=user_id, entity_type="daily_cards", metadata={"carta": carta["nome"], "ja_tirou": False})
    return {"carta": carta["nome"], "invertida": carta["invertida"], "simbolo": extrair_simbolo(carta["nome"]), "mensagem": mensagem, "ja_tirou": False}


@router.post("/readings")
@router.post("/api/readings")
@router.post("/api/leitura")
async def leitura(body: LeituraRequest, usuario: dict = Depends(usuario_atual)):
    pergunta = sanitize_question(body.pergunta or body.question or body.mensagem or "")
    user_id = usuario["user_id"]
    tipo_leitura = (body.tipo or body.tipo_leitura or body.reading_type or "tres_cartas").strip().lower()
    primeira_gratis = bool(usuario.get("primeira_tiragem_gratis"))
    custo_creditos = 0 if primeira_gratis else db_client.obter_custo_leitura(tipo_leitura)
    consumo_credito = None

    if custo_creditos > 0:
        consumo_credito = db_client.consumir_creditos(user_id=user_id, amount=custo_creditos, reason=f"Consumo de leitura: {tipo_leitura}")
        if "erro" in consumo_credito:
            track_server_event("credits_insufficient", user_id=user_id, metadata={"tipo": tipo_leitura, "custo_creditos": custo_creditos, "erro": consumo_credito.get("erro")})
            db_client.registrar_log(
                "READING_FAILED",
                "Leitura recusada por saldo insuficiente ou falha ao consumir creditos.",
                user_id=user_id,
                metadata={"tipo": tipo_leitura, "custo_creditos": custo_creditos, "erro": consumo_credito.get("erro")},
                severity="warning",
            )
            raise HTTPException(status_code=402, detail=consumo_credito.get("erro") or "Creditos insuficientes.")

    question_id = db_client.insert_question(user_id, pergunta, tema=tipo_leitura)
    track_server_event("reading_started", user_id=user_id, entity_type="questions", entity_id=question_id, metadata={"tipo": tipo_leitura, "custo_creditos": custo_creditos, "primeira_gratis": primeira_gratis})
    if not question_id:
        if custo_creditos > 0:
            db_client.estornar_creditos(user_id, custo_creditos, "Estorno: falha ao registrar pergunta")
        raise HTTPException(status_code=500, detail="Nao foi possivel registrar a pergunta.")

    cartas = sortear_cartas(3)
    c_passado, c_presente, c_futuro = cartas[0], cartas[1], cartas[2]

    try:
        track_server_event("reading_ai_started", user_id=user_id, entity_type="questions", entity_id=question_id, metadata={"tipo": tipo_leitura})
        interpretacao = gerar_interpretacao(pergunta, [c_passado, c_presente, c_futuro])
    except Exception as exc:
        erro_msg = str(exc)[:500]
        reading_erro = db_client.insert_reading(
            question_id=question_id,
            cartas={"passado": c_passado, "presente": c_presente, "futuro": c_futuro},
            interpretacao="Falha ao gerar interpretacao com IA.",
            model=gemini_model(),
            status="erro",
            error_message=erro_msg,
        )
        reading_id = reading_erro.get("reading_id") if isinstance(reading_erro, dict) else None
        if custo_creditos > 0:
            db_client.estornar_creditos(user_id=user_id, amount=custo_creditos, reason="Estorno automatico: IA falhou antes de entregar leitura.", related_reading_id=reading_id)
            if consumo_credito and consumo_credito.get("transaction_id"):
                db_client.vincular_transacao_credito(consumo_credito["transaction_id"], related_reading_id=reading_id)
        db_client.registrar_log(
            "READING_FAILED",
            "Falha de IA durante leitura; creditos estornados quando aplicavel.",
            user_id=user_id,
            metadata={"tipo": tipo_leitura, "question_id": question_id, "reading_id": reading_id, "erro": erro_msg},
            severity="error",
        )
        track_server_event("reading_ai_failed", user_id=user_id, entity_type="readings", entity_id=reading_id, metadata={"tipo": tipo_leitura, "question_id": question_id, "erro": erro_msg})
        raise erro_http(503, "AI_READING_FAILED", "A IA falhou ao gerar a leitura. Seus creditos foram preservados.", {"reading_id": reading_id, "question_id": question_id})

    reading = db_client.insert_reading(
        question_id=question_id,
        cartas={"passado": c_passado, "presente": c_presente, "futuro": c_futuro},
        interpretacao=interpretacao,
        model=gemini_model(),
        status="concluida",
    )
    reading_id = reading.get("reading_id") if isinstance(reading, dict) else None

    if custo_creditos > 0 and consumo_credito and consumo_credito.get("transaction_id"):
        db_client.vincular_transacao_credito(consumo_credito["transaction_id"], related_reading_id=reading_id)
    if primeira_gratis:
        db_client.marcar_primeira_tiragem_usada(user_id)

    db_client.registrar_log(
        "READING_CREATED",
        "Leitura criada com sucesso.",
        user_id=user_id,
        metadata={"tipo": tipo_leitura, "question_id": question_id, "reading_id": reading_id, "custo_creditos": custo_creditos, "primeira_gratis": primeira_gratis},
    )
    track_server_event("reading_completed", user_id=user_id, entity_type="readings", entity_id=reading_id, metadata={"tipo": tipo_leitura, "question_id": question_id, "custo_creditos": custo_creditos, "primeira_gratis": primeira_gratis})
    try:
        automation_engine.agendar_retorno_leitura(user_id, question_id)
    except Exception as exc:
        db_client.registrar_log("AUTOMATION_SCHEDULE_FAILED", "Nao foi possivel agendar retorno automatico de leitura.", user_id=user_id, metadata={"question_id": question_id, "erro": str(exc)}, severity="warning")

    return {
        "cartas": [
            {"posicao": "passado", "nome": c_passado["nome"], "invertida": c_passado["invertida"], "simbolo": extrair_simbolo(c_passado["nome"])},
            {"posicao": "presente", "nome": c_presente["nome"], "invertida": c_presente["invertida"], "simbolo": extrair_simbolo(c_presente["nome"])},
            {"posicao": "futuro", "nome": c_futuro["nome"], "invertida": c_futuro["invertida"], "simbolo": extrair_simbolo(c_futuro["nome"])},
        ],
        "interpretacao": interpretacao,
        "question_id": question_id,
        "reading_id": reading_id,
        "creditos": {"cobrados": custo_creditos, "primeira_gratis": primeira_gratis, "saldo_atual": consumo_credito.get("saldo_atual") if isinstance(consumo_credito, dict) else usuario.get("credits_balance")},
    }


@router.post("/readings/enqueue")
@router.post("/api/readings/enqueue")
async def enqueue_leitura(body: LeituraRequest, usuario: dict = Depends(usuario_atual)):
    pergunta = sanitize_question(body.pergunta or body.question or body.mensagem or "")
    user_id = usuario["user_id"]
    tipo_leitura = (body.tipo or body.tipo_leitura or body.reading_type or "tres_cartas").strip().lower()
    primeira_gratis = bool(usuario.get("primeira_tiragem_gratis"))
    custo_creditos = 0 if primeira_gratis else db_client.obter_custo_leitura(tipo_leitura)
    consumo_credito = None

    if custo_creditos > 0:
        consumo_credito = db_client.consumir_creditos(user_id=user_id, amount=custo_creditos, reason=f"Consumo de leitura enfileirada: {tipo_leitura}")
        if "erro" in consumo_credito:
            track_server_event("credits_insufficient", user_id=user_id, metadata={"tipo": tipo_leitura, "custo_creditos": custo_creditos, "erro": consumo_credito.get("erro"), "queued": True})
            db_client.registrar_log(
                "READING_QUEUE_FAILED",
                "Leitura enfileirada recusada por saldo insuficiente ou falha ao consumir creditos.",
                user_id=user_id,
                metadata={"tipo": tipo_leitura, "custo_creditos": custo_creditos, "erro": consumo_credito.get("erro")},
                severity="warning",
            )
            raise HTTPException(status_code=402, detail=consumo_credito.get("erro") or "Creditos insuficientes.")

    question_id = db_client.insert_question(user_id, pergunta, tema=tipo_leitura)
    if not question_id:
        if custo_creditos > 0:
            db_client.estornar_creditos(user_id, custo_creditos, "Estorno: falha ao registrar pergunta enfileirada")
        raise HTTPException(status_code=500, detail="Nao foi possivel registrar a pergunta.")

    cartas = sortear_cartas(3)
    c_passado, c_presente, c_futuro = cartas[0], cartas[1], cartas[2]
    reading = db_client.insert_reading(
        question_id=question_id,
        cartas={"passado": c_passado, "presente": c_presente, "futuro": c_futuro},
        interpretacao="Leitura enfileirada. A interpretacao sera gerada em segundo plano.",
        model=gemini_model(),
        status="pendente",
    )
    reading_id = reading.get("reading_id") if isinstance(reading, dict) else None
    if not reading_id:
        if custo_creditos > 0:
            db_client.estornar_creditos(user_id, custo_creditos, "Estorno: falha ao criar leitura enfileirada")
        raise HTTPException(status_code=500, detail="Nao foi possivel enfileirar a leitura.")

    payload = {
        "job_kind": "ai_reading",
        "user_id": user_id,
        "question_id": question_id,
        "reading_id": reading_id,
        "pergunta": pergunta,
        "tipo": tipo_leitura,
        "cartas": {"passado": c_passado, "presente": c_presente, "futuro": c_futuro},
        "custo_creditos": custo_creditos,
        "credit_transaction_id": consumo_credito.get("transaction_id") if isinstance(consumo_credito, dict) else None,
        "primeira_gratis": primeira_gratis,
        "idempotency_key": f"ai_reading:{user_id}:{question_id}",
    }
    job = job_queue_service.enqueue("reading", payload, related_reading_id=reading_id, max_attempts=3)
    if "erro" in job:
        if custo_creditos > 0:
            db_client.estornar_creditos(user_id, custo_creditos, "Estorno: falha ao enfileirar leitura")
        db_client.atualizar_registro("readings", "reading_id", reading_id, {"status": "erro", "error_message": job["erro"]})
        raise HTTPException(status_code=500, detail=job["erro"])

    db_client.registrar_log(
        "READING_QUEUED",
        "Leitura enfileirada para processamento em segundo plano.",
        user_id=user_id,
        metadata={"queue_id": job.get("queue_id"), "question_id": question_id, "reading_id": reading_id, "tipo": tipo_leitura},
    )
    return {
        "status": "queued",
        "queue_id": job.get("queue_id"),
        "reading_id": reading_id,
        "question_id": question_id,
        "job": {"status": job.get("status"), "scheduled_at": job.get("scheduled_at"), "duplicado": bool(job.get("duplicado"))},
        "creditos": {"cobrados": custo_creditos, "primeira_gratis": primeira_gratis, "saldo_atual": consumo_credito.get("saldo_atual") if isinstance(consumo_credito, dict) else usuario.get("credits_balance")},
    }


@router.get("/readings/jobs/{queue_id}")
@router.get("/api/readings/jobs/{queue_id}")
async def reading_job_status(queue_id: str, usuario: dict = Depends(usuario_atual)):
    job = job_queue_service.job_status(queue_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de leitura nao encontrado.")
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    if payload.get("user_id") != usuario.get("user_id"):
        raise HTTPException(status_code=404, detail="Job de leitura nao encontrado.")
    reading = db_client.buscar_por_id("readings", "reading_id", job.get("related_reading_id") or payload.get("reading_id"))
    return {"job": job, "reading": reading}


@router.get("/readings/history")
@router.get("/api/readings/history")
async def readings_history(usuario: dict = Depends(usuario_atual), limit: int = 50):
    return listar_leituras_usuario(usuario, limit)


@router.get("/readings/{reading_id}")
@router.get("/api/readings/{reading_id}")
async def get_reading(reading_id: str, usuario: dict = Depends(usuario_atual)):
    reading = db_client.buscar_por_id("readings", "reading_id", reading_id)
    if not reading:
        raise HTTPException(status_code=404, detail="Leitura nao encontrada.")
    question = db_client.buscar_por_id("questions", "question_id", reading.get("question_id"))
    if not question or question.get("user_id") != usuario.get("user_id"):
        raise HTTPException(status_code=404, detail="Leitura nao encontrada.")
    return {"reading": reading, "question": question}
