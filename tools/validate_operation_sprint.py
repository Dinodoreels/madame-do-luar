"""
Valida a Sprint 4 - Operacao.

Confere a existencia do painel admin, filtros/busca no frontend, rotas
administrativas, auditoria persistida e painel de status operacional.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import api
import db_client


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _validate_admin_frontend() -> None:
    html = _read("frontend/admin.html")
    js = _read("frontend/admin.js")
    for view in ("dashboard", "users", "payments", "messages", "status", "logs", "audit", "ops"):
        _require(f'data-view="{view}"' in html, f"Aba admin ausente: {view}")
        _require(f'id="view-{view}"' in html, f"View admin ausente: {view}")
    for marker in ("globalSearch", "data-filter", "loadAudit", "loadStatusPanel", "loadLogs"):
        _require(marker in html or marker in js, f"Marcador admin ausente: {marker}")


def _validate_routes() -> None:
    routes = {route.path for route in api.app.routes}
    required = {
        "/admin/dashboard",
        "/admin/users",
        "/admin/payments",
        "/admin/messages",
        "/admin/logs",
        "/admin/audit",
        "/admin/status",
        "/admin/operations/daily-check",
        "/api/admin/audit",
        "/api/admin/status",
    }
    missing = sorted(required - routes)
    _require(not missing, "Rotas admin ausentes: " + ", ".join(missing))


def _validate_audit() -> dict:
    audit_id = f"operation-sprint-{uuid.uuid4()}"
    result = db_client.registrar_auditoria(
        "OPERATION_SPRINT_VALIDATION",
        entity_type="system",
        entity_id=audit_id,
        metadata={"source": "tools/validate_operation_sprint.py"},
    )
    _require(isinstance(result, dict) and "erro" not in result, f"Falha ao registrar auditoria: {result}")
    rows = db_client.listar_registros(
        "audit_logs",
        select="*",
        filtros=f"entity_id=eq.{audit_id}",
        limit=1,
    )
    _require(bool(rows), "Auditoria registrada nao foi encontrada em audit_logs.")
    return rows[0]


def _validate_status_panel() -> dict:
    status = db_client.painel_status_operacional()
    _require(isinstance(status, dict), "Painel de status nao retornou dict.")
    for key in ("health", "conversao", "retencao", "receita", "alertas_abertos", "mensagens_pendentes"):
        _require(key in status, f"Campo ausente no painel de status: {key}")
    _require(status["health"].get("status") in {"ok", "degraded", "error"}, "Health status invalido.")
    return status


def main() -> None:
    load_dotenv()
    _require(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"), "SUPABASE_URL/SUPABASE_KEY ausentes.")
    _validate_admin_frontend()
    _validate_routes()
    audit = _validate_audit()
    status = _validate_status_panel()

    print("OK Sprint 4 operacao validada.")
    print(f"Rotas admin: {len(api.app.routes)} carregadas")
    print(f"Audit log: {audit.get('audit_id')} / {audit.get('action')}")
    print(f"Health: {status['health'].get('status')} / alertas={len(status.get('alertas_abertos') or [])}")
    print(f"Mensagens pendentes: {len(status.get('mensagens_pendentes') or [])}")


if __name__ == "__main__":
    main()
