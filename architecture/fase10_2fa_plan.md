# Planejamento 2FA - Madame do Luar

## Escopo recomendado

1. Admin e super admin: 2FA obrigatorio.
2. Cliente: 2FA opcional.
3. Metodo inicial: TOTP em aplicativo autenticador.
4. Recuperacao: codigos de backup de uso unico.

## Modelo de dados

- `user_security_settings`
  - `user_id`
  - `totp_enabled`
  - `totp_secret_encrypted`
  - `recovery_codes_hash`
  - `last_2fa_at`
  - `created_at`
  - `updated_at`

## Fluxo

1. Usuario solicita ativacao.
2. Backend gera segredo TOTP e QR code.
3. Usuario confirma com codigo valido.
4. Backend grava segredo criptografado e gera codigos de recuperacao.
5. Login de usuario com 2FA exige senha + codigo TOTP antes de emitir JWT final.

## Cuidados

- Nunca armazenar segredo TOTP em texto puro.
- Rate limit especifico em tentativas de 2FA.
- Auditoria para ativacao, desativacao e falhas.
- Super admin nao pode desativar 2FA sem segundo fator ou procedimento manual registrado.
