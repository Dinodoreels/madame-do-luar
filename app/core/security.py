import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import Cookie, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import settings


def security_headers() -> dict:
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "media-src 'self' data:; "
        "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'"
    )
    return {
        "Content-Security-Policy": csp,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }


def set_auth_cookie(response: JSONResponse, token: str) -> JSONResponse:
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=settings.jwt_expires_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return response


def clear_auth_cookie(response: JSONResponse) -> JSONResponse:
    response.delete_cookie(settings.auth_cookie_name, path="/", samesite=settings.auth_cookie_samesite)
    return response


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def criar_token_acesso(usuario: dict) -> str:
    agora = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": usuario["user_id"],
        "email": usuario.get("email"),
        "name": usuario.get("nome"),
        "iss": settings.jwt_issuer,
        "iat": agora,
        "exp": agora + settings.jwt_expires_seconds,
    }
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def verificar_token_acesso(token: str) -> dict:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected_signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        received_signature = _b64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, received_signature):
            raise ValueError("assinatura invalida")

        payload = json.loads(_b64url_decode(encoded_payload))
        if payload.get("iss") != settings.jwt_issuer:
            raise ValueError("issuer invalido")
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expirado")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")


def resposta_auth(usuario: dict) -> dict:
    usuario_limpo = dict(usuario)
    usuario_limpo.pop("senha_hash", None)
    token = criar_token_acesso(usuario_limpo)
    return {
        "usuario": usuario_limpo,
        "_access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expires_seconds,
    }


def public_auth_payload(auth_payload: dict) -> dict:
    payload = dict(auth_payload)
    payload.pop("_access_token", None)
    payload.pop("access_token", None)
    payload.pop("token", None)
    return payload


def token_from_request(authorization: Optional[str], cookie_token: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return cookie_token


def admin_em_env(email: str) -> bool:
    admins = [item.strip().lower() for item in os.getenv("ADMIN_EMAILS", "").split(",") if item.strip()]
    return bool(email and email.lower() in admins)


async def usuario_atual(
    authorization: Optional[str] = Header(None),
    mdl_access_token: Optional[str] = Cookie(None),
) -> dict:
    import db_client

    token = token_from_request(authorization, mdl_access_token)
    if not token:
        raise HTTPException(status_code=401, detail="Autenticacao obrigatoria.")

    payload = verificar_token_acesso(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token sem usuario.")

    usuario = db_client.get_user_by_id(user_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario nao encontrado.")
    if usuario.get("status") == "bloqueado":
        raise HTTPException(status_code=403, detail="Usuario bloqueado.")
    usuario.pop("senha_hash", None)
    return usuario


async def usuario_atual_opcional(
    authorization: Optional[str] = Header(None),
    mdl_access_token: Optional[str] = Cookie(None),
) -> Optional[dict]:
    if not token_from_request(authorization, mdl_access_token):
        return None
    try:
        return await usuario_atual(authorization, mdl_access_token)
    except HTTPException:
        return None


async def admin_atual(
    request: Request,
    authorization: Optional[str] = Header(None),
    mdl_access_token: Optional[str] = Cookie(None),
) -> dict:
    if not token_from_request(authorization, mdl_access_token):
        raise HTTPException(status_code=401, detail={
            "message": "Autenticacao obrigatoria.",
            "app_env": settings.app_env,
            "host": request.client.host if request.client else None,
        })

    usuario = await usuario_atual(authorization, mdl_access_token)
    role = usuario.get("role")
    if admin_em_env(usuario.get("email")) and role not in ("admin", "super_admin", "financeiro", "suporte", "marketing", "operacoes"):
        usuario = {**usuario, "role": "super_admin"}
        return usuario
    if role in ("admin", "super_admin", "financeiro", "suporte", "marketing", "operacoes"):
        return usuario
    raise HTTPException(status_code=403, detail="Acesso administrativo obrigatorio.")
