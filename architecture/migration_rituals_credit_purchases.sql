-- Compra de rituais por creditos, sem checkout em reais.
-- `rituals.preco` permanece por compatibilidade, mas passa a representar custo em creditos.

ALTER TABLE ritual_purchases ADD COLUMN IF NOT EXISTS credits_spent INTEGER DEFAULT 0;
ALTER TABLE ritual_purchases ADD COLUMN IF NOT EXISTS coupon_code TEXT;

CREATE INDEX IF NOT EXISTS idx_ritual_purchases_coupon_code
  ON ritual_purchases(coupon_code);
