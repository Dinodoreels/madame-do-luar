-- =====================================================
-- Migration: adicionar autenticação na tabela users
-- Execute no Supabase: https://app.supabase.com
-- Menu: SQL Editor → New Query → colar e rodar
-- =====================================================

-- Adiciona coluna de senha hasheada
ALTER TABLE users ADD COLUMN IF NOT EXISTS senha_hash TEXT;

-- Adiciona índice no email para buscas rápidas
CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users (email);

-- Confirma estrutura
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users'
ORDER BY ordinal_position;
