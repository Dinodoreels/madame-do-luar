"""
Valida a Sprint 6 - Producao.

O validador confirma os artefatos de LGPD, monitoramento, backup, deploy e
go-live que ficam sob controle do repositorio. Quando executado com as
credenciais locais, tambem consulta o Supabase para validar o painel operacional.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import api
import db_client
from backup_database import sha256_file


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _run(command: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    output = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode == 0, output


def _validate_routes_and_pages() -> None:
    routes = {route.path for route in api.app.routes}
    required_routes = {
        "/health/detailed",
        "/api/health/detailed",
        "/lgpd/export",
        "/api/lgpd/export",
        "/lgpd/account",
        "/api/lgpd/account",
        "/admin/status",
        "/api/admin/status",
        "/admin/metrics/conversion",
        "/admin/metrics/retention",
        "/admin/metrics/revenue",
        "/admin/operations/daily-check",
    }
    missing = sorted(required_routes - routes)
    _require(not missing, "Rotas de producao ausentes: " + ", ".join(missing))

    for path in (
        "frontend/privacidade.html",
        "frontend/termos.html",
        "frontend/ia.html",
        "frontend/admin.html",
        "frontend/pagamento/sucesso/index.html",
        "frontend/pagamento/cancelado/index.html",
    ):
        _require((ROOT / path).exists(), f"Pagina/arquivo obrigatorio ausente: {path}")

    app_js = _read("frontend/app.js")
    for marker in ("terms_accepted", "privacy_accepted", "ai_notice_accepted", "/lgpd/export", "/lgpd/account"):
        _require(marker in app_js, f"Marcador LGPD ausente no frontend: {marker}")


def _validate_deploy_artifacts() -> None:
    required_files = (
        "render.yaml",
        "scripts/deploy/deploy_render.ps1",
        ".env.production.example",
        "tools/predeploy_check.py",
        "tools/deploy_smoke_test.py",
        "tools/daily_operation_check.py",
        "architecture/deploy_runbook.md",
        "architecture/pre_deploy_checklist.md",
        "architecture/rollback_checklist.md",
        "architecture/maintenance_runbook.md",
        "architecture/go_live_checklist.md",
        "architecture/backup_restore_runbook.md",
    )
    for path in required_files:
        _require((ROOT / path).exists(), f"Artefato de producao ausente: {path}")

    render = _read("render.yaml")
    for marker in (
        "type: web",
        "type: worker",
        "type: cron",
        "healthCheckPath: /health/detailed",
        "madamedoluar.com.br",
        "sync: false",
        "generateValue: true",
        "APP_ENV",
        "APP_CORS_ORIGINS",
    ):
        _require(marker in render, f"render.yaml sem marcador obrigatorio: {marker}")

    smoke = _read("tools/deploy_smoke_test.py")
    for path in ("/health/detailed", "/api/status", "/admin.html", "/privacidade.html", "/termos.html"):
        _require(path in smoke, f"Smoke test nao cobre {path}")


def _validate_backup_manifest() -> dict:
    manifest_file = ROOT / "backups" / "latest_backup_manifest.json"
    restore_file = ROOT / "backups" / "latest_restore_test.json"
    _require(manifest_file.exists(), "Manifesto de backup ausente.")
    _require(restore_file.exists(), "Relatorio de restore ausente.")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    backup_file = Path(manifest.get("backup_file") or "")
    if not backup_file.is_absolute():
        backup_file = ROOT / backup_file
    _require(backup_file.exists(), f"Arquivo de backup nao encontrado: {backup_file}")
    _require(manifest.get("sha256") == sha256_file(backup_file), "SHA256 do backup nao confere com manifesto.")

    restore = json.loads(restore_file.read_text(encoding="utf-8"))
    restored_rows = int(restore.get("total_rows") or restore.get("rows") or 0)
    _require(restored_rows > 0, "Restore test nao reconstituiu registros.")
    return {"manifest": manifest, "restore": restore}


def _validate_live_monitoring() -> dict:
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        return {"skipped": True, "reason": "SUPABASE_URL/SUPABASE_KEY ausentes"}
    try:
        status = db_client.painel_status_operacional()
    except Exception as exc:
        return {"skipped": True, "reason": f"rede ou Supabase indisponivel: {exc}"}
    health = status.get("health", {})
    _require(health.get("status") in {"ok", "degraded"}, f"Health operacional bloqueante: {health}")
    for key in ("conversao", "retencao", "receita", "alertas_abertos", "mensagens_pendentes"):
        _require(key in status, f"Painel operacional sem campo: {key}")
    try:
        rotina = db_client.rotina_diaria_verificacao()
    except Exception as exc:
        return {"skipped": True, "reason": f"rotina diaria indisponivel: {exc}", "status": status}
    resultado = rotina.get("resultado", {})
    _require(resultado.get("health_status") in {"ok", "degraded"}, f"Rotina diaria com status invalido: {resultado}")
    return {"status": status, "rotina": rotina}


def main() -> None:
    load_dotenv(ROOT / ".env")
    _validate_routes_and_pages()
    _validate_deploy_artifacts()

    ok, output = _run([sys.executable, "-B", "tools/predeploy_check.py", "--env-file", ".env.production.example", "--allow-placeholders"])
    _require(ok, "Pre-deploy com .env.production.example falhou:\n" + output)

    backup = _validate_backup_manifest()
    live = _validate_live_monitoring()

    print("OK Sprint 6 producao validada.")
    print(f"Rotas carregadas: {len(api.app.routes)}")
    print(f"Backup: {backup['manifest'].get('backup_file')}")
    print(f"Restore total_rows: {backup['restore'].get('total_rows') or backup['restore'].get('rows')}")
    if live.get("skipped"):
        print(f"Monitoramento live: ignorado ({live['reason']})")
    else:
        print(f"Health live: {live['status']['health'].get('status')}")
        print(f"Alertas abertos: {len(live['status'].get('alertas_abertos') or [])}")


if __name__ == "__main__":
    main()
