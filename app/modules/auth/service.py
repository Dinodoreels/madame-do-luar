import os

from fastapi import HTTPException

import automation_engine
from app.core.context import request_context
from app.core.security import admin_em_env
from app.modules.analytics.use_cases import track_server_event
from services import NotificationService

from .repository import AuthRepository


class AuthService:
    def __init__(self, repository: AuthRepository | None = None, notification_service: NotificationService | None = None):
        self.repository = repository or AuthRepository()
        self.notification_service = notification_service or NotificationService()

    def register(self, body, request):
        try:
            resultado = self.repository.create_user(
                nome=body.nome,
                email=body.email,
                senha=body.senha,
                avatar_url=body.avatar_url,
                whatsapp=body.whatsapp,
                whatsapp_opt_in=bool(body.whatsapp_opt_in),
                email_opt_in=bool(body.email_opt_in),
                terms_accepted=bool(body.terms_accepted),
                privacy_accepted=bool(body.privacy_accepted),
                ai_notice_accepted=bool(body.ai_notice_accepted),
            )
        except Exception as exc:
            print(f"[AUTH] Erro ao criar usuario: {exc}")
            raise HTTPException(status_code=503, detail="Banco de dados indisponivel. Verifique Supabase e tente novamente.")
        if "erro" in resultado:
            raise HTTPException(status_code=400, detail=resultado["erro"])

        usuario = resultado["usuario"]
        ctx = request_context(request)
        self.repository.log(
            "USER_REGISTERED",
            "Usuario cadastrado pelo frontend.",
            user_id=usuario.get("user_id"),
            metadata={"email": body.email},
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
        )
        self.repository.audit(
            "USER_REGISTERED",
            entity_type="users",
            entity_id=usuario.get("user_id"),
            user_id=usuario.get("user_id"),
            after_data={"email": body.email, "whatsapp_opt_in": bool(body.whatsapp_opt_in), "email_opt_in": bool(body.email_opt_in)},
            metadata={"terms_accepted": bool(body.terms_accepted), "privacy_accepted": bool(body.privacy_accepted), "ai_notice_accepted": bool(body.ai_notice_accepted)},
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
        )
        track_server_event("signup_completed", user_id=usuario.get("user_id"), entity_type="users", entity_id=usuario.get("user_id"), metadata={"email_opt_in": bool(body.email_opt_in), "whatsapp_opt_in": bool(body.whatsapp_opt_in)})
        if body.whatsapp_opt_in:
            track_server_event("whatsapp_opt_in", user_id=usuario.get("user_id"), entity_type="users", entity_id=usuario.get("user_id"))
        if body.email_opt_in:
            track_server_event("email_opt_in", user_id=usuario.get("user_id"), entity_type="users", entity_id=usuario.get("user_id"))
        try:
            automation_engine.agendar_boas_vindas(usuario)
        except Exception:
            pass
        return usuario

    def login(self, body, request):
        try:
            resultado = self.repository.verify_login(body.email, body.senha)
        except Exception as exc:
            print(f"[AUTH] Erro no login: {exc}")
            raise HTTPException(status_code=503, detail="Banco de dados indisponivel. Verifique Supabase e tente novamente.")
        ctx = request_context(request)
        if "erro" in resultado:
            track_server_event("login_failed", metadata={"email": body.email, "erro": resultado["erro"]}, source="backend")
            self.repository.log(
                "USER_LOGIN",
                "Tentativa de login recusada.",
                metadata={"email": body.email, "erro": resultado["erro"]},
                severity="warning",
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            raise HTTPException(status_code=401, detail=resultado["erro"])
        self.repository.log(
            "USER_LOGIN",
            "Login realizado com sucesso.",
            user_id=resultado["usuario"].get("user_id"),
            metadata={"email": body.email},
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
        )
        usuario = resultado["usuario"]
        track_server_event("login_success", user_id=usuario.get("user_id"), entity_type="users", entity_id=usuario.get("user_id"))
        if admin_em_env(usuario.get("email")) or usuario.get("role") in ("admin", "super_admin", "financeiro", "suporte", "marketing", "operacoes"):
            track_server_event("admin_login", user_id=usuario.get("user_id"), admin_id=usuario.get("user_id"), entity_type="users", entity_id=usuario.get("user_id"))
        if admin_em_env(usuario.get("email")) and usuario.get("role") not in ("admin", "super_admin"):
            usuario = {**usuario, "role": "admin"}
        return usuario

    def logout(self, usuario: dict, request):
        ctx = request_context(request)
        self.repository.log(
            "USER_LOGOUT",
            "Logout solicitado pelo usuario.",
            user_id=usuario.get("user_id"),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
        )

    def forgot_password(self, body, request) -> dict:
        resultado = self.repository.create_password_reset_token(body.email)
        if "erro" in resultado:
            raise HTTPException(status_code=400, detail=resultado["erro"])

        reset_url = None
        if resultado.get("token"):
            reset_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/reset-password?token={resultado['token']}"
            try:
                self.notification_service.enviar_email(
                    resultado["email"],
                    "Recuperacao de senha - Madame do Luar",
                    f"Ola, {resultado.get('nome') or 'cliente'}.\n\n"
                    f"Use este link para redefinir sua senha: {reset_url}\n"
                    f"O link expira em {os.getenv('PASSWORD_RESET_MINUTES', '30')} minutos.\n\n"
                    "Se voce nao pediu isso, ignore este email.",
                )
            except Exception:
                pass

        ctx = request_context(request)
        self.repository.log(
            "PASSWORD_RESET",
            "Solicitacao de recuperacao de senha.",
            user_id=resultado.get("user_id"),
            metadata={"email": body.email},
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
        )
        response = {"status": "ok", "mensagem": "Se o e-mail existir, enviaremos as instrucoes."}
        if os.getenv("EXPOSE_RESET_TOKEN_DEV", "false").lower() == "true" and resultado.get("token"):
            response["reset_token_dev"] = resultado["token"]
            response["reset_url_dev"] = reset_url
        return response

    def reset_password(self, body) -> dict:
        resultado = self.repository.reset_password_by_token(body.token, body.nova_senha)
        if "erro" in resultado:
            raise HTTPException(status_code=400, detail=resultado["erro"])
        return {"status": "ok", "mensagem": "Senha redefinida com sucesso."}
