"""
Gate final de venda publica do Madame do Luar.

Este script nao declara o produto pronto apenas porque o codigo existe. Ele
separa validacao local, credenciais reais e provas ponta a ponta. Por padrao,
nao cria usuario, nao chama IA, nao envia notificacao e nao dispara pagamento.

Uso:
  python -B tools/validate_public_sale_readiness.py
  python -B tools/validate_public_sale_readiness.py --env-file .env.production
  python -B tools/validate_public_sale_readiness.py --live-auth-reading
  python -B tools/validate_public_sale_readiness.py --live-notifications
  python -B tools/validate_public_sale_readiness.py --public-base-url https://madamedoluar.com.br
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


@dataclass
class Gate:
    name: str
    status: str
    detail: str


def _run(command: list[str], timeout: int = 180) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        return completed.returncode == 0, output
    except Exception as exc:
        return False, str(exc)


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _has_env(*keys: str) -> bool:
    return all(bool(os.getenv(key, "").strip()) for key in keys)


def _routes() -> set[str]:
    import api

    return {route.path for route in api.app.routes}


def _ok(name: str, detail: str) -> Gate:
    return Gate(name, "PASS", detail)


def _fail(name: str, detail: str) -> Gate:
    return Gate(name, "FAIL", detail)


def _blocked(name: str, detail: str) -> Gate:
    return Gate(name, "BLOCKED", detail)


def _skip(name: str, detail: str) -> Gate:
    return Gate(name, "SKIP", detail)


def _file_has(path: str, *markers: str) -> bool:
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    return all(marker in text for marker in markers)


def _any_file_has(paths: list[str], marker: str) -> bool:
    for path in paths:
        if marker in (ROOT / path).read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def _check_routes(name: str, required: set[str]) -> Gate:
    missing = sorted(required - _routes())
    if missing:
        return _fail(name, "Rotas ausentes: " + ", ".join(missing))
    return _ok(name, "Rotas obrigatorias carregadas.")


def gate_auth_profile(live: bool) -> Gate:
    base = _check_routes("Cadastro, login e perfil", {"/auth/register", "/auth/login", "/me/profile", "/api/perfil"})
    if base.status != "PASS":
        return base
    if not _file_has("frontend/index.html", "cadNome", "loginEmail", "perfilFormDados"):
        return _fail(base.name, "Frontend nao possui cadastro, login e perfil completos.")
    if not live:
        return _blocked(base.name, "Implementado localmente; rode com --live-auth-reading para provar cadastro/login/perfil no Supabase real.")

    from fastapi.testclient import TestClient
    import api

    email = f"public-sale-{uuid.uuid4().hex[:10]}@madamedoluar.test"
    password = "VendaPublica123!"
    client = TestClient(api.app)
    register = client.post(
        "/auth/register",
        json={
            "nome": "Teste Venda Publica",
            "email": email,
            "senha": password,
            "whatsapp": None,
            "terms_accepted": True,
            "privacy_accepted": True,
            "ai_notice_accepted": True,
            "email_opt_in": False,
            "whatsapp_opt_in": False,
        },
    )
    if register.status_code >= 400:
        return _fail(base.name, f"Cadastro falhou HTTP {register.status_code}: {register.text[:300]}")
    login = client.post("/auth/login", json={"email": email, "senha": password})
    if login.status_code >= 400:
        return _fail(base.name, f"Login falhou HTTP {login.status_code}: {login.text[:300]}")
    if "mdl_access_token" not in client.cookies:
        return _fail(base.name, "Login nao retornou cookie de sessao.")
    profile = client.get("/api/perfil")
    if profile.status_code >= 400:
        return _fail(base.name, f"Perfil autenticado falhou HTTP {profile.status_code}: {profile.text[:300]}")
    return _ok(base.name, f"Cadastro, login e perfil validados com usuario {email}.")


def gate_daily_card(live: bool) -> Gate:
    base = _check_routes("Carta do dia autenticada", {"/api/carta-do-dia"})
    if base.status != "PASS":
        return base
    if not live:
        return _blocked(base.name, "Endpoint exige usuario autenticado; rode com --live-auth-reading para chamar com JWT real.")

    from fastapi.testclient import TestClient
    import api

    email = f"daily-sale-{uuid.uuid4().hex[:10]}@madamedoluar.test"
    password = "VendaPublica123!"
    client = TestClient(api.app)
    register = client.post(
        "/auth/register",
        json={
            "nome": "Teste Carta Publica",
            "email": email,
            "senha": password,
            "terms_accepted": True,
            "privacy_accepted": True,
            "ai_notice_accepted": True,
        },
    )
    if register.status_code >= 400:
        return _fail(base.name, f"Cadastro preparatorio falhou HTTP {register.status_code}: {register.text[:300]}")
    if "mdl_access_token" not in client.cookies:
        return _fail(base.name, "Cadastro preparatorio nao retornou cookie de sessao.")
    daily = client.post("/api/carta-do-dia", json={}, timeout=90)
    if daily.status_code >= 400:
        return _fail(base.name, f"Carta do dia falhou HTTP {daily.status_code}: {daily.text[:300]}")
    data = daily.json()
    if not data.get("carta") or not data.get("mensagem"):
        return _fail(base.name, "Resposta nao contem carta e mensagem.")
    return _ok(base.name, f"Carta do dia autenticada validada com usuario {email}.")


def gate_three_cards_ai(live: bool) -> Gate:
    base = _check_routes("Leitura de 3 cartas com IA real", {"/readings", "/api/leitura"})
    if base.status != "PASS":
        return base
    if not _has_env("GEMINI_API_KEY"):
        return _fail(base.name, "GEMINI_API_KEY ausente.")
    if not live:
        return _blocked(base.name, "Codigo e credencial existem; rode com --live-auth-reading para provar resposta real da IA.")

    from fastapi.testclient import TestClient
    import api

    email = f"reading-sale-{uuid.uuid4().hex[:10]}@madamedoluar.test"
    password = "VendaPublica123!"
    client = TestClient(api.app)
    register = client.post(
        "/auth/register",
        json={
            "nome": "Teste Leitura Publica",
            "email": email,
            "senha": password,
            "terms_accepted": True,
            "privacy_accepted": True,
            "ai_notice_accepted": True,
        },
    )
    if register.status_code >= 400:
        return _fail(base.name, f"Cadastro preparatorio falhou HTTP {register.status_code}: {register.text[:300]}")
    if "mdl_access_token" not in client.cookies:
        return _fail(base.name, "Cadastro preparatorio nao retornou cookie de sessao.")

    daily = client.post("/api/carta-do-dia", json={}, timeout=90)
    if daily.status_code >= 400:
        return _fail("Carta do dia autenticada", f"Carta do dia falhou HTTP {daily.status_code}: {daily.text[:300]}")
    reading = client.post(
        "/api/leitura",
        json={"pergunta": "O que preciso compreender para tomar uma boa decisao profissional esta semana?", "tipo": "tres_cartas"},
        timeout=120,
    )
    if reading.status_code >= 400:
        return _fail(base.name, f"Leitura falhou HTTP {reading.status_code}: {reading.text[:300]}")
    data = reading.json()
    if len(data.get("cartas") or []) != 3 or not data.get("interpretacao"):
        return _fail(base.name, "Resposta nao contem 3 cartas e interpretacao.")
    return _ok(base.name, f"IA real retornou leitura e carta do dia para {email}.")


def gate_payment_and_webhook(public_base_url: str | None) -> list[Gate]:
    gates: list[Gate] = []
    payment_name = "Pagamento real ponta a ponta"
    webhook_name = "Webhook libera acesso sem manual"

    if not _has_env("MERCADO_PAGO_ACCESS_TOKEN", "MERCADO_PAGO_WEBHOOK_SECRET"):
        gates.append(_fail(payment_name, "MERCADO_PAGO_ACCESS_TOKEN ou MERCADO_PAGO_WEBHOOK_SECRET ausente."))
        gates.append(_fail(webhook_name, "Webhook Mercado Pago nao pode ser validado sem secret."))
        return gates

    notification_url = os.getenv("MERCADO_PAGO_NOTIFICATION_URL", "")
    if not notification_url.startswith("https://"):
        gates.append(_fail(payment_name, "MERCADO_PAGO_NOTIFICATION_URL precisa ser HTTPS."))
        gates.append(_fail(webhook_name, "Webhook final precisa usar HTTPS."))
        return gates

    if "loca.lt" in notification_url or "localhost" in notification_url or "127.0.0.1" in notification_url:
        gates.append(_blocked(payment_name, f"Webhook atual aponta para ambiente temporario: {notification_url}"))
        gates.append(_blocked(webhook_name, "Para venda publica, configurar dominio final no Mercado Pago e validar webhook automatico."))
        return gates

    ok, output = _run([sys.executable, "-B", "tools/test_payment.py"], timeout=60)
    if not ok:
        gates.append(_fail(payment_name, "Mercado Pago API falhou: " + output[:500]))
    else:
        gates.append(_blocked(payment_name, "Mercado Pago conectado; ainda exige checkout real pago no ambiente final."))

    if public_base_url:
        ok, output = _run([sys.executable, "-B", "tools/deploy_smoke_test.py", "--base-url", public_base_url], timeout=120)
        if not ok:
            gates.append(_fail(webhook_name, "Smoke publico falhou antes do webhook: " + output[:500]))
        else:
            gates.append(_blocked(webhook_name, "Smoke publico OK; rode validate_mercado_pago_webhook_e2e com pagamento sandbox/final."))
    else:
        gates.append(_blocked(webhook_name, "Informe --public-base-url e rode validate_mercado_pago_webhook_e2e no dominio final."))
    return gates


def gate_email(live: bool) -> Gate:
    name = "Email real validado"
    if not _has_env("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"):
        return _fail(name, "SMTP_HOST, SMTP_PORT, SMTP_USER ou SMTP_PASS ausente.")
    if not live:
        return _blocked(name, "Credenciais existem; rode com --live-notifications para validar login SMTP.")
    import smtplib

    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT") or 587), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        return _ok(name, "Login SMTP validado.")
    except Exception as exc:
        return _fail(name, f"SMTP falhou: {exc}")


def gate_whatsapp(live: bool) -> Gate:
    name = "WhatsApp real validado ou removido da promessa"
    front = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8", errors="replace").lower()
    promised = "whatsapp" in front
    if not promised:
        return _ok(name, "WhatsApp nao aparece como promessa comercial no frontend principal.")
    if not _has_env("WHATSAPP_API_URL", "WHATSAPP_API_TOKEN"):
        return _fail(name, "WhatsApp e prometido no frontend, mas credenciais do provedor estao ausentes.")
    if _env_bool("ALLOW_SIMULATED_NOTIFICATIONS"):
        return _fail(name, "ALLOW_SIMULATED_NOTIFICATIONS esta ativo; venda publica exige envio real ou remover promessa.")
    if not live:
        return _blocked(name, "Credenciais existem; rode com --live-notifications para enviar teste real e registrar log.")
    ok, output = _run([sys.executable, "-B", "tools/test_whatsapp_uazapi.py"], timeout=90)
    return _ok(name, "Envio WhatsApp real validado.") if ok else _fail(name, output[:500])


def gate_admin() -> Gate:
    base = _check_routes("Admin acompanha usuarios, pagamentos e mensagens", {"/admin/dashboard", "/admin/users", "/admin/payments", "/admin/messages"})
    if base.status != "PASS":
        return base
    if not _file_has("frontend/admin.html", "data-view=\"users\"", "data-view=\"payments\"", "data-view=\"messages\""):
        return _fail(base.name, "Admin visual nao possui abas obrigatorias.")
    return _ok(base.name, "Rotas e UI admin cobrem usuarios, pagamentos e mensagens.")


def gate_logs() -> Gate:
    routes = _check_routes("Logs principais ativos", {"/admin/logs", "/admin/audit", "/admin/errors", "/health/detailed"})
    if routes.status != "PASS":
        return routes
    files = [
        "app/legacy_api.py",
        "app/modules/auth/service.py",
        "app/modules/readings/router.py",
        "app/modules/payments/router.py",
        "app/modules/webhooks/router.py",
        "app/modules/admin/router.py",
    ]
    required = ["registrar_log", "registrar_auditoria", "track_server_event", "api_error", "payment_approved", "reading_completed"]
    missing = [marker for marker in required if not _any_file_has(files, marker)]
    if missing:
        return _fail(routes.name, "Eventos/logs ausentes no backend modular: " + ", ".join(missing))
    return _ok(routes.name, "Logs, auditoria, erros e health estao expostos no admin/API.")


def gate_backup_restore() -> Gate:
    name = "Backup automatico e restore testado"
    required_files = [
        "tools/backup_database.py",
        "tools/restore_database_test.py",
        "tools/backup_and_restore_check.py",
        "architecture/backup_restore_runbook.md",
        "render.yaml",
    ]
    missing = [path for path in required_files if not (ROOT / path).exists()]
    if missing:
        return _fail(name, "Arquivos ausentes: " + ", ".join(missing))
    if not _file_has("render.yaml", "madame-do-luar-backup-check", "tools/backup_and_restore_check.py"):
        return _fail(name, "render.yaml nao agenda backup+restore automatico.")
    ok, output = _run([sys.executable, "-B", "tools/backup_and_restore_check.py"], timeout=360)
    if not ok:
        return _fail(name, output[:800])
    return _ok(name, "Backup e restore local validados; cron de producao configurado.")


def gate_monitoring_alerts() -> Gate:
    name = "Monitoramento e alertas operacionais"
    base = _check_routes(name, {"/health/detailed", "/admin/status", "/admin/alerts", "/admin/operations/daily-check", "/admin/jobs/alerts/check"})
    if base.status != "PASS":
        return base
    if not _file_has("render.yaml", "madame-do-luar-daily-check", "PENDING_MESSAGES_ALERT_THRESHOLD"):
        return _fail(name, "Cron/check diario ou thresholds nao configurados no render.yaml.")
    if not _file_has("tools/db_client.py", "gerar_alertas_operacionais", "rotina_diaria_verificacao", "health_detalhado"):
        return _fail(name, "Funcoes de health/alerta/rotina diaria ausentes.")
    return _ok(name, "Health, status admin, alertas e cron diario configurados.")


def gate_load_smoke(public_base_url: str | None) -> Gate:
    name = "Teste de carga leve"
    base_url = public_base_url or os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    if not (ROOT / "tools" / "load_smoke_test.py").exists():
        return _fail(name, "tools/load_smoke_test.py ausente.")
    if base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1"):
        return _blocked(name, "Teste de carga local disponivel; informe --public-base-url para carga leve no dominio final.")
    ok, output = _run([sys.executable, "-B", "tools/load_smoke_test.py", "--base-url", base_url, "--requests", "60", "--concurrency", "10"], timeout=180)
    if not ok:
        return _fail(name, output[:800])
    return _ok(name, output[:300])


def gate_legal() -> Gate:
    name = "Politica de privacidade e termos publicados"
    required = ["frontend/privacidade.html", "frontend/termos.html"]
    missing = [path for path in required if not (ROOT / path).exists()]
    if missing:
        return _fail(name, "Arquivos ausentes: " + ", ".join(missing))
    if not _file_has("frontend/index.html", "/termos.html", "/privacidade.html"):
        return _fail(name, "Frontend principal nao linka termos e privacidade.")
    return _ok(name, "Termos e privacidade publicados no frontend.")


def gate_https(public_base_url: str | None) -> Gate:
    name = "Deploy seguro com HTTPS"
    base_url = public_base_url or os.getenv("APP_BASE_URL", "")
    if not base_url.startswith("https://"):
        return _fail(name, "APP_BASE_URL/public URL precisa usar HTTPS.")
    if "loca.lt" in base_url or "localhost" in base_url or "127.0.0.1" in base_url:
        return _blocked(name, f"URL atual nao e dominio final de producao: {base_url}")
    if not public_base_url:
        return _blocked(name, "HTTPS configurado em env; informe --public-base-url para smoke test publico.")
    ok, output = _run([sys.executable, "-B", "tools/deploy_smoke_test.py", "--base-url", public_base_url], timeout=120)
    return _ok(name, "Smoke HTTPS publico aprovado.") if ok else _fail(name, output[:500])


def gate_frontend_truth() -> Gate:
    name = "Frontend sem texto quebrado nem dado falso"
    ok, output = _run([sys.executable, "-B", "tools/check_text_quality.py"], timeout=60)
    if not ok:
        return _fail(name, output[:800])
    front = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8", errors="replace")
    if "Nenhuma leitura simulada foi exibida" not in front:
        return _fail(name, "Frontend nao deixa explicito quando a leitura real falha.")
    return _ok(name, "Text quality OK e sem fallback silencioso de leitura simulada.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida se o Madame do Luar pode ser vendido publicamente.")
    parser.add_argument("--env-file", default=".env", help="Arquivo de ambiente a carregar.")
    parser.add_argument("--live-auth-reading", action="store_true", help="Cria usuario de teste, valida login, perfil, carta do dia e leitura IA real.")
    parser.add_argument("--live-notifications", action="store_true", help="Valida SMTP e envia WhatsApp real para WHATSAPP_TEST_NUMBER.")
    parser.add_argument("--public-base-url", help="URL publica HTTPS para smoke test.")
    args = parser.parse_args()

    load_dotenv(ROOT / args.env_file, override=True)

    gates: list[Gate] = [
        gate_auth_profile(args.live_auth_reading),
        gate_daily_card(args.live_auth_reading),
        gate_three_cards_ai(args.live_auth_reading),
        *gate_payment_and_webhook(args.public_base_url),
        gate_email(args.live_notifications),
        gate_whatsapp(args.live_notifications),
        gate_admin(),
        gate_logs(),
        gate_backup_restore(),
        gate_monitoring_alerts(),
        gate_load_smoke(args.public_base_url),
        gate_legal(),
        gate_https(args.public_base_url),
        gate_frontend_truth(),
    ]

    print("Gate de venda publica - Madame do Luar")
    print("=" * 48)
    for gate in gates:
        print(f"[{gate.status}] {gate.name}")
        print(f"  {gate.detail}")

    blocking = [gate for gate in gates if gate.status in {"FAIL", "BLOCKED"}]
    if blocking:
        print("\nRESULTADO: NAO PRONTO PARA VENDA PUBLICA")
        print(f"Itens bloqueantes: {len(blocking)}")
        return 1

    print("\nRESULTADO: PRONTO PARA VENDA PUBLICA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
