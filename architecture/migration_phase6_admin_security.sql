-- Fase 6 - Painel administrativo profissional
-- Aplicar no Supabase quando houver acesso SQL.

ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'cliente';
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('cliente', 'admin', 'super_admin', 'financeiro', 'suporte', 'marketing', 'operacoes'));

ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_secret TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_admin_reauth_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_two_factor_enabled ON users(two_factor_enabled);

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS severity TEXT DEFAULT 'info';
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_agent TEXT;

CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs(severity);

-- Perfis operacionais previstos:
-- super_admin: acesso total.
-- admin: operacao geral sem aprovacao financeira sensivel.
-- financeiro: pagamentos, planos, pacotes, cupons e aprovacao manual com reautenticacao.
-- suporte: usuarios, CRM e logs.
-- marketing: CRM, campanhas e exportacoes.
-- operacoes: jobs, alertas, status e auditoria operacional.
