-- =====================================================
-- Madame do Luar - schema consolidado
-- =====================================================
-- Objetivo:
-- - Criar uma base nova coerente com o backend atual.
-- - Ser seguro para reexecutar no Supabase SQL Editor.
-- - Consolidar schema inicial, migration de autenticacao,
--   admin operacional, PIX, automacoes e logs.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- Usuarios, autenticacao e permissoes
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome TEXT,
    email TEXT UNIQUE,
    whatsapp TEXT UNIQUE,
    avatar_url TEXT,
    whatsapp_opt_in BOOLEAN DEFAULT FALSE,
    whatsapp_opt_in_at TIMESTAMP WITH TIME ZONE,
    whatsapp_opt_out_at TIMESTAMP WITH TIME ZONE,
    email_opt_in BOOLEAN DEFAULT FALSE,
    email_opt_in_at TIMESTAMP WITH TIME ZONE,
    email_opt_out_at TIMESTAMP WITH TIME ZONE,
    terms_accepted_at TIMESTAMP WITH TIME ZONE,
    privacy_accepted_at TIMESTAMP WITH TIME ZONE,
    ai_notice_accepted_at TIMESTAMP WITH TIME ZONE,
    senha_hash TEXT,
    role TEXT DEFAULT 'cliente',
    status TEXT DEFAULT 'ativo',
    plan_id UUID,
    credits_balance INTEGER DEFAULT 0,
    primeira_tiragem_gratis BOOLEAN DEFAULT true,
    assinante BOOLEAN DEFAULT false,
    origem TEXT,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS senha_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_in BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_in_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_out_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_in BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_in_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_opt_out_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_notice_accepted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'cliente';
ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ativo';
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_id UUID;
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits_balance INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('cliente', 'admin', 'super_admin'));

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_check;
ALTER TABLE users ADD CONSTRAINT users_status_check
  CHECK (status IN ('ativo', 'bloqueado', 'inativo'));

CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(criado_em);
CREATE INDEX IF NOT EXISTS idx_users_last_login_at ON users(last_login_at);

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

-- O modelo administrativo oficial e por roles em users.role.
-- Esta tabela opcional registra concessoes administrativas/auditoria de acesso.
CREATE TABLE IF NOT EXISTS admin_users (
    admin_user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'super_admin')),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    granted_by_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    granted_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_users_status ON admin_users(status);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);

-- =====================================================
-- Produtos, planos, creditos e cupons
-- =====================================================

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

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_plan_id_fkey;
ALTER TABLE users ADD CONSTRAINT users_plan_id_fkey
  FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);

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

CREATE INDEX IF NOT EXISTS idx_credit_packages_status ON credit_packages(status);

CREATE TABLE IF NOT EXISTS coupons (
    coupon_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    discount_type TEXT NOT NULL CHECK (discount_type IN ('percent', 'fixed')),
    discount_value NUMERIC(10, 2) NOT NULL CHECK (discount_value >= 0),
    applies_to TEXT DEFAULT 'all' CHECK (applies_to IN ('all', 'package', 'plan', 'ritual', 'reading')),
    event_type TEXT,
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
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS applies_to TEXT DEFAULT 'all';
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS event_type TEXT;

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

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_created_at ON credit_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_related_payment_id ON credit_transactions(related_payment_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_related_reading_id ON credit_transactions(related_reading_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_expires_at ON credit_transactions(expires_at);

-- =====================================================
-- Conteudo, leituras e IA
-- =====================================================

CREATE TABLE IF NOT EXISTS cards (
    card_id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    naipe TEXT NOT NULL,
    numero INTEGER NOT NULL,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    question_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    pergunta TEXT NOT NULL,
    tema TEXT,
    emocao TEXT,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questions_user_id ON questions(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_criado_em ON questions(criado_em);
CREATE INDEX IF NOT EXISTS idx_questions_tema ON questions(tema);

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
CREATE INDEX IF NOT EXISTS idx_ai_prompts_status ON ai_prompts(status);

CREATE TABLE IF NOT EXISTS readings (
    reading_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id UUID REFERENCES questions(question_id) ON DELETE CASCADE,
    carta_passado TEXT NOT NULL,
    inverted_passado BOOLEAN DEFAULT false,
    carta_presente TEXT NOT NULL,
    inverted_presente BOOLEAN DEFAULT false,
    carta_futuro TEXT NOT NULL,
    inverted_futuro BOOLEAN DEFAULT false,
    interpretacao TEXT NOT NULL,
    conselho TEXT,
    mini_ritual TEXT,
    nivel_energia TEXT,
    prompt_id UUID REFERENCES ai_prompts(prompt_id) ON DELETE SET NULL,
    model TEXT,
    tokens_used INTEGER DEFAULT 0,
    estimated_cost NUMERIC(12, 6) DEFAULT 0,
    status TEXT DEFAULT 'concluida',
    error_message TEXT,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE readings ADD COLUMN IF NOT EXISTS prompt_id UUID REFERENCES ai_prompts(prompt_id) ON DELETE SET NULL;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS estimated_cost NUMERIC(12, 6) DEFAULT 0;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'concluida';
ALTER TABLE readings ADD COLUMN IF NOT EXISTS error_message TEXT;

ALTER TABLE readings DROP CONSTRAINT IF EXISTS readings_status_check;
ALTER TABLE readings ADD CONSTRAINT readings_status_check
  CHECK (status IN ('pendente', 'concluida', 'erro'));

CREATE INDEX IF NOT EXISTS idx_readings_question_id ON readings(question_id);
CREATE INDEX IF NOT EXISTS idx_readings_status ON readings(status);
CREATE INDEX IF NOT EXISTS idx_readings_criado_em ON readings(criado_em);
CREATE INDEX IF NOT EXISTS idx_readings_prompt_id ON readings(prompt_id);

CREATE TABLE IF NOT EXISTS daily_cards (
    daily_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    carta TEXT NOT NULL,
    inverted BOOLEAN DEFAULT false,
    mensagem TEXT NOT NULL,
    nivel_energia TEXT,
    criado_em DATE DEFAULT CURRENT_DATE
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_daily_card_per_user ON daily_cards(user_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_daily_cards_user_id ON daily_cards(user_id);

-- =====================================================
-- Pagamentos, assinaturas e rituais
-- =====================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    sub_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    status TEXT,
    plano TEXT,
    valor NUMERIC(10, 2),
    inicio DATE,
    renovacao DATE,
    gateway_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS valor NUMERIC(10, 2);
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS gateway_id TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_status_check;
ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_status_check
  CHECK (status IN ('ativo', 'expirado', 'cancelado', 'past_due', 'trialing'));

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_renovacao ON subscriptions(renovacao);
CREATE INDEX IF NOT EXISTS idx_subscriptions_gateway_id ON subscriptions(gateway_id);

CREATE TABLE IF NOT EXISTS payments (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    plan_id UUID REFERENCES plans(plan_id) ON DELETE SET NULL,
    package_id UUID REFERENCES credit_packages(package_id) ON DELETE SET NULL,
    product_type TEXT,
    product_name TEXT,
    status TEXT DEFAULT 'pending',
    valor NUMERIC(10, 2),
    amount NUMERIC(10, 2),
    original_amount NUMERIC(10, 2),
    discount_amount NUMERIC(10, 2) DEFAULT 0,
    coupon_code TEXT,
    tipo TEXT,
    method TEXT DEFAULT 'PIX',
    gateway TEXT,
    gateway_ref TEXT,
    transaction_id TEXT,
    qr_code_url TEXT,
    pix_copy_paste TEXT,
    checkout_url TEXT,
    webhook_payload JSONB,
    gateway_payload JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    credits_to_release INTEGER DEFAULT 0,
    credits_released BOOLEAN DEFAULT false,
    approved_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    abandoned_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS plan_id UUID REFERENCES plans(plan_id) ON DELETE SET NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS package_id UUID REFERENCES credit_packages(package_id) ON DELETE SET NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS product_type TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS product_name TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS original_amount NUMERIC(10, 2);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10, 2) DEFAULT 0;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS coupon_code TEXT;
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

ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_tipo_check;
ALTER TABLE payments ADD CONSTRAINT payments_tipo_check
  CHECK (tipo IS NULL OR tipo IN ('leitura', 'assinatura', 'ritual'));

CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_transaction_id_unique
  ON payments(transaction_id)
  WHERE transaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_expires_at ON payments(expires_at);
CREATE INDEX IF NOT EXISTS idx_payments_gateway_ref ON payments(gateway_ref);

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
CREATE INDEX IF NOT EXISTS idx_payment_webhook_events_processed ON payment_webhook_events(processed);

CREATE TABLE IF NOT EXISTS rituals (
    ritual_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome TEXT NOT NULL,
    tema TEXT,
    descricao TEXT,
    preco NUMERIC(10, 2) DEFAULT 0,
    pdf_url TEXT,
    audio_url TEXT,
    ativo BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rituals_ativo ON rituals(ativo);
CREATE INDEX IF NOT EXISTS idx_rituals_tema ON rituals(tema);

CREATE TABLE IF NOT EXISTS ritual_purchases (
    purchase_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    ritual_id UUID REFERENCES rituals(ritual_id) ON DELETE CASCADE,
    payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL,
    status TEXT CHECK (status IN ('pending', 'approved', 'failed', 'cancelled', 'refunded')),
    data TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE ritual_purchases ADD COLUMN IF NOT EXISTS payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL;
ALTER TABLE ritual_purchases ADD COLUMN IF NOT EXISTS credits_spent INTEGER DEFAULT 0;
ALTER TABLE ritual_purchases ADD COLUMN IF NOT EXISTS coupon_code TEXT;
ALTER TABLE ritual_purchases ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_ritual_purchases_user_id ON ritual_purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_ritual_purchases_status ON ritual_purchases(status);

-- =====================================================
-- Automacoes, eventos e notificacoes
-- =====================================================

CREATE TABLE IF NOT EXISTS message_events (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    question_id UUID REFERENCES questions(question_id) ON DELETE SET NULL,
    payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL,
    tipo TEXT,
    canal TEXT CHECK (canal IN ('whatsapp', 'email')),
    subject TEXT,
    mensagem TEXT,
    variables JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    agendado_para TIMESTAMP WITH TIME ZONE,
    enviado_em TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE message_events ADD COLUMN IF NOT EXISTS payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS variables JSONB DEFAULT '{}'::jsonb;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS max_attempts INTEGER DEFAULT 3;
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE message_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE message_events DROP CONSTRAINT IF EXISTS message_events_tipo_check;
ALTER TABLE message_events ADD CONSTRAINT message_events_tipo_check
  CHECK (tipo IN ('24h', '3d', '7d', '30d', 'marketing', 'welcome', 'carrinho_abandonado', 'pos_venda', 'recompra', 'reativacao'));

ALTER TABLE message_events DROP CONSTRAINT IF EXISTS message_events_status_check;
ALTER TABLE message_events ADD CONSTRAINT message_events_status_check
  CHECK (status IN ('pending', 'processing', 'sent', 'failed', 'skipped', 'cancelled'));

CREATE INDEX IF NOT EXISTS idx_message_events_status_due ON message_events(status, agendado_para);
CREATE INDEX IF NOT EXISTS idx_message_events_user_tipo ON message_events(user_id, tipo);
CREATE INDEX IF NOT EXISTS idx_message_events_payment_id ON message_events(payment_id);

CREATE TABLE IF NOT EXISTS automation_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    audience_filter JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_automation_rules_event_type ON automation_rules(event_type);
CREATE INDEX IF NOT EXISTS idx_automation_rules_status ON automation_rules(status);

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

CREATE INDEX IF NOT EXISTS idx_automation_steps_rule_order ON automation_steps(rule_id, step_order);
CREATE INDEX IF NOT EXISTS idx_automation_steps_status ON automation_steps(status);

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

CREATE INDEX IF NOT EXISTS idx_notification_logs_user_id ON notification_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_status ON notification_logs(status);
CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at ON notification_logs(created_at);

-- =====================================================
-- CRM e segmentacao
-- =====================================================

CREATE TABLE IF NOT EXISTS customer_tags (
    tag_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_customer_tags (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    tag_id UUID REFERENCES customer_tags(tag_id) ON DELETE CASCADE,
    assigned_by_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, tag_id)
);

CREATE TABLE IF NOT EXISTS customer_segments (
    segment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    rules JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_customer_segments (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    segment_id UUID REFERENCES customer_segments(segment_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, segment_id)
);

CREATE INDEX IF NOT EXISTS idx_customer_tags_status ON customer_tags(status);
CREATE INDEX IF NOT EXISTS idx_customer_segments_status ON customer_segments(status);

CREATE TABLE IF NOT EXISTS admin_customer_notes (
    note_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    note TEXT NOT NULL,
    visibility TEXT DEFAULT 'internal' CHECK (visibility IN ('internal', 'support', 'sales', 'marketing')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_customer_notes_user_id ON admin_customer_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_customer_notes_created_at ON admin_customer_notes(created_at);

CREATE TABLE IF NOT EXISTS segment_automation_triggers (
    trigger_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    segment_id UUID REFERENCES customer_segments(segment_id) ON DELETE CASCADE,
    rule_id UUID REFERENCES automation_rules(rule_id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    event_type TEXT DEFAULT 'segment_entry',
    channel TEXT CHECK (channel IN ('email', 'whatsapp')),
    template TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_segment_automation_triggers_segment_id ON segment_automation_triggers(segment_id);
CREATE INDEX IF NOT EXISTS idx_segment_automation_triggers_status ON segment_automation_triggers(status);

-- =====================================================
-- Logs, auditoria, monitoramento e configuracoes
-- =====================================================

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

CREATE TABLE IF NOT EXISTS analytics_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_name TEXT NOT NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    session_id TEXT,
    anonymous_id TEXT,
    page_url TEXT,
    referrer TEXT,
    source TEXT DEFAULT 'frontend',
    entity_type TEXT,
    entity_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_name_created_at ON analytics_events(event_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_user_created_at ON analytics_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_session_created_at ON analytics_events(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_entity ON analytics_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_metadata_gin ON analytics_events USING GIN (metadata);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    before_data JSONB DEFAULT '{}'::jsonb,
    after_data JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    severity TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_admin_id ON audit_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

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

-- =====================================================
-- Funcoes atomicas de creditos
-- =====================================================

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

    SELECT credits_balance INTO v_balance
      FROM users
     WHERE user_id = p_user_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('erro', 'Usuario nao encontrado.');
    END IF;

    v_balance := COALESCE(v_balance, 0);
    IF v_balance < p_amount THEN
        RETURN jsonb_build_object('erro', 'Saldo insuficiente.', 'saldo_atual', v_balance, 'necessario', p_amount);
    END IF;

    v_new_balance := v_balance - p_amount;

    UPDATE users
       SET credits_balance = v_new_balance,
           updated_at = NOW()
     WHERE user_id = p_user_id;

    INSERT INTO credit_transactions (user_id, type, amount, reason, related_reading_id, metadata)
    VALUES (p_user_id, 'consume', p_amount, p_reason, p_related_reading_id, jsonb_build_object('old_balance', v_balance, 'new_balance', v_new_balance))
    RETURNING transaction_id INTO v_transaction_id;

    RETURN jsonb_build_object('ok', true, 'transaction_id', v_transaction_id, 'saldo_anterior', v_balance, 'saldo_atual', v_new_balance);
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

    SELECT credits_balance INTO v_balance
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

    INSERT INTO credit_transactions (user_id, type, amount, reason, related_reading_id, metadata)
    VALUES (p_user_id, 'refund', p_amount, p_reason, p_related_reading_id, jsonb_build_object('old_balance', v_balance, 'new_balance', v_new_balance))
    RETURNING transaction_id INTO v_transaction_id;

    RETURN jsonb_build_object('ok', true, 'transaction_id', v_transaction_id, 'saldo_anterior', v_balance, 'saldo_atual', v_new_balance);
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

    SELECT credits_balance INTO v_balance
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
        RETURN jsonb_build_object('erro', 'Saldo insuficiente para remover creditos.', 'saldo_atual', v_balance, 'amount', p_amount);
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

    RETURN jsonb_build_object('ok', true, 'transaction_id', v_transaction_id, 'saldo_anterior', v_balance, 'saldo_atual', v_new_balance);
END;
$$;
