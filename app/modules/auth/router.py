from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.security import (
    clear_auth_cookie,
    public_auth_payload,
    resposta_auth,
    set_auth_cookie,
    usuario_atual,
)

from .schemas import ForgotPasswordRequest, LoginRequest, RegistrarRequest, ResetPasswordRequest
from .service import AuthService


router = APIRouter(tags=["auth"])
auth_service = AuthService()


@router.post("/auth/register")
@router.post("/api/auth/registrar")
async def auth_registrar(body: RegistrarRequest, request: Request):
    usuario = auth_service.register(body, request)
    auth_payload = {**resposta_auth(usuario), "mensagem": "Conta criada com sucesso!"}
    return set_auth_cookie(JSONResponse(content=public_auth_payload(auth_payload)), auth_payload["_access_token"])


@router.post("/auth/login")
@router.post("/api/auth/login")
async def auth_login(body: LoginRequest, request: Request):
    usuario = auth_service.login(body, request)
    auth_payload = resposta_auth(usuario)
    return set_auth_cookie(JSONResponse(content=public_auth_payload(auth_payload)), auth_payload["_access_token"])


@router.post("/auth/logout")
@router.post("/api/auth/logout")
async def auth_logout(request: Request, usuario: dict = Depends(usuario_atual)):
    auth_service.logout(usuario, request)
    return clear_auth_cookie(JSONResponse(content={"status": "ok"}))


@router.post("/auth/forgot-password")
@router.post("/api/auth/forgot-password")
async def auth_forgot_password(body: ForgotPasswordRequest, request: Request):
    return auth_service.forgot_password(body, request)


@router.post("/auth/reset-password")
@router.post("/api/auth/reset-password")
async def auth_reset_password(body: ResetPasswordRequest):
    return auth_service.reset_password(body)
