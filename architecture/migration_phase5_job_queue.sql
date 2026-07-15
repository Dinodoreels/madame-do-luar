-- Fase 5 - fila simples baseada no banco
-- Aplicar no Supabase quando houver acesso SQL.

ALTER TABLE reprocess_queue DROP CONSTRAINT IF EXISTS reprocess_queue_type_check;
ALTER TABLE reprocess_queue ADD CONSTRAINT reprocess_queue_type_check
  CHECK (type IN ('webhook', 'reading', 'payment', 'notification'));

ALTER TABLE reprocess_queue DROP CONSTRAINT IF EXISTS reprocess_queue_status_check;
ALTER TABLE reprocess_queue ADD CONSTRAINT reprocess_queue_status_check
  CHECK (status IN ('pending', 'processing', 'done', 'failed', 'cancelled'));

ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0;
ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS max_attempts INTEGER DEFAULT 3;
ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;
ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE reprocess_queue ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_reprocess_queue_status_scheduled
  ON reprocess_queue(status, scheduled_at);

CREATE INDEX IF NOT EXISTS idx_reprocess_queue_type_status
  ON reprocess_queue(type, status);

CREATE INDEX IF NOT EXISTS idx_reprocess_queue_payload_idempotency
  ON reprocess_queue ((payload->>'idempotency_key'));

ALTER TABLE readings DROP CONSTRAINT IF EXISTS readings_status_check;
ALTER TABLE readings ADD CONSTRAINT readings_status_check
  CHECK (status IN ('pendente', 'concluida', 'erro'));
