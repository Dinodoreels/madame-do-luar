import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db_client
from notificacoes import enviar_email, enviar_whatsapp_result, whatsapp_configurado

load_dotenv(ROOT / ".env")


BASE_URL = os.getenv("LOCAL_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_EMAIL = os.getenv("MATURITY_ADMIN_EMAIL") or (os.getenv("ADMIN_EMAILS", "").split(",")[0].strip())
ADMIN_PASSWORD = os.getenv("MATURITY_ADMIN_PASSWORD")
CLIENT_PASSWORD = os.getenv("MATURITY_CLIENT_PASSWORD", "TesteMaturidade#2026")
REPORT_PATH = ROOT / "RELATORIO_AUDITORIA_ESTADO_ATUAL.md"


class Audit:
    def __init__(self):
        self.results = []
        self.context = {}

    def add(self, item, status, evidence, detail=""):
        self.results.append(
            {
                "item": item,
                "status": status,
                "evidence": evidence,
                "detail": detail,
            }
        )
        marker = {"OK": "PASS", "FALHA": "FAIL", "BLOQUEADO": "BLOCK", "PARCIAL": "PARTIAL"}.get(status, status)
        print(f"[{marker}] {item}: {evidence}")
        if detail:
            print(f"       {detail}")

    def write(self):
        now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        totals = {}
        for result in self.results:
            totals[result["status"]] = totals.get(result["status"], 0) + 1
        lines = [
            "# Relatorio de Auditoria - Estado Atual",
            "",
            f"Gerado em: `{now}`",
            f"Base local testada: `{BASE_URL}`",
            "",
            "## Resumo",
            "",
            "| Status | Total |",
            "|---|---:|",
        ]
        for status in ("OK", "PARCIAL", "BLOQUEADO", "FALHA"):
            lines.append(f"| {status} | {totals.get(status, 0)} |")
        lines += [
            "",
            "## Evidencias",
            "",
            "| Item | Status | Evidencia | Detalhe |",
            "|---|---|---|---|",
        ]
        for result in self.results:
            lines.append(
                "| {item} | {status} | {evidence} | {detail} |".format(
                    item=result["item"].replace("|", "/"),
                    status=result["status"],
                    evidence=str(result["evidence"]).replace("|", "/"),
                    detail=str(result["detail"]).replace("|", "/"),
                )
            )
        lines += [
            "",
            "## Observacoes",
            "",
            "- `OK` significa validado com execucao real ou simulacao explicita permitida pelo ambiente local.",
            "- `PARCIAL` significa que a base tecnica respondeu, mas existe dependencia externa ou validacao complementar.",
            "- `BLOQUEADO` significa dependencia ausente, credencial ausente ou ambiente sem permissao.",
            "- `FALHA` significa erro real observado no fluxo testado.",
            "",
        ]
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def request_json(method, path, token=None, session=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    client = session or requests
    response = client.request(method, f"{BASE_URL}{path}", headers=headers, timeout=45, **kwargs)
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}
    return response, data


def validate_health(audit):
    response, data = request_json("GET", "/health")
    if response.status_code == 200 and data.get("status") == "ok":
        audit.context["health_ok"] = True
        return True
    audit.add("Backend local", "FALHA", f"Health HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:200])
    return False


def validate_admin_login(audit):
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        audit.add(
            "Validar login de admin real",
            "BLOQUEADO",
            "Defina MATURITY_ADMIN_EMAIL e MATURITY_ADMIN_PASSWORD fora do repositorio para validar login admin.",
        )
        return False
    session = requests.Session()
    response, data = request_json(
        "POST",
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "senha": ADMIN_PASSWORD},
        session=session,
    )
    if response.status_code == 200 and data.get("usuario", {}).get("role") in {"admin", "super_admin"} and session.cookies.get("mdl_access_token"):
        audit.context["admin_session"] = session
        audit.context["admin_user"] = data["usuario"]
        audit.add("Validar login de admin real", "OK", "Login admin retornou cookie HttpOnly e role administrativa.")
        return True
    audit.add("Validar login de admin real", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
    return False


def validate_client_register_and_login(audit):
    suffix = int(time.time())
    email = f"cliente.maturidade.{suffix}@madamedoluar.test"
    payload = {
        "nome": "Cliente Auditoria Maturidade",
        "email": email,
        "senha": CLIENT_PASSWORD,
        "whatsapp": f"119{str(suffix)[-8:]}",
        "whatsapp_opt_in": True,
        "email_opt_in": True,
        "terms_accepted": True,
        "privacy_accepted": True,
        "ai_notice_accepted": True,
    }
    session = requests.Session()
    response, data = request_json("POST", "/api/auth/registrar", json=payload, session=session)
    if response.status_code not in {200, 201} or not session.cookies.get("mdl_access_token"):
        audit.add("Validar cadastro novo", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
        return False

    user = data["usuario"]
    audit.context["client_email"] = email
    audit.context["client_user"] = user
    audit.context["client_session"] = session
    audit.add("Validar cadastro novo", "OK", "Conta nova criada com cookie de sessao.")

    session = requests.Session()
    response, data = request_json("POST", "/api/auth/login", json={"email": email, "senha": CLIENT_PASSWORD}, session=session)
    if response.status_code == 200 and session.cookies.get("mdl_access_token") and data.get("usuario", {}).get("role") not in {"admin", "super_admin"}:
        audit.context["client_session"] = session
        audit.context["client_user"] = data["usuario"]
        audit.add("Validar login de cliente real", "OK", "Login cliente retornou cookie e role nao administrativa.")
        return True
    audit.add("Validar login de cliente real", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
    return False


def validate_password_recovery(audit):
    email = audit.context.get("client_email")
    if not email:
        audit.add("Validar recuperacao de senha", "BLOQUEADO", "Cadastro de cliente nao foi concluido.")
        return False

    response, data = request_json("POST", "/api/auth/forgot-password", json={"email": email})
    if response.status_code != 200:
        audit.add("Validar recuperacao de senha", "FALHA", f"Forgot HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
        return False

    token_result = db_client.criar_token_recuperacao(email)
    token = token_result.get("token")
    if not token:
        audit.add("Validar recuperacao de senha", "FALHA", "Token de recuperacao nao foi criado.", json.dumps(token_result, ensure_ascii=False)[:240])
        return False

    new_password = CLIENT_PASSWORD + "R"
    response, data = request_json("POST", "/api/auth/reset-password", json={"token": token, "nova_senha": new_password})
    if response.status_code != 200:
        audit.add("Validar recuperacao de senha", "FALHA", f"Reset HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
        return False

    session = requests.Session()
    response, data = request_json("POST", "/api/auth/login", json={"email": email, "senha": new_password}, session=session)
    if response.status_code == 200 and session.cookies.get("mdl_access_token"):
        audit.context["client_session"] = session
        audit.context["client_user"] = data["usuario"]
        audit.add("Validar recuperacao de senha", "OK", "Forgot, reset e novo login validados.")
        return True

    audit.add("Validar recuperacao de senha", "FALHA", f"Login pos-reset HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
    return False


def validate_daily_card(audit):
    session = audit.context.get("client_session")
    if not session:
        audit.add("Validar carta do dia", "BLOQUEADO", "Cliente autenticado indisponivel.")
        return False
    response, data = request_json("POST", "/api/carta-do-dia", session=session, json={})
    if response.status_code == 200 and data.get("carta"):
        audit.add("Validar carta do dia", "OK", f"Carta retornada: {data.get('carta')}.")
        return True
    audit.add("Validar carta do dia", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
    return False


def admin_credit(audit, amount, type_, reason):
    admin_session = audit.context.get("admin_session")
    user = audit.context.get("client_user") or {}
    user_id = user.get("user_id")
    if not admin_session or not user_id:
        return None, "Admin ou cliente indisponivel."
    response, data = request_json(
        "POST",
        f"/api/admin/users/{user_id}/credits",
        session=admin_session,
        json={"amount": amount, "type": type_, "reason": reason},
    )
    return (response, data), None


def get_client_from_db(audit):
    user = audit.context.get("client_user") or {}
    user_id = user.get("user_id")
    return db_client.get_user_by_id(user_id) if user_id else None


def validate_admin_credit_and_audit(audit):
    result, block = admin_credit(audit, 150, "add", "Auditoria Fase 1 - adicionar creditos")
    if block:
        audit.add("Validar alteracao de creditos pelo admin", "BLOQUEADO", block)
        audit.add("Validar logs e auditoria apos acao administrativa", "BLOQUEADO", block)
        return False
    response, data = result
    if response.status_code != 200 or "erro" in data:
        audit.add("Validar alteracao de creditos pelo admin", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
        audit.add("Validar logs e auditoria apos acao administrativa", "BLOQUEADO", "Alteracao de creditos falhou.")
        return False
    audit.add("Validar alteracao de creditos pelo admin", "OK", "Credito alterado via endpoint admin.")

    user = audit.context.get("client_user") or {}
    logs = db_client.listar_registros(
        "system_logs",
        select="*",
        filtros=f"user_id=eq.{user.get('user_id')}",
        limit=20,
        order="created_at.desc",
    )
    audits = db_client.listar_registros(
        "audit_logs",
        select="*",
        filtros=f"user_id=eq.{user.get('user_id')}",
        limit=20,
        order="created_at.desc",
    )
    has_log = any(row.get("event_type") == "ADMIN_ACTION" for row in logs)
    has_audit = any(row.get("action") == "ADMIN_USER_CREDITS_CHANGED" for row in audits)
    if has_log and has_audit:
        audit.add("Validar logs e auditoria apos acao administrativa", "OK", "System log e audit log encontrados.")
        return True
    audit.add(
        "Validar logs e auditoria apos acao administrativa",
        "FALHA",
        f"Log admin encontrado={has_log}; audit encontrado={has_audit}.",
    )
    return False


def validate_reading_success_and_credit_consumption(audit):
    session = audit.context.get("client_session")
    user = get_client_from_db(audit)
    if not session or not user:
        audit.add("Validar criacao de tiragem", "BLOQUEADO", "Cliente autenticado indisponivel.")
        audit.add("Validar consumo de credito por tiragem", "BLOQUEADO", "Cliente autenticado indisponivel.")
        return False

    db_client.atualizar_registro("users", "user_id", user["user_id"], {"primeira_tiragem_gratis": False})
    before = db_client.get_user_by_id(user["user_id"])
    before_balance = int(before.get("credits_balance") or 0)

    response, data = request_json(
        "POST",
        "/api/readings",
        session=session,
        json={"pergunta": "Auditoria de maturidade: validar tiragem de tres cartas.", "tipo": "tres_cartas"},
    )
    after = db_client.get_user_by_id(user["user_id"])
    after_balance = int(after.get("credits_balance") or 0) if after else before_balance

    if response.status_code == 200 and data.get("reading_id"):
        audit.context["reading_id"] = data.get("reading_id")
        audit.add("Validar criacao de tiragem", "OK", f"Reading criada: {data.get('reading_id')}.")
        if before_balance - after_balance == 50:
            audit.add("Validar consumo de credito por tiragem", "OK", f"Saldo {before_balance} -> {after_balance}.")
        else:
            audit.add("Validar consumo de credito por tiragem", "FALHA", f"Saldo {before_balance} -> {after_balance}; esperado debito 50.")
        return True

    audit.add("Validar criacao de tiragem", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
    if before_balance == after_balance:
        audit.add("Validar consumo de credito por tiragem", "BLOQUEADO", "Tiragem nao concluida; saldo preservado.")
    else:
        audit.add("Validar consumo de credito por tiragem", "FALHA", f"Tiragem falhou e saldo mudou {before_balance} -> {after_balance}.")
    return False


def validate_ai_refund(audit):
    user = get_client_from_db(audit)
    if not user:
        audit.add("Validar estorno de credito se a IA falhar", "BLOQUEADO", "Cliente de teste indisponivel.")
        return False

    db_client.ajustar_creditos(
        user_id=user["user_id"],
        amount=100,
        tipo="add",
        reason="Auditoria Fase 1 - preparar estorno IA",
        admin_id=(audit.context.get("admin_user") or {}).get("user_id"),
    )
    db_client.atualizar_registro("users", "user_id", user["user_id"], {"primeira_tiragem_gratis": False})
    fresh = db_client.get_user_by_id(user["user_id"])
    before_balance = int(fresh.get("credits_balance") or 0)

    import api

    class FailingReadingService:
        def gerar_interpretacao_tres_cartas(self, pergunta, cartas):
            raise RuntimeError("Falha simulada de IA para auditoria")

    original = api.reading_service
    api.reading_service = FailingReadingService()
    try:
        try:
            asyncio.run(
                api.leitura(
                    api.LeituraRequest(pergunta="Forcar falha IA para validar estorno.", tipo="tres_cartas"),
                    usuario=fresh,
                )
            )
        except Exception:
            pass
    finally:
        api.reading_service = original

    after = db_client.get_user_by_id(user["user_id"])
    after_balance = int(after.get("credits_balance") or 0) if after else -1
    logs = db_client.listar_registros(
        "system_logs",
        select="*",
        filtros=f"user_id=eq.{user['user_id']}",
        limit=20,
        order="created_at.desc",
    )
    has_ai_failure = any(row.get("event_type") == "READING_FAILED" for row in logs)
    if after_balance == before_balance and has_ai_failure:
        audit.add("Validar estorno de credito se a IA falhar", "OK", f"Saldo preservado {before_balance} -> {after_balance}; log de falha registrado.")
        return True
    audit.add(
        "Validar estorno de credito se a IA falhar",
        "FALHA",
        f"Saldo {before_balance} -> {after_balance}; log falha IA={has_ai_failure}.",
    )
    return False


def validate_admin_panel_blocks(audit):
    session = audit.context.get("admin_session")
    if not session:
        audit.add("Validar painel admin carregando todos os blocos", "BLOQUEADO", "Admin autenticado indisponivel.")
        audit.add("Validar listagem de usuarios no admin", "BLOQUEADO", "Admin autenticado indisponivel.")
        return False

    paths = [
        "/api/admin/dashboard",
        "/api/admin/reports/financial",
        "/api/admin/reports/ai",
        "/api/admin/status",
        "/api/admin/alerts",
    ]
    statuses = []
    for path in paths:
        response, data = request_json("GET", path, session=session)
        statuses.append((path, response.status_code, list(data.keys())[:5]))
    ok = all(status == 200 for _, status, _ in statuses)
    if ok:
        audit.add("Validar painel admin carregando todos os blocos", "OK", "Dashboard, financeiro, IA, status e alertas responderam 200.")
    else:
        audit.add("Validar painel admin carregando todos os blocos", "FALHA", json.dumps(statuses, ensure_ascii=False)[:400])

    response, data = request_json("GET", "/api/admin/users?limit=10", session=session)
    users = data.get("usuarios") if isinstance(data, dict) else None
    if response.status_code == 200 and isinstance(users, list):
        audit.add("Validar listagem de usuarios no admin", "OK", f"{len(users)} usuarios retornados.")
    else:
        audit.add("Validar listagem de usuarios no admin", "FALHA", f"HTTP {response.status_code}", json.dumps(data, ensure_ascii=False)[:240])
    return ok


def validate_notifications(audit):
    client_email = audit.context.get("client_email") or ADMIN_EMAIL
    email_ok = enviar_email(
        client_email,
        "Teste de auditoria - Madame do Luar",
        "Mensagem de teste da auditoria de maturidade da plataforma.",
    )
    simulated_email = not (os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))
    if email_ok and simulated_email:
        audit.add("Validar envio de email", "PARCIAL", "Envio simulado com sucesso; SMTP real nao configurado.")
    elif email_ok:
        audit.add("Validar envio de email", "OK", "Email enviado via SMTP configurado.")
    else:
        audit.add("Validar envio de email", "FALHA", "Envio SMTP/simulado retornou falso.")

    user = audit.context.get("client_user") or {}
    result = enviar_whatsapp_result(user.get("whatsapp") or os.getenv("WHATSAPP_DEFAULT_RECIPIENT") or "11999999999", "Teste de auditoria - Madame do Luar")
    if result.get("ok") and result.get("status") == "simulated":
        audit.add("Validar envio de WhatsApp", "PARCIAL", "Envio simulado com sucesso; provedor real nao configurado.")
    elif result.get("ok"):
        audit.add("Validar envio de WhatsApp", "OK", f"WhatsApp enviado via {result.get('provider')}.")
    elif not whatsapp_configurado():
        audit.add("Validar envio de WhatsApp", "BLOQUEADO", "Credenciais do provedor WhatsApp ausentes ou incompletas.")
    else:
        audit.add("Validar envio de WhatsApp", "FALHA", result.get("error") or "Provedor retornou falha.")


def validate_daily_card_scheduler(audit):
    import automation_engine

    result = automation_engine.agendar_cartas_do_dia_renovadas(dry_run=True)
    if isinstance(result, dict) and ("scheduled" in result or "agendados" in result):
        scheduled = result.get("scheduled", result.get("agendados"))
        users = result.get("usuarios", result.get("users", 0))
        audit.add("Validar scheduler da carta do dia", "OK", f"Dry-run executado; usuarios={users}; agendaveis={scheduled}.")
        return True
    audit.add("Validar scheduler da carta do dia", "FALHA", "Retorno inesperado do scheduler.", json.dumps(result, ensure_ascii=False)[:240])
    return False


def validate_backup_restore(audit):
    import subprocess

    backup = subprocess.run(
        [sys.executable, str(TOOLS / "backup_database.py")],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    if backup.returncode == 0:
        audit.add("Validar backup", "OK", "Backup executado; manifesto atualizado.")
    else:
        audit.add("Validar backup", "FALHA", f"Exit {backup.returncode}", (backup.stdout + backup.stderr)[-400:])
        audit.add("Validar restore de teste", "BLOQUEADO", "Backup falhou.")
        return False

    manifest_path = ROOT / "backups" / "latest_backup_manifest.json"
    if not manifest_path.exists():
        audit.add("Validar restore de teste", "FALHA", "Manifesto de backup nao encontrado.")
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backup_file = manifest.get("backup_file")
    restore = subprocess.run(
        [sys.executable, str(TOOLS / "restore_database_test.py"), backup_file],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    if restore.returncode == 0:
        audit.add("Validar restore de teste", "OK", "Restore de teste validou o arquivo de backup.")
        return True
    audit.add("Validar restore de teste", "FALHA", f"Exit {restore.returncode}", (restore.stdout + restore.stderr)[-400:])
    return False


def main():
    audit = Audit()
    if not validate_health(audit):
        audit.write()
        return 1

    validate_admin_login(audit)
    validate_client_register_and_login(audit)
    validate_password_recovery(audit)
    validate_daily_card(audit)
    validate_admin_panel_blocks(audit)
    validate_admin_credit_and_audit(audit)
    validate_reading_success_and_credit_consumption(audit)
    validate_ai_refund(audit)
    validate_notifications(audit)
    validate_daily_card_scheduler(audit)
    validate_backup_restore(audit)
    audit.write()

    failures = [row for row in audit.results if row["status"] == "FALHA"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
