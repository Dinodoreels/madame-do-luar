-- Madame do Luar - avatar do usuario
-- Aplica suporte para imagem de perfil no cadastro, login/header e perfil.

ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
