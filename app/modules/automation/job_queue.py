from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import automation_engine
import db_client
from app.modules.readings.service import gemini_model, gerar_interpretacao

from .repository import AutomationRepository


JobHandler = Callable[[dict[str, Any]], dict[str, Any]]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scheduled_iso(minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def stable_idempotency_key(type_: str, payload: dict[str, Any]) -> str:
    raw = payload.get("idempotency_key") or json.dumps({"type": type_, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:32]


class JobQueueService:
    def __init__(self, repository: AutomationRepository | None = None):
        self.repository = repository or AutomationRepository()

    def enqueue(
        self,
        type_: str,
        payload: dict[str, Any],
        *,
        related_payment_id: str | None = None,
        related_reading_id: str | None = None,
        delay_minutes: int = 0,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        logical_type = type_
        type_ = self._normalize_type(type_)
        max_attempts = max_attempts or int(os.getenv("JOB_QUEUE_MAX_ATTEMPTS", "3"))
        key = stable_idempotency_key(type_, payload)
        existing = self.repository.list_jobs(
            filters=f"type=eq.{type_}&status=in.(pending,processing,done)",
            limit=100,
            order="created_at.desc",
        )
        for job in existing:
            job_payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
            if job_payload.get("idempotency_key") == key:
                return {**job, "duplicado": True}

        enriched_payload = {**payload, "idempotency_key": key, "job_kind": payload.get("job_kind") or logical_type}
        job = self.repository.enqueue(
            type_,
            enriched_payload,
            related_payment_id=related_payment_id,
            related_reading_id=related_reading_id,
        )
        if "erro" in job:
            return job
        update = {
            "scheduled_at": scheduled_iso(delay_minutes),
            "max_attempts": max(1, int(max_attempts)),
            "updated_at": now_iso(),
        }
        return self.repository.update_job(job["queue_id"], update)

    def list_jobs(self, status: str | None = None, type_: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        filters = []
        if status:
            filters.append(f"status=eq.{status}")
        if type_:
            filters.append(f"type=eq.{self._normalize_type(type_)}")
        return self.repository.list_jobs(filters="&".join(filters), limit=min(max(limit, 1), 300), order="scheduled_at.asc")

    def job_status(self, queue_id: str) -> dict[str, Any] | None:
        return self.repository.get_job(queue_id)

    def process_due(self, limit: int = 25, dry_run: bool = False) -> dict[str, Any]:
        due = datetime.now(timezone.utc)
        candidates = self.repository.list_jobs(
            filters="status=eq.pending",
            limit=min(max(limit * 3, 1), 300),
            order="scheduled_at.asc",
        )
        jobs = [job for job in candidates if self._is_due(job, due)][: min(max(limit, 1), 100)]
        result = {"processed": 0, "done": 0, "failed": 0, "retry": 0, "jobs": []}
        for job in jobs:
            processed = self.process_job(job, dry_run=dry_run)
            result["processed"] += 1
            status = processed.get("status")
            if status == "done":
                result["done"] += 1
            elif status == "pending":
                result["retry"] += 1
            elif status == "failed":
                result["failed"] += 1
            result["jobs"].append(processed)
        self.alert_if_stalled()
        return result

    def _is_due(self, job: dict[str, Any], due: datetime) -> bool:
        raw = job.get("scheduled_at")
        if not raw:
            return True
        try:
            scheduled = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return True
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        return scheduled <= due

    def process_job(self, job: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"queue_id": job.get("queue_id"), "status": "dry_run", "type": job.get("type")}
        queue_id = job["queue_id"]
        attempts = int(job.get("attempts") or 0) + 1
        self.repository.update_job(queue_id, {"status": "processing", "attempts": attempts, "updated_at": now_iso()})
        try:
            output = self._handler_for(job)(job)
            self.repository.update_job(queue_id, {"status": "done", "processed_at": now_iso(), "error_message": None, "updated_at": now_iso()})
            self.repository.audit(
                "JOB_PROCESSED",
                entity_type="reprocess_queue",
                entity_id=queue_id,
                after_data={"status": "done", "attempts": attempts},
                metadata={"type": job.get("type"), "output": output},
            )
            return {"queue_id": queue_id, "status": "done", "attempts": attempts, "output": output}
        except Exception as exc:
            return self._handle_failure(job, attempts, exc)

    def retry_job(self, queue_id: str, admin_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
        job = self.repository.get_job(queue_id)
        if not job:
            return {"erro": "Job nao encontrado."}
        payload = {
            "status": "pending",
            "scheduled_at": now_iso(),
            "error_message": reason or None,
            "updated_at": now_iso(),
        }
        updated = self.repository.update_job(queue_id, payload)
        self.repository.audit(
            "JOB_REQUEUED",
            entity_type="reprocess_queue",
            entity_id=queue_id,
            admin_id=admin_id,
            after_data=payload,
            metadata={"reason": reason},
        )
        return updated

    def alert_if_stalled(self) -> dict[str, Any]:
        threshold = int(os.getenv("JOB_QUEUE_STALLED_MINUTES", "30"))
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold)).isoformat()
        stalled = self.repository.list_jobs(filters=f"status=eq.processing&updated_at=lt.{cutoff}", limit=50, order="updated_at.asc")
        if not stalled:
            return {"stalled": 0}
        alert = self.repository.create_alert(
            "job_queue_stalled",
            "Fila de jobs travada",
            f"{len(stalled)} job(s) estao em processamento ha mais de {threshold} minutos.",
            "warning",
            metadata={"fingerprint": f"job_queue_stalled:{datetime.now(timezone.utc).date().isoformat()}", "jobs": [j.get("queue_id") for j in stalled]},
        )
        return {"stalled": len(stalled), "alert": alert}

    def _handle_failure(self, job: dict[str, Any], attempts: int, exc: Exception) -> dict[str, Any]:
        queue_id = job["queue_id"]
        max_attempts = int(job.get("max_attempts") or 3)
        message = str(exc)[:500]
        if attempts < max_attempts:
            retry_delay = int(os.getenv("JOB_QUEUE_RETRY_DELAY_MINUTES", "15"))
            update = {"status": "pending", "scheduled_at": scheduled_iso(retry_delay), "error_message": message, "updated_at": now_iso()}
            self.repository.update_job(queue_id, update)
            self.repository.log("JOB_RETRY_SCHEDULED", "Job reagendado apos falha.", metadata={"queue_id": queue_id, "attempts": attempts, "erro": message}, severity="warning")
            return {"queue_id": queue_id, "status": "pending", "attempts": attempts, "error": message}

        self._dead_letter(job, attempts, message)
        return {"queue_id": queue_id, "status": "failed", "attempts": attempts, "error": message}

    def _dead_letter(self, job: dict[str, Any], attempts: int, error: str) -> None:
        queue_id = job["queue_id"]
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        dead_payload = {**payload, "dead_letter": True, "dead_letter_at": now_iso()}
        self.repository.update_job(queue_id, {"status": "failed", "payload": dead_payload, "error_message": error, "processed_at": now_iso(), "updated_at": now_iso()})
        self.repository.audit(
            "JOB_DEAD_LETTER",
            entity_type="reprocess_queue",
            entity_id=queue_id,
            after_data={"status": "failed", "attempts": attempts, "error_message": error},
            metadata={"type": job.get("type"), "payload": dead_payload},
        )
        if job.get("related_reading_id") and payload.get("job_kind") == "ai_reading":
            self._fail_reading(job, error)
        self.repository.create_alert(
            "job_dead_letter",
            "Job enviado para dead-letter",
            f"Job {queue_id} falhou apos {attempts} tentativa(s).",
            "error",
            metadata={"fingerprint": f"job_dead_letter:{queue_id}", "queue_id": queue_id, "type": job.get("type"), "error": error},
        )

    def _handler_for(self, job: dict[str, Any]) -> JobHandler:
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        kind = payload.get("job_kind") or job.get("type")
        if kind == "ai_reading":
            return self._process_ai_reading
        if kind == "notification":
            return self._process_notification
        if kind == "automation":
            return self._process_automation
        if job.get("type") == "notification":
            return self._process_notification
        raise RuntimeError(f"Tipo de job sem handler: {kind}")

    def _process_ai_reading(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") or {}
        reading_id = job.get("related_reading_id") or payload.get("reading_id")
        cards = payload["cartas"]
        interpretacao = gerar_interpretacao(payload["pergunta"], [cards["passado"], cards["presente"], cards["futuro"]])
        updated = self.repository.readings.update(
            "reading_id",
            reading_id,
            {
                "interpretacao": interpretacao,
                "model": gemini_model(),
                "status": "concluida",
                "error_message": None,
            },
        )
        if payload.get("credit_transaction_id"):
            db_client.vincular_transacao_credito(payload["credit_transaction_id"], related_reading_id=reading_id)
        if payload.get("primeira_gratis"):
            db_client.marcar_primeira_tiragem_usada(payload["user_id"])
        try:
            automation_engine.agendar_retorno_leitura(payload["user_id"], payload.get("question_id"))
        except Exception as exc:
            self.repository.log("AUTOMATION_SCHEDULE_FAILED", "Nao foi possivel agendar retorno automatico de leitura.", user_id=payload.get("user_id"), metadata={"question_id": payload.get("question_id"), "erro": str(exc)}, severity="warning")
        return {"reading_id": reading_id, "reading": updated}

    def _fail_reading(self, job: dict[str, Any], error: str) -> None:
        payload = job.get("payload") or {}
        reading_id = job.get("related_reading_id") or payload.get("reading_id")
        if reading_id:
            self.repository.readings.update("reading_id", reading_id, {"status": "erro", "error_message": error})
        if payload.get("custo_creditos", 0) > 0:
            db_client.estornar_creditos(payload.get("user_id"), int(payload["custo_creditos"]), "Estorno automatico: leitura enfileirada falhou definitivamente.", related_reading_id=reading_id)

    def _process_notification(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") or {}
        message_id = payload.get("message_id")
        if not message_id:
            return automation_engine.processar_pendentes(limit=int(payload.get("limit") or 50))
        evento = db_client.buscar_por_id("message_events", "message_id", message_id)
        if not evento:
            raise RuntimeError("Evento de notificacao nao encontrado.")
        return automation_engine.processar_evento(evento)

    def _process_automation(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") or {}
        action = payload.get("action") or "process_pending_notifications"
        if action == "sync_default_rules":
            return automation_engine.sincronizar_regras_padrao()
        if action == "daily_cards":
            return automation_engine.agendar_cartas_do_dia_renovadas(limit=int(payload.get("limit") or 1000), dry_run=bool(payload.get("dry_run")))
        return automation_engine.processar_pendentes(limit=int(payload.get("limit") or 100))

    def _normalize_type(self, type_: str) -> str:
        if type_ in ("ai_reading", "reading"):
            return "reading"
        if type_ in ("automation", "notification"):
            return "notification"
        if type_ in ("payment", "webhook"):
            return type_
        return "notification"


job_queue_service = JobQueueService()
