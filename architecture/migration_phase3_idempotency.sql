-- Migration: Fase 3 - idempotencia, pagamentos e creditos atomicos
-- Objetivo: impedir dupla liberacao de credito/entitlement em webhooks, compras e reprocessamentos.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed')),
    request_hash TEXT,
    response_payload JSONB DEFAULT '{}'::jsonb,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_scope_status ON idempotency_keys(scope, status);
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_locked_until ON idempotency_keys(locked_until);

ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS related_payment_id UUID REFERENCES payments(payment_id) ON DELETE SET NULL;
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS related_reading_id UUID;
ALTER TABLE payment_webhook_events ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_webhook_events_gateway_type_tx_unique
  ON payment_webhook_events(gateway, event_type, transaction_id)
  WHERE transaction_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_transactions_idempotency_key_unique
  ON credit_transactions(idempotency_key)
  WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_transactions_payment_add_unique
  ON credit_transactions(related_payment_id)
  WHERE related_payment_id IS NOT NULL AND type = 'add';

CREATE UNIQUE INDEX IF NOT EXISTS idx_ritual_purchases_user_ritual_active_unique
  ON ritual_purchases(user_id, ritual_id)
  WHERE status IN ('pending', 'approved');

CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_user_active_unique
  ON subscriptions(user_id)
  WHERE status = 'ativo';

CREATE INDEX IF NOT EXISTS idx_payments_user_status_created_at ON payments(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_gateway_status_created_at ON payments(gateway, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_created_at ON credit_transactions(user_id, created_at DESC);

CREATE OR REPLACE FUNCTION approve_payment_once(
    p_payment_id UUID,
    p_webhook_payload JSONB DEFAULT '{}'::jsonb,
    p_admin_id UUID DEFAULT NULL,
    p_manual BOOLEAN DEFAULT FALSE,
    p_reason TEXT DEFAULT 'Pagamento aprovado'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_payment payments%ROWTYPE;
    v_balance INTEGER;
    v_new_balance INTEGER;
    v_transaction_id UUID;
    v_idempotency_key TEXT;
BEGIN
    SELECT *
      INTO v_payment
      FROM payments
     WHERE payment_id = p_payment_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('erro', 'Pagamento nao encontrado.');
    END IF;

    IF v_payment.status = 'approved' AND COALESCE(v_payment.credits_released, false) = true THEN
        RETURN jsonb_build_object(
            'ok', true,
            'ja_liberado', true,
            'payment_id', v_payment.payment_id,
            'credits_to_release', COALESCE(v_payment.credits_to_release, 0)
        );
    END IF;

    UPDATE payments
       SET status = 'approved',
           approved_at = COALESCE(approved_at, NOW()),
           webhook_payload = COALESCE(p_webhook_payload, webhook_payload),
           updated_at = NOW()
     WHERE payment_id = p_payment_id;

    IF COALESCE(v_payment.credits_to_release, 0) <= 0 THEN
        UPDATE payments
           SET credits_released = true,
               updated_at = NOW()
         WHERE payment_id = p_payment_id;

        RETURN jsonb_build_object(
            'ok', true,
            'sem_creditos', true,
            'payment_id', p_payment_id
        );
    END IF;

    v_idempotency_key := 'payment-credit-release:' || p_payment_id::TEXT;

    SELECT credits_balance
      INTO v_balance
      FROM users
     WHERE user_id = v_payment.user_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('erro', 'Usuario do pagamento nao encontrado.');
    END IF;

    v_balance := COALESCE(v_balance, 0);
    v_new_balance := v_balance + COALESCE(v_payment.credits_to_release, 0);

    INSERT INTO credit_transactions (
        user_id,
        type,
        amount,
        reason,
        related_payment_id,
        created_by_admin_id,
        idempotency_key,
        metadata
    )
    VALUES (
        v_payment.user_id,
        'add',
        COALESCE(v_payment.credits_to_release, 0),
        p_reason,
        p_payment_id,
        p_admin_id,
        v_idempotency_key,
        jsonb_build_object(
            'old_balance', v_balance,
            'new_balance', v_new_balance,
            'manual', p_manual
        )
    )
    ON CONFLICT DO NOTHING
    RETURNING transaction_id INTO v_transaction_id;

    IF v_transaction_id IS NULL THEN
        UPDATE payments
           SET credits_released = true,
               updated_at = NOW()
         WHERE payment_id = p_payment_id;

        RETURN jsonb_build_object(
            'ok', true,
            'ja_liberado', true,
            'payment_id', p_payment_id
        );
    END IF;

    UPDATE users
       SET credits_balance = v_new_balance,
           updated_at = NOW()
     WHERE user_id = v_payment.user_id;

    UPDATE payments
       SET credits_released = true,
           updated_at = NOW()
     WHERE payment_id = p_payment_id;

    RETURN jsonb_build_object(
        'ok', true,
        'transaction_id', v_transaction_id,
        'saldo_anterior', v_balance,
        'saldo_atual', v_new_balance,
        'payment_id', p_payment_id
    );
END;
$$;

CREATE OR REPLACE FUNCTION purchase_ritual_with_credits(
    p_user_id UUID,
    p_ritual_id UUID,
    p_amount INTEGER,
    p_reason TEXT DEFAULT 'Compra de ritual',
    p_coupon_code TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_existing ritual_purchases%ROWTYPE;
    v_balance INTEGER;
    v_new_balance INTEGER;
    v_transaction_id UUID;
    v_purchase_id UUID;
    v_idempotency_key TEXT;
BEGIN
    SELECT *
      INTO v_existing
      FROM ritual_purchases
     WHERE user_id = p_user_id
       AND ritual_id = p_ritual_id
       AND status IN ('pending', 'approved')
     LIMIT 1;

    IF FOUND THEN
        RETURN jsonb_build_object(
            'ok', true,
            'ja_comprado', true,
            'purchase_id', v_existing.purchase_id,
            'status', v_existing.status
        );
    END IF;

    IF p_amount <= 0 THEN
        INSERT INTO ritual_purchases (user_id, ritual_id, status, credits_spent, coupon_code)
        VALUES (p_user_id, p_ritual_id, 'approved', 0, p_coupon_code)
        ON CONFLICT DO NOTHING
        RETURNING purchase_id INTO v_purchase_id;

        RETURN jsonb_build_object('ok', true, 'purchase_id', v_purchase_id, 'status', 'approved', 'sem_creditos', true);
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
        RETURN jsonb_build_object('erro', 'Saldo insuficiente.', 'saldo_atual', v_balance, 'necessario', p_amount);
    END IF;

    v_new_balance := v_balance - p_amount;
    v_idempotency_key := 'ritual-purchase:' || p_user_id::TEXT || ':' || p_ritual_id::TEXT;

    INSERT INTO ritual_purchases (user_id, ritual_id, status, credits_spent, coupon_code)
    VALUES (p_user_id, p_ritual_id, 'approved', p_amount, p_coupon_code)
    ON CONFLICT DO NOTHING
    RETURNING purchase_id INTO v_purchase_id;

    IF v_purchase_id IS NULL THEN
        SELECT purchase_id, status
          INTO v_purchase_id, v_existing.status
          FROM ritual_purchases
         WHERE user_id = p_user_id
           AND ritual_id = p_ritual_id
           AND status IN ('pending', 'approved')
         LIMIT 1;

        RETURN jsonb_build_object('ok', true, 'ja_comprado', true, 'purchase_id', v_purchase_id, 'status', v_existing.status);
    END IF;

    INSERT INTO credit_transactions (user_id, type, amount, reason, related_reading_id, idempotency_key, metadata)
    VALUES (
        p_user_id,
        'consume',
        p_amount,
        p_reason,
        NULL,
        v_idempotency_key,
        jsonb_build_object('old_balance', v_balance, 'new_balance', v_new_balance, 'ritual_id', p_ritual_id)
    )
    RETURNING transaction_id INTO v_transaction_id;

    UPDATE users
       SET credits_balance = v_new_balance,
           updated_at = NOW()
     WHERE user_id = p_user_id;

    RETURN jsonb_build_object(
        'ok', true,
        'purchase_id', v_purchase_id,
        'transaction_id', v_transaction_id,
        'status', 'approved',
        'saldo_anterior', v_balance,
        'saldo_atual', v_new_balance
    );
END;
$$;

CREATE OR REPLACE FUNCTION cleanup_operational_logs(
    p_system_log_days INTEGER DEFAULT 180,
    p_notification_log_days INTEGER DEFAULT 180,
    p_webhook_event_days INTEGER DEFAULT 365
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_system_deleted INTEGER := 0;
    v_notification_deleted INTEGER := 0;
    v_webhook_deleted INTEGER := 0;
BEGIN
    DELETE FROM system_logs
     WHERE created_at < NOW() - make_interval(days => p_system_log_days);
    GET DIAGNOSTICS v_system_deleted = ROW_COUNT;

    DELETE FROM notification_logs
     WHERE created_at < NOW() - make_interval(days => p_notification_log_days);
    GET DIAGNOSTICS v_notification_deleted = ROW_COUNT;

    DELETE FROM payment_webhook_events
     WHERE created_at < NOW() - make_interval(days => p_webhook_event_days)
       AND processed = true;
    GET DIAGNOSTICS v_webhook_deleted = ROW_COUNT;

    RETURN jsonb_build_object(
        'ok', true,
        'system_logs_deleted', v_system_deleted,
        'notification_logs_deleted', v_notification_deleted,
        'webhook_events_deleted', v_webhook_deleted
    );
END;
$$;
