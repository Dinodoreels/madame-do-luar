-- Migration: base operacional para admin, creditos, prompts, logs e PIX
-- Execute no Supabase SQL Editor antes de usar os endpoints /api/admin/*.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Usuarios: roles, status e saldo de creditos.
ALTER TABLE users ADD COLUMN IF NOT EXISTS senha_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'cliente';
ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ativo';
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits_balance INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('cliente', 'admin', 'super_admin'));

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_check;
ALTER TABLE users ADD CONSTRAINT users_status_check
  CHECK (status IN ('ativo', 'bloqueado', 'inativo'));

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    reset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

-- Planos e pacotes.
CREATE TABLE IF NOT EXISTS plans (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) DEFAULT 0,
    credits INTEGER DEFAULT 0,
    duration_days INTEGER,
    benefits JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE plans ADD COLUMN IF NOT EXISTS benefits JSONB DEFAULT '[]'::jsonb;
ALTER TABLE plans ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_id UUID REFERENCES plans(plan_id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS credit_packages (
    package_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    credits INTEGER NOT NULL CHECK (credits > 0),
    price NUMERIC(10, 2) NOT NULL DEFAULT 0,
    bonus_credits INTEGER DEFAULT 0,
    validity_days INTEGER,
    benefits JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coupons (
    coupon_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    discount_type TEXT NOT NULL CHECK (discount_type IN ('percent', 'fixed')),
    discount_value NUMERIC(10, 2) NOT NULL CHECK (discount_value >= 0),
    max_uses INTEGER,
    used_count INTEGER DEFAULT 0,
    minimum_amount NUMERIC(10, 2) DEFAULT 0,
    starts_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
CREATE INDEX IF NOT EXISTS idx_coupons_status ON coupons(status);

CREATE TABLE IF NOT EXISTS plan_change_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    old_plan_id UUID REFERENCES plans(plan_id) ON DELETE SET NULL,
    new_plan_id UUID REFERENCES plans(plan_id) ON DELETE SET NULL,
    changed_by_admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    reason TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_change_history_user_id ON plan_change_history(user_id);
CREATE INDEX IF NOT EXISTS idx_plan_change_history_created_at ON plan_change_history(created_at);

-- Transacoes de creditos.
CREATE TABLE IF NOT EXISTS credit_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('add', 'remove', 'consume', 'refund')),
    amount INTEGER NOT NULL CHECK (amount > 0),
    reason TEXT,
    related_payment_id UUID,
    related_reading_id UUID,
    created_by_admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS related_payment_id UUID;
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS related_reading_id UUID;
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS created_by_admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_created_at ON credit_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_related_payment_id ON credit_transactions(related_payment_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_related_reading_id ON credit_transactions(related_reading_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_expires_at ON credit_transactions(expires_at);

-- Evolucao da tabela de pagamentos para PIX e conciliacao.
ALTER TABLE payments ADD COLUMN IF NOT EXISTS plan_id UUID REFERENCES plans(plan_id) ON DELETE SET NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS package_id UUID REFERENCES credit_packages(package_id) ON DELETE SET NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS product_type TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS product_name TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS amount NUMERIC(10, 2);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS method TEXT DEFAULT 'PIX';
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS transaction_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS qr_code_url TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS pix_copy_paste TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS checkout_url TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS webhook_payload JSONB;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway_payload JSONB DEFAULT '{}'::jsonb;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS credits_to_release INTEGER DEFAULT 0;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS credits_released BOOLEAN DEFAULT false;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS abandoned_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_status_check;
ALTER TABLE payments ADD CONSTRAINT payments_status_check
  CHECK (status IN ('pending', 'approved', 'failed', 'expired', 'cancelled', 'refused', 'refunded', 'error', 'abandoned'));

CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_transaction_id_unique
  ON payments(transaction_id)
  WHERE transaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_expires_at ON payments(expires_at);

CREATE TABLE IF NOT EXISTS payment_webhook_events (
    event_id TEXT PRIMARY KEY,
    payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL,
    gateway TEXT,
    event_type TEXT,
    transaction_id TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    processed BOOLEAN DEFAULT false,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_payment_webhook_events_payment_id ON payment_webhook_events(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_webhook_events_transaction_id ON payment_webhook_events(transaction_id);

CREATE TABLE IF NOT EXISTS internal_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_internal_alerts_status ON internal_alerts(status);
CREATE INDEX IF NOT EXISTS idx_internal_alerts_severity ON internal_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_internal_alerts_created_at ON internal_alerts(created_at);

CREATE TABLE IF NOT EXISTS reprocess_queue (
    queue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL CHECK (type IN ('webhook', 'reading', 'payment', 'notification')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed', 'cancelled')),
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    related_payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL,
    related_reading_id UUID REFERENCES readings(reading_id) ON DELETE SET NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reprocess_queue_status ON reprocess_queue(status);
CREATE INDEX IF NOT EXISTS idx_reprocess_queue_scheduled_at ON reprocess_queue(scheduled_at);

-- Prompts de IA versionados.
CREATE TABLE IF NOT EXISTS ai_prompts (
    prompt_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    reading_type TEXT NOT NULL,
    content TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_by_admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_prompts_reading_type ON ai_prompts(reading_type);

-- Configuracoes operacionais.
CREATE TABLE IF NOT EXISTS settings (
    setting_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    is_secret BOOLEAN DEFAULT false,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO settings (key, value, is_secret, updated_at) VALUES
('reading_cost_energia_do_dia', '0', false, NOW()),
('reading_cost_simples', '25', false, NOW()),
('reading_cost_geral', '25', false, NOW()),
('reading_cost_conselho_espiritual', '25', false, NOW()),
('reading_cost_sim_nao', '25', false, NOW()),
('reading_cost_amor', '50', false, NOW()),
('reading_cost_dinheiro', '50', false, NOW()),
('reading_cost_carreira', '50', false, NOW()),
('reading_cost_tres_cartas', '50', false, NOW()),
('reading_cost_personalizada', '100', false, NOW()),
('reading_cost_premium', '250', false, NOW()),
('credit_model_avulso_credits', '100', false, NOW()),
('credit_model_mensal_credits', '1500', false, NOW()),
('credit_model_anual_credits', '18250', false, NOW()),
('credit_model_tiragem_3_cartas_cost', '50', false, NOW())
ON CONFLICT (key) DO UPDATE
   SET value = EXCLUDED.value,
       is_secret = EXCLUDED.is_secret,
       updated_at = NOW();

-- Logs completos para auditoria.
CREATE TABLE IF NOT EXISTS system_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    severity TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_logs_user_id ON system_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_admin_id ON system_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_event_type ON system_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_system_logs_severity ON system_logs(severity);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);

-- Leituras: metadados de IA para relatorios.
ALTER TABLE readings ADD COLUMN IF NOT EXISTS prompt_id UUID REFERENCES ai_prompts(prompt_id) ON DELETE SET NULL;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS estimated_cost NUMERIC(12, 6) DEFAULT 0;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'concluida';
ALTER TABLE readings ADD COLUMN IF NOT EXISTS error_message TEXT;

ALTER TABLE readings DROP CONSTRAINT IF EXISTS readings_status_check;
ALTER TABLE readings ADD CONSTRAINT readings_status_check
  CHECK (status IN ('pendente', 'concluida', 'erro'));

-- Funcoes atomicas de creditos.
-- Usadas via Supabase REST RPC para evitar corrida de saldo.
CREATE OR REPLACE FUNCTION consume_user_credits(
    p_user_id UUID,
    p_amount INTEGER,
    p_reason TEXT DEFAULT 'Consumo de leitura',
    p_related_reading_id UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_balance INTEGER;
    v_new_balance INTEGER;
    v_transaction_id UUID;
BEGIN
    IF p_amount <= 0 THEN
        RETURN jsonb_build_object('erro', 'Quantidade de creditos deve ser maior que zero.');
    END IF;

    SELECT credits_balance
      INTO v_balance
      FROM users
     WHERE user_id = p_user_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('erro', 'Usuario nao encontrado.');
    END IF;

    v_balance := COALESCE(v_balance, 0);
    IF v_balance < p_amount THEN
        RETURN jsonb_build_object(
            'erro', 'Saldo insuficiente.',
            'saldo_atual', v_balance,
            'necessario', p_amount
        );
    END IF;

    v_new_balance := v_balance - p_amount;

    UPDATE users
       SET credits_balance = v_new_balance,
           updated_at = NOW()
     WHERE user_id = p_user_id;

    INSERT INTO credit_transactions (
        user_id,
        type,
        amount,
        reason,
        related_reading_id,
        metadata
    )
    VALUES (
        p_user_id,
        'consume',
        p_amount,
        p_reason,
        p_related_reading_id,
        jsonb_build_object('old_balance', v_balance, 'new_balance', v_new_balance)
    )
    RETURNING transaction_id INTO v_transaction_id;

    RETURN jsonb_build_object(
        'ok', true,
        'transaction_id', v_transaction_id,
        'saldo_anterior', v_balance,
        'saldo_atual', v_new_balance
    );
END;
$$;

CREATE OR REPLACE FUNCTION refund_user_credits(
    p_user_id UUID,
    p_amount INTEGER,
    p_reason TEXT DEFAULT 'Estorno de leitura',
    p_related_reading_id UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_balance INTEGER;
    v_new_balance INTEGER;
    v_transaction_id UUID;
BEGIN
    IF p_amount <= 0 THEN
        RETURN jsonb_build_object('erro', 'Quantidade de creditos deve ser maior que zero.');
    END IF;

    SELECT credits_balance
      INTO v_balance
      FROM users
     WHERE user_id = p_user_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('erro', 'Usuario nao encontrado.');
    END IF;

    v_balance := COALESCE(v_balance, 0);
    v_new_balance := v_balance + p_amount;

    UPDATE users
       SET credits_balance = v_new_balance,
           updated_at = NOW()
     WHERE user_id = p_user_id;

    INSERT INTO credit_transactions (
        user_id,
        type,
        amount,
        reason,
        related_reading_id,
        metadata
    )
    VALUES (
        p_user_id,
        'refund',
        p_amount,
        p_reason,
        p_related_reading_id,
        jsonb_build_object('old_balance', v_balance, 'new_balance', v_new_balance)
    )
    RETURNING transaction_id INTO v_transaction_id;

    RETURN jsonb_build_object(
        'ok', true,
        'transaction_id', v_transaction_id,
        'saldo_anterior', v_balance,
        'saldo_atual', v_new_balance
    );
END;
$$;

CREATE OR REPLACE FUNCTION admin_adjust_user_credits(
    p_user_id UUID,
    p_amount INTEGER,
    p_type TEXT,
    p_reason TEXT,
    p_admin_id UUID DEFAULT NULL,
    p_related_payment_id UUID DEFAULT NULL,
    p_related_reading_id UUID DEFAULT NULL,
    p_expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_balance INTEGER;
    v_new_balance INTEGER;
    v_delta INTEGER;
    v_transaction_id UUID;
BEGIN
    IF p_type NOT IN ('add', 'remove', 'consume', 'refund') THEN
        RETURN jsonb_build_object('erro', 'Tipo de transacao de credito invalido.');
    END IF;

    IF p_amount <= 0 THEN
        RETURN jsonb_build_object('erro', 'Quantidade de creditos deve ser maior que zero.');
    END IF;

    SELECT credits_balance
      INTO v_balance
      FROM users
     WHERE user_id = p_user_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('erro', 'Usuario nao encontrado.');
    END IF;

    v_balance := COALESCE(v_balance, 0);
    v_delta := CASE WHEN p_type IN ('add', 'refund') THEN p_amount ELSE -p_amount END;
    v_new_balance := v_balance + v_delta;

    IF v_new_balance < 0 THEN
        RETURN jsonb_build_object(
            'erro', 'Saldo insuficiente para remover creditos.',
            'saldo_atual', v_balance,
            'amount', p_amount
        );
    END IF;

    UPDATE users
       SET credits_balance = v_new_balance,
           updated_at = NOW()
     WHERE user_id = p_user_id;

    INSERT INTO credit_transactions (
        user_id,
        type,
        amount,
        reason,
        related_payment_id,
        related_reading_id,
        created_by_admin_id,
        expires_at,
        metadata
    )
    VALUES (
        p_user_id,
        p_type,
        p_amount,
        p_reason,
        p_related_payment_id,
        p_related_reading_id,
        p_admin_id,
        p_expires_at,
        jsonb_build_object('old_balance', v_balance, 'new_balance', v_new_balance)
    )
    RETURNING transaction_id INTO v_transaction_id;

    RETURN jsonb_build_object(
        'ok', true,
        'transaction_id', v_transaction_id,
        'saldo_anterior', v_balance,
        'saldo_atual', v_new_balance
    );
END;
$$;
