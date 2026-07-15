# Fase 5 - Filas, Workers e Automacoes

## Decisao

Usar fila simples baseada em `reprocess_queue` nesta fase.

Motivos:

- O projeto ja possui `reprocess_queue`, `message_events`, `notification_logs` e `internal_alerts`.
- Evita custo operacional de Redis/Celery antes de volume real.
- Mantem jobs auditaveis no banco atual.
- Permite evoluir depois para Redis/RQ ou Celery mantendo a mesma fronteira de `JobQueueService`.

## Componentes

- `app/modules/automation/job_queue.py`: service de fila, retries, idempotencia, dead-letter e alerta de fila travada.
- `tools/job_worker.py`: worker CLI.
- `scheduler_job_worker.bat`: launcher local Windows.
- `architecture/migration_phase5_job_queue.sql`: migration de referencia para indices e checks.
- `POST /api/readings/enqueue`: cria leitura pendente e enfileira IA.
- `GET /api/readings/jobs/{queue_id}`: consulta status da leitura enfileirada.
- `GET /api/admin/jobs`: painel/lista de jobs.
- `POST /api/admin/jobs/process`: processamento manual pelo admin.
- `POST /api/admin/jobs/{queue_id}/retry`: reprocessamento auditado.
- `POST /api/admin/jobs/alerts/check`: alerta de fila travada.

## Tipos de job

- `reading` com `payload.job_kind=ai_reading`: gera interpretacao de leitura em segundo plano.
- `notification`: processa uma mensagem especifica ou pendencias de notificacao.
- `notification` com `payload.job_kind=automation`: executa automacoes agendadas.
- `payment` e `webhook`: reservados para reprocessamentos financeiros/admin.

## Estados

- `pending`: aguardando processamento.
- `processing`: worker pegou o job.
- `done`: concluido.
- `failed`: dead-letter logico apos exceder tentativas.
- `cancelled`: cancelado manualmente.

## Regras

- Todo job recebe `payload.idempotency_key`.
- Falha antes do limite volta para `pending` com `scheduled_at` futuro.
- Falha no limite vira `failed`, marca `payload.dead_letter=true`, cria auditoria `JOB_DEAD_LETTER` e alerta interno.
- Reprocessamento manual usa `retry_job`, volta para `pending` e registra `JOB_REQUEUED`.
- Fila travada gera alerta unico por dia via `alert_if_stalled`.

## Proxima Evolucao

- Migrar para Redis/RQ ou Celery se houver volume sustentado.
- Quebrar `admin/router.py` em subrouters de jobs, billing, ops e reports.
- Adicionar worker dedicado por tipo quando IA/notificacao tiverem perfis de carga diferentes.
