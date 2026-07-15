# Matriz de Variaveis por Ambiente

Objetivo: impedir que configuracoes locais, mocks, URLs temporarias ou secrets compartilhados vazem para homologacao e producao.

## Regras Globais

- Cada ambiente usa um arquivo/grupo de secrets separado: local, homologation e production.
- Nunca copiar tokens de local para homologacao/producao.
- Nunca commitar valores reais de secrets.
- Validar antes de deploy com:

```powershell
python -B tools\validate_environment.py --env-file .env.production --environment production
python -B tools\predeploy_check.py --env-file .env.production
```

## Local

Arquivo base: `.env.example`

Obrigatorias:

- `APP_ENV=local`
- `ENVIRONMENT_NAME=local`
- `APP_BASE_URL=http://localhost:8000`
- `APP_CORS_ORIGINS` com `localhost`, `127.0.0.1` ou `null`
- `ADMIN_DIRECT_ACCESS=false`
- `JWT_SECRET` local, sem uso em outros ambientes
- `PIX_GATEWAY`
- `ALLOW_MOCK_PAYMENTS` explicitamente definido
- `ALLOW_SIMULATED_NOTIFICATIONS` explicitamente definido
- `BACKUP_DIR`

Permitido apenas no local:

- URL `localhost`
- origem `null` para abrir HTML local
- notificacoes simuladas
- credenciais vazias para integrações ainda nao testadas

## Homologacao

Arquivo base: `.env.homologation.example`

Obrigatorias:

- `APP_ENV=staging`
- `ENVIRONMENT_NAME=homologation`
- `APP_BASE_URL=https://homolog.madamedoluar.com.br` ou outro dominio publico HTTPS de homologacao
- `APP_CORS_ORIGINS` apenas com HTTPS publico de homologacao
- `ADMIN_DIRECT_ACCESS=false`
- `ALLOW_MOCK_PAYMENTS=false`
- `ALLOW_SIMULATED_NOTIFICATIONS=false`
- `MERCADO_PAGO_ENV=sandbox`
- `MERCADO_PAGO_NOTIFICATION_URL=https://homolog.../api/webhook/mercado-pago`
- `JWT_SECRET`, `GEMINI_API_KEY`, Supabase, Mercado Pago sandbox, WhatsApp e SMTP separados da producao

Proibido em homologacao:

- `localhost`, `127.0.0.1`, `null` ou `*` em URLs publicas/CORS
- secrets de producao
- mocks de pagamento
- acesso admin direto

## Producao

Arquivo base: `.env.production.example`

Obrigatorias:

- `APP_ENV=production`
- `ENVIRONMENT_NAME=production`
- `APP_BASE_URL=https://madamedoluar.com.br`
- `APP_CORS_ORIGINS=https://madamedoluar.com.br,https://www.madamedoluar.com.br`
- `ADMIN_DIRECT_ACCESS=false`
- `ALLOW_MOCK_PAYMENTS=false`
- `ALLOW_SIMULATED_NOTIFICATIONS=false`
- `MERCADO_PAGO_ENV=production`
- `MERCADO_PAGO_NOTIFICATION_URL=https://madamedoluar.com.br/api/webhook/mercado-pago`
- `JWT_SECRET` com pelo menos 32 caracteres
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `MERCADO_PAGO_PUBLIC_KEY`
- `MERCADO_PAGO_ACCESS_TOKEN`
- `MERCADO_PAGO_WEBHOOK_SECRET`
- `WHATSAPP_API_URL`
- `WHATSAPP_API_TOKEN`
- `SMTP_USER`
- `SMTP_PASS`

Proibido em producao:

- `ADMIN_DIRECT_ACCESS=true`
- `ALLOW_MOCK_PAYMENTS=true`
- `ALLOW_SIMULATED_NOTIFICATIONS=true`
- URLs `localhost`, `127.0.0.1`, `null`, `*`, `onrender.com` ou dominio temporario como URL principal
- webhook Mercado Pago/PIX fora do dominio publico final
- secrets contendo marcadores de local, staging, sandbox ou teste

## Gates de Deploy

Pre-deploy real:

```powershell
python -B tools\validate_environment.py --env-file .env.production --environment production
python -B tools\predeploy_check.py --env-file .env.production
```

Pre-deploy com template:

```powershell
python -B tools\validate_environment.py --env-file .env.production.example --environment production --allow-placeholders
python -B tools\predeploy_check.py --env-file .env.production.example --allow-placeholders
```
