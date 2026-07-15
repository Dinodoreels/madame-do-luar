import os
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request

import db_client
from app.core.context import request_context
from app.core.security import admin_atual


ROLE_PERMISSIONS = {
    "super_admin": {"*"},
    "admin": {
        "admin.dashboard",
        "admin.users.read",
        "admin.users.write",
        "admin.content",
        "admin.ops",
        "admin.logs",
        "admin.audit",
        "admin.crm",
        "admin.marketing",
        "admin.jobs",
        "admin.alerts",
        "admin.export",
    },
    "financeiro": {
        "admin.dashboard",
        "admin.users.read",
        "admin.billing.read",
        "admin.billing.write",
        "admin.billing.approve",
        "admin.logs",
        "admin.audit",
        "admin.export",
    },
    "suporte": {
        "admin.dashboard",
        "admin.users.read",
        "admin.logs",
        "admin.audit",
        "admin.crm",
    },
    "marketing": {
        "admin.dashboard",
        "admin.crm",
        "admin.marketing",
        "admin.content",
        "admin.export",
    },
    "operacoes": {
        "admin.dashboard",
        "admin.ops",
        "admin.jobs",
        "admin.alerts",
        "admin.logs",
        "admin.audit",
    },
}

SENSITIVE_PERMISSIONS = {"admin.billing.approve", "admin.export", "admin.settings", "admin.users.write"}


def admin_permissions(admin: dict) -> set[str]:
    role = admin.get("role") or "cliente"
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(admin: dict, permission: str) -> bool:
    permissions = admin_permissions(admin)
    return "*" in permissions or permission in permissions


def require_permission(permission: str) -> Callable:
    async def dependency(admin: dict = Depends(admin_atual)):
        if not has_permission(admin, permission):
            raise HTTPException(status_code=403, detail=f"Permissao administrativa obrigatoria: {permission}")
        return admin

    return dependency


async def require_sensitive_admin_action(
    request: Request,
    admin: dict,
    permission: str,
    x_admin_confirm_password: str | None = Header(None),
    x_admin_2fa_code: str | None = Header(None),
) -> dict:
    if not has_permission(admin, permission):
        raise HTTPException(status_code=403, detail=f"Permissao administrativa obrigatoria: {permission}")

    expected_code = os.getenv("ADMIN_2FA_CODE") or os.getenv("ADMIN_REAUTH_CODE")
    password_ok = False
    code_ok = bool(expected_code and x_admin_2fa_code and x_admin_2fa_code == expected_code)
    if x_admin_confirm_password:
        result = db_client.verificar_login(admin.get("email"), x_admin_confirm_password)
        password_ok = "erro" not in result

    if not (password_ok or code_ok):
        raise HTTPException(
            status_code=428,
            detail="Reautenticacao administrativa obrigatoria. Envie X-Admin-Confirm-Password ou X-Admin-2FA-Code valido.",
        )

    ctx = request_context(request)
    db_client.registrar_auditoria(
        "ADMIN_SENSITIVE_REAUTH",
        entity_type="admin_action",
        admin_id=admin.get("user_id"),
        metadata={"permission": permission, "method": "2fa" if code_ok else "password"},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning",
    )
    return admin


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    name, domain = value.split("@", 1)
    if len(name) <= 2:
        return f"{name[:1]}***@{domain}"
    return f"{name[:2]}***@{domain}"


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_user(user: dict, reveal: bool = False) -> dict:
    result = dict(user)
    result.pop("senha_hash", None)
    if not reveal:
        result["email"] = mask_email(result.get("email"))
        result["whatsapp"] = mask_phone(result.get("whatsapp"))
    return result


def audit_sensitive_view(request: Request, admin: dict, action: str, entity_type: str, entity_id: str | None = None, metadata: dict | None = None):
    ctx = request_context(request)
    db_client.registrar_auditoria(
        action,
        entity_type=entity_type,
        entity_id=entity_id,
        admin_id=admin.get("user_id"),
        metadata=metadata or {},
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        severity="warning",
    )
