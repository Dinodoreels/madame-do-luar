-- Migration: automacoes WhatsApp/email, regras e logs de notificacao.
-- Pode ser executada no Supabase SQL Editor depois da base operacional.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_in BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_in_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_out_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE message_events DROP CONSTRAINT IF EXISTS message_events_tipo_check;
ALTER TABLE message_events ADD CONSTRAINT message_events_tipo_check
  CHECK (tipo IN (
    '24h',
    '3d',
    '7d',
    '30d',
    'marketing',
    'welcome',
    'carrinho_abandonado',
    'pos_venda',
    'recompra',
    'reativacao'
  ));

ALTER TABLE message_events DROP CONSTRAINT IF EXISTS message_events_status_check;
ALTER TABLE message_events ADD CONSTRAINT message_events_status_check
  CHECK (status IN ('pending', 'processing', 'sent', 'failed', 'skipped', 'cancelled'));

ALTER TABLE message_events ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS variables JSONB DEFAULT '{}'::jsonb;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS max_attempts INTEGER DEFAULT 3;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_message_events_status_due
  ON message_events(status, agendado_para);
CREATE INDEX IF NOT EXISTS idx_message_events_user_tipo
  ON message_events(user_id, tipo);
CREATE INDEX IF NOT EXISTS idx_message_events_payment_id
  ON message_events(payment_id);

CREATE TABLE IF NOT EXISTS automation_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    audience_filter JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS automation_steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id UUID REFERENCES automation_rules(rule_id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL DEFAULT 1,
    delay_minutes INTEGER NOT NULL DEFAULT 0,
    channel TEXT NOT NULL CHECK (channel IN ('email', 'whatsapp')),
    subject TEXT,
    template TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_automation_rules_event_type
  ON automation_rules(event_type);
CREATE INDEX IF NOT EXISTS idx_automation_steps_rule_order
  ON automation_steps(rule_id, step_order);

CREATE TABLE IF NOT EXISTS notification_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_event_id UUID REFERENCES message_events(message_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    channel TEXT CHECK (channel IN ('email', 'whatsapp')),
    type TEXT,
    recipient TEXT,
    subject TEXT,
    status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped', 'simulated')),
    error_message TEXT,
    provider_response JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_logs_user_id
  ON notification_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_status
  ON notification_logs(status);
CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at
  ON notification_logs(created_at);
