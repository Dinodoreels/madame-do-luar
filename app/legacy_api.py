"""
api.py — Madame do Luar API (FastAPI)
======================================
Conecta o frontend ao backend Python.

Endpoints:
  GET  /              → health check
  GET  /status        → painel de métricas
  POST /carta-do-dia  → carta do dia para um user
  POST /leitura       → leitura de 3 cartas
  POST /cadastro      → cadastro de usuário
  POST /api/checkout  → checkout Mercado Pago
  POST /api/webhook/mercado-pago → webhook de confirmação de pagamento

Rode com:
  python api.py
  ou
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import uuid
import time
import json
import hashlib
import csv
import io
import asyncio
import requests as http
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Any, Optional
from collections import defaultdict, deque

from fastapi import FastAPI, Request, HTTPException, Header, Depends, Cookie
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Adiciona /tools ao path para importar os módulos do projeto
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))

import db_client
import automation_engine
from app.core.config import settings
from app.core.context import clean_payload, request_context
from app.core.errors import error_response, erro_http, http_code_from_status, operational_event_type
from app.core.security import (
    admin_atual,
    clear_auth_cookie,
    public_auth_payload,
    resposta_auth,
    security_headers,
    set_auth_cookie,
    token_from_request,
    usuario_atual,
    usuario_atual_opcional,
    verificar_token_acesso,
)
from app.modules.admin.router import router as admin_router
from app.modules.analytics.router import router as analytics_router
from app.modules.analytics.use_cases import track_server_event
from app.modules.auth.router import router as auth_router
from app.modules.crm.router import router as crm_router
from app.modules.payments.router import router as payments_router
from app.modules.readings.router import router as readings_router
from app.modules.rituals.router import router as rituals_router
from app.modules.users.router import router as users_router
from app.modules.users.service import listar_leituras_usuario
from app.modules.webhooks.router import router as webhooks_router
from services import AIService, DatabaseService, NotificationService, PaymentService, ReadingService, ServiceError
from sortear_cartas import sortear

# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(
    title="Madame do Luar API",
    description="Backend do SaaS de Tarot com IA",
    version="1.0.0"
)

APP_ENV = settings.app_env

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(readings_router)
app.include_router(payments_router)
app.include_router(rituals_router)
app.include_router(webhooks_router)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(crm_router)

# Diretório do frontend
frontend_dir = str(settings.frontend_dir)
media_dir = str(settings.media_dir)
video_dir = str(settings.video_dir)
logger = logging.getLogger("madame_do_luar.api")
logging.basicConfig(level=settings.log_level)

# Seguranca
RATE_LIMIT_WINDOW_SECONDS = settings.rate_limit_window_seconds
RATE_LIMIT_MAX_REQUESTS = settings.rate_limit_max_requests
RATE_LIMIT_BUCKETS = defaultdict(deque)
MAX_TAROT_QUESTION_LENGTH = settings.max_tarot_question_length
MIN_TAROT_QUESTION_LENGTH = settings.min_tarot_question_length
AUTH_COOKIE_NAME = settings.auth_cookie_name

database_service = DatabaseService()
ai_service = AIService()
payment_service = PaymentService()
notification_service = NotificationService()
reading_service = ReadingService(database_service, ai_service)

def sanitize_question(pergunta: str) -> str:
    texto = " ".join((pergunta or "").split())
    if len(texto) < MIN_TAROT_QUESTION_LENGTH:
        raise erro_http(400, "READING_QUESTION_TOO_SHORT", f"Pergunta deve ter pelo menos {MIN_TAROT_QUESTION_LENGTH} caracteres.")
    if len(texto) > MAX_TAROT_QUESTION_LENGTH:
        raise erro_http(400, "READING_QUESTION_TOO_LONG", f"Pergunta deve ter no maximo {MAX_TAROT_QUESTION_LENGTH} caracteres.")
    if not any(ch.isalpha() for ch in texto):
        raise erro_http(400, "READING_QUESTION_INVALID_CONTENT", "Pergunta deve conter texto legivel.")
    return texto


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = str(uuid.uuid4())
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code") or http_code_from_status(exc.status_code)
        message = detail.get("message") or "Erro na requisicao."
        details = detail.get("details") or {}
    else:
        code = http_code_from_status(exc.status_code)
        message = str(detail)
        details = {}

    event_type = operational_event_type(code, request.url.path)
    if exc.status_code >= 500:
        logger.error("HTTP error %s [%s]: %s", exc.status_code, request_id, message)
        try:
            db_client.registrar_log(
                event_type,
                message,
                metadata={"path": request.url.path, "method": request.method, "code": code, "request_id": request_id, "details": details},
                severity="error",
            )
        except Exception:
            pass
        track_server_event("api_error", metadata={"path": request.url.path, "method": request.method, "code": code, "request_id": request_id, "details": details})
    return error_response(exc.status_code, code, message, details, request_id, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = str(uuid.uuid4())
    details = {"errors": exc.errors()}
    try:
        db_client.registrar_log(
            "API_VALIDATION_ERROR",
            "Payload invalido recebido pela API.",
            metadata={"path": request.url.path, "method": request.method, "request_id": request_id, "errors": exc.errors()},
            severity="warning",
        )
    except Exception:
        pass
    track_server_event("api_error", metadata={"path": request.url.path, "method": request.method, "code": "VALIDATION_ERROR", "request_id": request_id, "errors": exc.errors()})
    return error_response(422, "VALIDATION_ERROR", "Payload invalido. Revise os campos enviados.", details, request_id)


@app.exception_handler(ServiceError)
async def service_exception_handler(request: Request, exc: ServiceError):
    request_id = str(uuid.uuid4())
    severity = "error" if exc.status_code >= 500 else "warning"
    try:
        db_client.registrar_log(
            operational_event_type(exc.code, request.url.path),
            exc.message,
            metadata={"path": request.url.path, "method": request.method, "code": exc.code, "request_id": request_id, "details": exc.details},
            severity=severity,
        )
    except Exception:
        pass
    if exc.status_code >= 500:
        track_server_event("api_error", metadata={"path": request.url.path, "method": request.method, "code": exc.code, "request_id": request_id, "details": exc.details})
    return error_response(exc.status_code, exc.code, exc.message, exc.details, request_id)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = str(uuid.uuid4())
    logger.exception("Unhandled API error [%s]", request_id)
    try:
        db_client.registrar_log(
            "API_ERROR",
            "Erro interno nao tratado.",
            metadata={"path": request.url.path, "method": request.method, "request_id": request_id, "erro": str(exc)[:500]},
            severity="critical",
        )
    except Exception:
        pass
    track_server_event("api_error", metadata={"path": request.url.path, "method": request.method, "request_id": request_id, "erro": str(exc)[:500]})
    return error_response(500, "INTERNAL_ERROR", "Erro interno inesperado.", {"request_id": request_id}, request_id)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    maintenance_paths = {
        "/readings",
        "/api/readings",
        "/api/leitura",
        "/payments/pix/create",
        "/api/payments/pix/create",
    }
    if request.method in ("POST", "PATCH") and request.url.path in maintenance_paths:
        maintenance_enabled = bool(db_client.get_setting("maintenance_mode", False))
        if maintenance_enabled:
            return error_response(
                503,
                "MAINTENANCE_MODE",
                db_client.get_setting(
                    "maintenance_message",
                    "Sistema em manutencao. Tente novamente em instantes.",
                ),
            )

    if not request.url.path.startswith("/api/") and not request.url.path.startswith(("/auth", "/me", "/readings", "/payments", "/webhooks", "/admin")):
        return await call_next(request)

    if request.url.path in ("/api/webhook/stripe", "/api/webhook/mercado-pago"):
        return await call_next(request)

    agora = time.time()
    client_ip = request.client.host if request.client else "unknown"
    subject = None
    auth = request.headers.get("authorization", "")
    request_token = token_from_request(auth, request.cookies.get(AUTH_COOKIE_NAME))
    if request_token:
        try:
            subject = verificar_token_acesso(request_token).get("sub")
        except Exception:
            subject = None
    bucket_keys = [f"ip:{client_ip}:{request.url.path}"]
    if subject:
        bucket_keys.append(f"user:{subject}:{request.url.path}")

    for bucket_key in bucket_keys:
        bucket = RATE_LIMIT_BUCKETS[bucket_key]
        while bucket and agora - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            db_client.registrar_log(
                "RATE_LIMITED",
                "Rate limit excedido.",
                user_id=subject,
                metadata={"path": request.url.path, "bucket": bucket_key},
                severity="warning",
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
            )
            track_server_event("rate_limited", user_id=subject, metadata={"path": request.url.path, "bucket": bucket_key, "ip_address": client_ip})
            return error_response(
                429,
                "RATE_LIMITED",
                "Muitas requisicoes. Tente novamente em instantes.",
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            )

    for bucket_key in bucket_keys:
        RATE_LIMIT_BUCKETS[bucket_key].append(agora)
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    for key, value in security_headers().items():
        response.headers.setdefault(key, value)
    if APP_ENV == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# ─────────────────────────────────────────────
# Modelos Pydantic
# ─────────────────────────────────────────────
class ApiRequestModel(BaseModel):
    class Config:
        extra = "forbid"


class CadastroRequest(ApiRequestModel):
    nome:  str
    email: str
    plano: Optional[str] = None

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def garantir_usuario(email: str, nome: str = "Visitante") -> str:
    """Busca user_id pelo email ou cria novo usuário. Retorna user_id."""
    url, headers = db_client.get_supabase_headers()

    r = http.get(
        f"{url}/rest/v1/users?email=eq.{email}&select=user_id&limit=1",
        headers=headers
    )
    usuarios = r.json() if isinstance(r.json(), list) else []
    if usuarios:
        return usuarios[0]["user_id"]

    new_id = str(uuid.uuid4())
    post_h = dict(headers)
    post_h["Prefer"] = "return=representation"
    http.post(f"{url}/rest/v1/users", headers=post_h, json={
        "user_id": new_id,
        "nome":    nome,
        "email":   email,
        "primeira_tiragem_gratis": True,
        "assinante": False,
        "origem": "frontend"
    })
    return new_id

def extrair_simbolo(nome_carta: str) -> str:
    mapa = {
        "Lua": "&#9790;", "Sol": "&#9728;", "Estrela": "&#11088;",
        "Mago": "&#128295;", "Louco": "&#9854;", "Morte": "&#9760;",
        "Torre": "&#128303;", "Carro": "&#9855;", "Forca": "&#8982;",
        "Eremita": "&#128302;", "Justica": "&#9878;", "Diabo": "&#9760;",
        "Mundo": "&#127758;", "Julgamento": "&#9733;", "Roda": "&#9855;",
        "Enamorados": "&#9829;", "Sacerdotisa": "&#128274;",
        "Imperatriz": "&#9775;", "Imperador": "&#9732;",
        "Hierofante": "&#9768;", "Enforcado": "&#9835;", "Temperanca": "&#9763;"
    }
    for k, v in mapa.items():
        if k.lower() in nome_carta.lower():
            return v
    return "&#10022;"


def contar_registros(tabela: str, filtro: str = "") -> int:
    """Conta registros no Supabase usando Content-Range."""
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
        }
    }


def montar_status_pagamento(payment: dict, usuario: dict) -> dict:
    assinatura = buscar_assinatura_ativa(usuario["user_id"])
    status = payment.get("status") or "pending"
    return {
        "payment": {
            "payment_id": payment.get("payment_id"),
            "status": status,
            "tipo": payment.get("tipo"),
            "product_type": payment.get("product_type"),
            "product_name": payment.get("product_name"),
            "amount": payment.get("amount") or payment.get("valor"),
            "gateway": payment.get("gateway"),
            "gateway_ref": payment.get("gateway_ref"),
            "checkout_url": payment.get("checkout_url"),
            "credits_released": bool(payment.get("credits_released")),
            "approved_at": payment.get("approved_at"),
            "expires_at": payment.get("expires_at"),
            "error_message": payment.get("error_message"),
        },
        "assinatura": assinatura,
        "usuario": {
            "user_id": usuario.get("user_id"),
            "assinante": bool(usuario.get("assinante")),
            "plan_id": usuario.get("plan_id"),
            "credits_balance": usuario.get("credits_balance"),
        },
        "resolved": status in {"approved", "failed", "expired", "cancelled", "refused", "refunded", "error", "abandoned"},
    }


def validar_status_ativo(status: Optional[str]):
    if status is not None and status not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="Status invalido.")


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


def enriquecer_leituras_admin(leituras: list[dict]) -> list[dict]:
    """Anexa pergunta e usuario das leituras para a tabela administrativa."""
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


def ritual_public_payload(ritual: dict) -> dict:
    preco = float(ritual.get("preco") or 0)
    custo_creditos = custo_creditos_ritual({"amount": preco})
    return {
        "ritual_id": ritual.get("ritual_id"),
        "nome": ritual.get("nome"),
        "tema": ritual.get("tema"),
        "descricao": ritual.get("descricao"),
        "preco": preco,
        "creditos": custo_creditos,
        "custo_creditos": custo_creditos,
        "moeda": "creditos",
        "gratuito": custo_creditos <= 0,
        "pdf_url": ritual.get("pdf_url") if custo_creditos <= 0 else None,
        "audio_url": ritual.get("audio_url") if custo_creditos <= 0 else None,
        "tem_pdf": bool(ritual.get("pdf_url")),
        "tem_audio": bool(ritual.get("audio_url")),
        "ativo": ritual.get("ativo", True),
    }


def custo_creditos_ritual(produto: dict) -> int:
    valor = max(0, float(produto.get("amount") or 0))
    inteiro = int(valor)
    return inteiro if valor == inteiro else inteiro + 1


def criar_compra_ritual_creditos(user_id: str, ritual_id: str, status: str, credits_spent: int = 0, coupon_code: str = None) -> dict:
    compras = db_client.listar_registros(
        "ritual_purchases",
        select="*",
        filtros=f"user_id=eq.{user_id}&ritual_id=eq.{ritual_id}&status=in.(pending,approved)",
        limit=1,
    )
    if compras:
        return {**compras[0], "ja_comprado": True}

    payload = {
        "user_id": user_id,
        "ritual_id": ritual_id,
        "status": status,
        "credits_spent": credits_spent,
        "coupon_code": coupon_code,
    }
    compra = db_client.criar_registro("ritual_purchases", payload)
    if "erro" in compra and any(field in str(compra["erro"]) for field in ("credits_spent", "coupon_code")):
        payload.pop("credits_spent", None)
        payload.pop("coupon_code", None)
        compra = db_client.criar_registro("ritual_purchases", payload)
    return compra


COMMERCIAL_THEME_KEYWORDS = {
    "amor": ("amor", "relacionamento", "casamento", "ex", "paixao", "sentimento"),
    "protecao": ("protecao", "limpeza", "energia", "inveja", "medo", "ansiedade", "bloqueio"),
    "clareza": ("clareza", "decisao", "duvida", "caminho", "escolha", "direcao"),
    "carreira": ("carreira", "trabalho", "emprego", "negocio", "dinheiro", "prosperidade"),
}


def tema_comercial_usuario(user_id: str) -> str:
    perguntas = db_client.listar_registros(
        "questions",
        select="pergunta,tema,criado_em",
        filtros=f"user_id=eq.{user_id}",
        limit=5,
        order="criado_em.desc",
    )
    for pergunta in perguntas:
        tema = str(pergunta.get("tema") or "").strip().lower()
        if tema:
            return tema
        texto = str(pergunta.get("pergunta") or "").lower()
        for candidato, keywords in COMMERCIAL_THEME_KEYWORDS.items():
            if any(keyword in texto for keyword in keywords):
                return candidato
    return "clareza"


def selecionar_ofertas_pos_leitura(user_id: str) -> dict:
    tema = tema_comercial_usuario(user_id)
    rituais = db_client.listar_registros("rituals", select="*", filtros="ativo=eq.true", limit=100)

    def pontuar(ritual: dict, gratuito: bool) -> tuple[int, float]:
        preco = float(ritual.get("preco") or 0)
        ritual_gratuito = preco <= 0
        if ritual_gratuito != gratuito:
            return (-1000, -preco)
        pontos = 0
        ritual_tema = str(ritual.get("tema") or "").lower()
        texto = f"{ritual.get('nome') or ''} {ritual.get('descricao') or ''}".lower()
        if ritual_tema == tema:
            pontos += 40
        for keyword in COMMERCIAL_THEME_KEYWORDS.get(tema, (tema,)):
            if keyword and keyword in texto:
                pontos += 8
        return (pontos, preco)

    pagos = [r for r in rituais if float(r.get("preco") or 0) > 0]
    gratuitos = [r for r in rituais if float(r.get("preco") or 0) <= 0]
    pago = max(pagos, key=lambda r: pontuar(r, gratuito=False), default=None)
    gratuito = max(gratuitos, key=lambda r: pontuar(r, gratuito=True), default=None)

    cupons = db_client.listar_registros(
        "coupons",
        select="*",
        filtros="status=eq.active&applies_to=in.(all,ritual)&event_type=eq.after_reading",
        limit=5,
    )
    cupom = cupons[0] if cupons else db_client.buscar_por_id("coupons", "code", "RITUAL10")
    return {
        "tema": tema,
        "upsell": ritual_public_payload(pago) if pago else None,
        "downsell": ritual_public_payload(gratuito) if gratuito else None,
        "coupon_hint": (cupom or {}).get("code") or "RITUAL10",
    }


def normalize_webhook_status(payload: dict) -> tuple[str, str, str]:
    event_type = str(payload.get("type") or payload.get("event_type") or payload.get("event") or "").lower()
    raw_status = str(payload.get("status") or payload.get("payment_status") or "").lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    object_status = str(obj.get("status") or obj.get("payment_status") or "").lower()
    status_text = " ".join([event_type, raw_status, object_status])

    if "checkout.session.completed" in event_type or "approved" in status_text or "paid" in status_text or "succeeded" in status_text:
        return "approved", event_type or "payment.approved", obj.get("id") or payload.get("transaction_id")
    if "expired" in status_text:
        return "expired", event_type or "payment.expired", obj.get("id") or payload.get("transaction_id")
    if "cancel" in status_text:
        return "cancelled", event_type or "payment.cancelled", obj.get("id") or payload.get("transaction_id")
    if "refused" in status_text or "failed" in status_text or "error" in status_text:
        return "error", event_type or "payment.failed", obj.get("id") or payload.get("transaction_id")
    return "pending", event_type or "payment.updated", obj.get("id") or payload.get("transaction_id")


# ─────────────────────────────────────────────
# Endpoints — Auth
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Endpoints — Conteudo
# ─────────────────────────────────────────────

# Rota raiz será tratada pelo StaticFiles no final


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health/detailed")
@app.get("/api/health/detailed")
async def health_detailed():
    return db_client.health_detalhado()


@app.get("/api/status")
async def status():
    """Painel de métricas em tempo real."""
    url, headers = db_client.get_supabase_headers()

    def contar(tabela, filtro=""):
        try:
            r = http.get(
                f"{url}/rest/v1/{tabela}?select=*{filtro}",
                headers={**headers, "Prefer": "count=exact"},
                timeout=4,
            )
            return int(r.headers.get("content-range", "0/0").split("/")[-1])
        except Exception as exc:
            logger.warning("Falha ao contar tabela %s no status: %s", tabela, exc)
            return 0

    hoje = str(date.today())
    count_specs = {
        "usuarios": ("users", ""),
        "assinantes": ("users", "&assinante=eq.true"),
        "leituras_total": ("readings", ""),
        "cartas_hoje": ("daily_cards", f"&criado_em=eq.{hoje}"),
        "mensagens_sent": ("message_events", "&status=eq.sent"),
        "mensagens_pending": ("message_events", "&status=eq.pending"),
    }
    counts = dict(zip(
        count_specs.keys(),
        await asyncio.gather(*(asyncio.to_thread(contar, tabela, filtro) for tabela, filtro in count_specs.values())),
    ))
    return {
        **counts,
        "integracoes": {
            "gemini":   bool(os.getenv("GEMINI_API_KEY")),
            "supabase": bool(os.getenv("SUPABASE_URL")),
            "email":    bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS")),
            "mercado_pago": bool(os.getenv("MERCADO_PAGO_ACCESS_TOKEN")),
            "whatsapp": bool(os.getenv("WHATSAPP_API_URL")),
        }
    }


@app.post("/api/cadastro")
async def cadastro(body: CadastroRequest):
    """Endpoint legado desativado: cadastro agora exige senha e sessao JWT."""
    raise erro_http(
        410,
        "LEGACY_ENDPOINT_DISABLED",
        "Fluxo legado desativado. Use /api/auth/registrar e depois /api/checkout autenticado.",
    )


# Serve o frontend estático (deve ser a última rota)
if os.path.isdir(media_dir):
    app.mount("/imagems", StaticFiles(directory=media_dir), name="imagems")

if os.path.isdir(video_dir):
    app.mount("/video", StaticFiles(directory=video_dir), name="video")

if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*55)
    print("  MADAME DO LUAR API — INICIANDO")
    print("="*55)
    print("  Frontend: http://localhost:8000")
    print("  Docs API: http://localhost:8000/docs")
    print("  Status:   http://localhost:8000/api/status")
    print("="*55 + "\n")
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=reload_enabled)
