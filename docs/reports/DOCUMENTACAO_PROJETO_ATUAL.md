# Documentacao Completa do Projeto - Madame do Luar

Atualizado em: 2026-05-21

## 1. Resumo executivo

O Madame do Luar e uma plataforma digital de leituras espirituais, tarot, carta do dia, rituais, creditos, pagamentos PIX, automacoes de relacionamento, CRM e painel administrativo.

O projeto ja passou da fase de MVP simples. Hoje existe uma base operacional em FastAPI com frontend estatico, Supabase, IA generativa, Mercado Pago, email SMTP, WhatsApp via Uazapi, automacoes, painel admin, LGPD, backup/restore e scripts de validacao.

Status real atual:

- Plataforma local funcional e bem documentada.
- Backend com grande numero de rotas implementadas.
- Painel admin existente e redesenhado com visual premium.
- Supabase, Gemini, email, pagamentos sandbox e scripts operacionais preparados.
- Go-live publico ainda nao deve ser considerado concluido.
- Venda publica depende de dominio final, HTTPS, webhook Mercado Pago final, secrets de producao e validacao ponta a ponta no ambiente publico.

## 2. Modelo de negocio

O produto suporta um modelo B2C com possibilidade de evoluir para B2B/B2B2C.

Oferta principal:

- Carta do dia gratuita ou limitada por regra diaria.
- Leituras espirituais com IA.
- Tiragem de 3 cartas.
- Leituras por tema: amor, dinheiro, carreira, energia, conselho espiritual.
- Rituais gratuitos e pagos.
- Pacotes de creditos.
- Assinatura mensal.
- Assinatura anual.

Objetivo comercial:

- Converter visitante em cliente.
- Monetizar por credito, assinatura e rituais pagos.
- Reter usuarios por carta diaria, automacoes, mensagens, CRM e ofertas contextuais.

## 3. Stack tecnica

Backend:

- Python
- FastAPI
- Uvicorn
- Requests
- bcrypt
- python-dotenv

Banco e dados:

- Supabase
- PostgreSQL
- SQL manual versionado em `architecture/schema.sql` e migrations auxiliares.

IA:

- Gemini configurado como modelo principal.
- OpenAI previsto como chave opcional.

Frontend:

- HTML, CSS e JavaScript estaticos.
- Landing/app publico em `frontend/index.html`, `frontend/app.js`, `frontend/style.css`.
- Painel admin em `frontend/admin.html`, `frontend/admin.js`, `frontend/admin.css`.
- Paginas legais em `frontend/privacidade.html`, `frontend/termos.html`, `frontend/ia.html`.
- Paginas de pagamento em `frontend/pagamento/sucesso/` e `frontend/pagamento/cancelado/`.

Infra/deploy:

- Render configurado em `render.yaml`.
- Web service FastAPI.
- Worker de automacoes.
- Cron de checagem diaria.
- Scripts de deploy, smoke test, backup e restore.

Dependencias registradas:

- `fastapi==0.111.0`
- `uvicorn==0.29.0`
- `supabase==2.4.5`
- `google-generativeai==0.5.2`
- `openai==1.23.2`
- `requests==2.31.0`
- `bcrypt==4.1.2`
- `psycopg2-binary==2.9.9`
- `python-dotenv==1.0.1`

## 4. Estrutura principal do projeto

Arquivos centrais:

- `api.py`: backend FastAPI principal, com auth, perfil, leituras, pagamentos, admin, CRM, LGPD, relatorios, status e webhooks.
- `tools/db_client.py`: cliente e helpers Supabase.
- `tools/flow_pagamento.py`: criacao de checkout/PIX e adaptadores de gateway.
- `tools/llm_client.py`: integracao com IA.
- `tools/notificacoes.py`: email e WhatsApp.
- `tools/automation_engine.py`: regras e agendamento de automacoes.
- `tools/automation_worker.py`: processamento em segundo plano.
- `architecture/schema.sql`: contrato consolidado de banco.
- `PLANO_IMPLANTACAO_MELHORIAS.md`: plano operacional principal.
- `PLANO_ACAO_MATURIDADE_PLATAFORMA.md`: plano de maturidade.
- `progress.md`: historico do desenvolvimento.
- `architecture/go_live_checklist.md`: checklist real de publicacao.

Pastas:

- `architecture/`: schemas, migrations, runbooks, contratos e checklists.
- `frontend/`: interface publica, painel admin e paginas legais.
- `prompts/`: prompts base para IA.
- `tools/`: scripts operacionais, validadores, workers e testes.
- `backups/`: manifests e backups REST/Supabase.
- `logs/`: logs locais.
- `imagems/`: assets visuais do produto.

## 5. Modulos implementados

### 5.1 Autenticacao e conta

Implementado:

- Cadastro.
- Login.
- Logout.
- JWT.
- Hash de senha.
- Recuperacao de senha.
- Reset de senha.
- Perfil do usuario.
- Atualizacao de dados.
- Historico de leituras.
- Historico de pagamentos.
- Saldo de creditos.
- Opt-in/opt-out de email.
- Opt-in/opt-out de WhatsApp.
- Aceite de termos, privacidade e aviso de IA.

Rotas principais:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /api/auth/me`
- `GET /api/me`
- `PATCH /api/me`
- `GET /api/me/credits`
- `GET /api/me/readings`
- `GET /api/me/payments`

### 5.2 Leituras e carta do dia

Implementado:

- Carta do dia autenticada.
- Leituras com IA.
- Tiragem de 3 cartas.
- Historico de leituras.
- Detalhe de leitura.
- Controle de custo por tipo de leitura.
- Primeira tiragem gratis.
- Consumo de credito.
- Estorno automatico se IA falhar.
- Registro de prompt, modelo, tokens, custo estimado e status.

Rotas principais:

- `POST /api/carta-do-dia`
- `POST /api/leitura`
- `POST /api/readings`
- `GET /api/readings/history`
- `GET /api/readings/{reading_id}`

### 5.3 Sistema de creditos

Modelo atual:

- Carta do dia: 0 credito, limitada por regra diaria.
- Tiragem de 3 cartas: 50 creditos.
- Leitura avulsa: 100 creditos por R$ 19,90.
- Plano mensal: 1.500 creditos por R$ 49,90.
- Plano anual: 18.250 creditos por R$ 397,00.
- Recargas: 100, 300, 500 e 1.500 creditos.

Implementado:

- Saldo por usuario.
- Transacoes de credito.
- Consumo atomico.
- Estorno atomico.
- Ajuste manual pelo admin.
- Relacao entre credito, leitura e pagamento.
- Expiracao opcional.
- Logs de alteracao.

Funcoes SQL previstas:

- `consume_user_credits`
- `refund_user_credits`
- `admin_adjust_user_credits`

### 5.4 Pagamentos

Implementado:

- Criacao de pagamento PIX/checkout.
- Mercado Pago como gateway principal.
- Stripe legado/opcional em partes do codigo.
- Webhooks PIX/Mercado Pago.
- Webhook idempotente.
- Liberacao automatica de creditos apos aprovacao.
- Aprovacao manual administrativa.
- Reprocessamento.
- Reenvio.
- Marcacao de abandonado.
- Paginas de sucesso e cancelamento.
- Consulta de status de pagamento.

Rotas principais:

- `POST /api/payments/pix/create`
- `GET /api/payments/{payment_id}`
- `GET /api/payments/{payment_id}/status`
- `POST /api/webhooks/pix`
- `POST /api/webhook/mercado-pago`
- `POST /api/webhook/stripe`
- `POST /api/checkout`
- `POST /api/subscription/cancel`

Ponto importante:

- O pagamento em sandbox ja foi validado.
- A venda publica ainda depende de webhook em URL final HTTPS e teste ponta a ponta no ambiente definitivo.

### 5.5 Planos, pacotes e cupons

Implementado:

- CRUD de planos.
- CRUD de pacotes de creditos.
- CRUD de cupons.
- Historico de mudanca de plano.
- Cupom percentual/valor e rastreio no pagamento.
- Contabilizacao de uso de cupom ao aprovar pagamento.

Rotas admin:

- `GET/POST/PATCH/DELETE /api/admin/plans`
- `GET/POST/PATCH/DELETE /api/admin/credit-packages`
- `GET/POST/PATCH/DELETE /api/admin/coupons`
- `PATCH /api/admin/users/{user_id}/plan`

### 5.6 Rituais e ofertas

Implementado:

- Listagem publica de rituais.
- Detalhe de ritual.
- Compra de ritual.
- Rituais pagos.
- Rituais gratuitos.
- Upsell/downsell pos-leitura.
- Oferta contextual por tema da ultima pergunta.
- Cupom aplicado em ritual.

Rotas:

- `GET /api/rituals`
- `GET /api/rituals/{ritual_id}`
- `POST /api/rituals/{ritual_id}/purchase`
- `GET /api/offers/after-reading`

### 5.7 CRM inteligente

Implementado:

- Tags de cliente.
- Segmentos.
- Associacao usuario/tag.
- Associacao usuario/segmento.
- Historico/notas administrativas.
- Classificacao de usuario.
- Gatilhos de automacao por segmento.
- Exportacao CSV.
- Aba dedicada no painel admin.

Rotas principais:

- `GET /api/admin/crm`
- `GET /api/admin/crm/users/{user_id}`
- `GET/POST/PATCH /api/admin/crm/tags`
- `POST /api/admin/crm/users/{user_id}/tags`
- `GET/POST/PATCH /api/admin/crm/segments`
- `POST /api/admin/crm/classify`
- `POST /api/admin/crm/users/{user_id}/notes`
- `GET/POST/PATCH /api/admin/crm/triggers`
- `GET /api/admin/crm/export.csv`

### 5.8 Automacoes, notificacoes e relacionamento

Implementado:

- Motor de automacoes.
- Regras de automacao.
- Etapas com delay, canal, mensagem e variaveis.
- Fila de `message_events`.
- Logs de notificacao.
- Boas-vindas.
- Retorno 24h.
- Recuperacao de pagamento abandonado.
- Campanha diaria de carta do dia renovada.
- Envio por email.
- Envio por WhatsApp via Uazapi.
- Worker em segundo plano.
- Scheduler local por `.bat` e `.ps1`.

Scripts:

- `tools/automation_engine.py`
- `tools/automation_worker.py`
- `tools/daily_card_renewal.py`
- `tools/flow_retorno_24h.py`
- `scheduler_automacoes_worker.bat`
- `scheduler_carta_do_dia.bat`
- `setup_agendamentos.ps1`

Ponto importante:

- Em validacao de maturidade de 2026-05-18, WhatsApp falhou por Uazapi HTTP 503/instancia desconectada por limite de assinatura zero.
- Em validacao anterior, envio real de WhatsApp ja havia passado com numero de teste. Portanto o codigo existe, mas a disponibilidade depende da conta/instancia Uazapi ativa.

### 5.9 Painel administrativo

Implementado:

- Login admin.
- Dashboard executivo.
- Usuarios.
- Creditos.
- Leituras.
- Pagamentos.
- Mensagens.
- Rituais.
- Campanhas.
- CRM.
- Planos.
- Pacotes.
- Cupons.
- Prompts.
- Configuracoes.
- Logs.
- Auditoria.
- Erros.
- Status operacional.
- Alertas.
- Relatorios financeiros.
- Relatorios de IA.
- Metricas de conversao, retencao e receita.
- Fila de reprocessamento.
- Modo manutencao.
- Redesign visual premium responsivo.

Rotas admin representativas:

- `GET /api/admin/dashboard`
- `GET /api/admin/users`
- `POST /api/admin/users/{user_id}/credits`
- `GET /api/admin/readings`
- `GET /api/admin/payments`
- `GET /api/admin/logs`
- `GET /api/admin/audit`
- `GET /api/admin/errors`
- `GET /api/admin/status`
- `GET /api/admin/alerts`
- `GET /api/admin/reports/financial`
- `GET /api/admin/reports/ai`

### 5.10 LGPD e juridico

Implementado:

- Termos de uso.
- Politica de privacidade.
- Aviso sobre IA.
- Aceite no cadastro.
- Exportacao de dados.
- Exclusao/anonimizacao de conta.
- Opt-in e opt-out de canais.
- Auditoria de acoes sensiveis.

Rotas:

- `GET /api/lgpd/export`
- `DELETE /api/lgpd/account`

Pendencia:

- Revisao juridica profissional antes de campanhas em escala.

### 5.11 Monitoramento, logs e operacao

Implementado:

- `GET /health`
- `GET /health/detailed`
- `GET /api/status`
- Painel de status admin.
- Logs estruturados em `system_logs`.
- Auditoria em `audit_logs`.
- Alertas internos.
- Fila de reprocessamento.
- Rotina diaria operacional.
- Pre-deploy check.
- Smoke test pos-deploy.

Scripts relevantes:

- `tools/status.py`
- `tools/daily_operation_check.py`
- `tools/predeploy_check.py`
- `tools/deploy_smoke_test.py`
- `tools/validate_production_sprint.py`
- `tools/validate_public_sale_readiness.py`

### 5.12 Backup e restore

Implementado:

- Backup via REST/Supabase.
- Manifesto de backup.
- Teste de restore/integridade.
- Runbook de backup e restore.

Arquivos:

- `tools/backup_database.py`
- `tools/restore_database_test.py`
- `architecture/backup_restore_runbook.md`
- `backups/latest_backup_manifest.json`
- `backups/latest_restore_test.json`

Pendencias:

- Backup Postgres `.dump` com `DATABASE_URL`, `SUPABASE_DB_URL` ou `SUPABASE_DB_PASSWORD`.
- Restore Postgres real em banco isolado antes de migracoes destrutivas.

## 6. Banco de dados

Contrato canonico:

- `architecture/schema.sql`

Migrations auxiliares:

- `architecture/migration_auth.sql`
- `architecture/migration_admin_operacional.sql`
- `architecture/migration_automacoes_notificacoes.sql`
- `architecture/migration_crm_inteligente.sql`
- `architecture/migration_fase10_lgpd_security.sql`
- `architecture/migration_rituals_credit_purchases.sql`
- `architecture/migration_user_avatar_url.sql`

Tabelas principais previstas/consolidadas:

- `users`
- `admin_users`
- `password_reset_tokens`
- `plans`
- `credit_packages`
- `coupons`
- `plan_change_history`
- `credit_transactions`
- `cards`
- `questions`
- `readings`
- `daily_cards`
- `subscriptions`
- `payments`
- `payment_webhook_events`
- `rituals`
- `ritual_purchases`
- `message_events`
- `automation_rules`
- `automation_steps`
- `notification_logs`
- `customer_tags`
- `user_customer_tags`
- `customer_segments`
- `user_customer_segments`
- `admin_customer_notes`
- `segment_automation_triggers`
- `system_logs`
- `audit_logs`
- `settings`
- `internal_alerts`
- `reprocess_queue`

## 7. Variaveis de ambiente

Templates existentes:

- `.env.example`
- `.env.homologation.example`
- `.env.production.example`

Categorias:

- Ambiente: `APP_ENV`, `ENVIRONMENT_NAME`, `APP_BASE_URL`, `APP_CORS_ORIGINS`, `APP_TIMEZONE`
- Auth: `JWT_SECRET`, `JWT_ISSUER`, `JWT_EXPIRES_SECONDS`, `ADMIN_EMAILS`, `ADMIN_DIRECT_ACCESS`
- IA: `GEMINI_API_KEY`, `GEMINI_MODEL`, `OPENAI_API_KEY`
- Supabase: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `SUPABASE_DB_URL`, `SUPABASE_DB_PASSWORD`
- Pagamentos: `PIX_GATEWAY`, `MERCADO_PAGO_*`, `STRIPE_*`, `ALLOW_MOCK_PAYMENTS`
- WhatsApp: `WHATSAPP_PROVIDER`, `WHATSAPP_API_URL`, `WHATSAPP_API_TOKEN`, `WHATSAPP_TEST_NUMBER`, `UAZAPI_CONVERT`
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
- Automacoes: `AUTOMATION_WORKER_INTERVAL_SECONDS`, `AUTOMATION_SYNC_RULES_ON_START`, `AUTOMATION_RETRY_DELAY_MINUTES`
- Operacao: `PENDING_MESSAGES_ALERT_THRESHOLD`, `BACKUP_DIR`, `LOG_LEVEL`

Regra de seguranca:

- Nunca publicar `.env` real.
- Producao deve usar `ADMIN_DIRECT_ACCESS=false`.
- Producao deve usar `ALLOW_MOCK_PAYMENTS=false`.
- Webhook Mercado Pago de producao deve apontar para dominio HTTPS final.

## 8. Deploy

Deploy recomendado:

- Render.

Servicos definidos em `render.yaml`:

- Web: `madame-do-luar-web`
- Worker: `madame-do-luar-worker`
- Cron: `madame-do-luar-daily-check`

Dominio planejado:

- `madamedoluar.com.br`
- `www.madamedoluar.com.br`

Comando web:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Comando worker:

```bash
python tools/automation_worker.py
```

Cron diario:

```bash
python tools/daily_operation_check.py
```

## 9. Validacoes ja registradas

Historico consolidado em `progress.md`:

- Backend importando sem erro em varias rodadas.
- `py_compile` em `api.py` e scripts principais.
- `node --check frontend/app.js`.
- `node --check frontend/admin.js`.
- `tools/check_text_quality.py`: OK em rodadas recentes.
- Pre-deploy com `.env.production.example`: OK com placeholders permitidos.
- Mercado Pago sandbox criando preferencias.
- Webhook Mercado Pago local assinado validado.
- Email SMTP validado.
- WhatsApp validado em sprint anterior, mas com falha operacional posterior por conta Uazapi.
- Painel admin validado com 219 rotas carregadas em sprint operacional.
- Backup e restore REST validados com 126 registros em 32 tabelas em evidencia anterior.
- Gate de venda publica retornou nao pronto porque faltam dominio final, HTTPS, webhook final e pagamento final ponta a ponta.

## 10. Estado real de prontidao

Pronto no repositorio/local:

- Backend funcional.
- Frontend publico.
- Painel admin.
- Auth.
- Perfil.
- Leituras com IA.
- Carta do dia.
- Creditos.
- Pagamentos sandbox.
- Webhooks locais/sandbox.
- CRM.
- Automacoes.
- Email.
- WhatsApp no codigo.
- LGPD tecnica.
- Logs/auditoria.
- Backup/restore REST.
- Deploy blueprint Render.

Nao concluir como pronto para venda publica ainda:

- Dominio final ativo.
- HTTPS emitido no provedor.
- Render sincronizado com secrets reais.
- Webhook Mercado Pago final apontado para dominio real.
- Pagamento real ponta a ponta em producao.
- Uazapi/WhatsApp com instancia ativa e plano operacional.
- Gate final `validate_public_sale_readiness.py` aprovado sem `FAIL` ou `BLOCKED`.
- Revisao juridica profissional.

## 11. Principais riscos atuais

Riscos tecnicos:

- `api.py` concentra muitas responsabilidades.
- `tools/db_client.py` tambem esta grande e centraliza muitas regras.
- Backend precisa ser modularizado para manutencao profissional.
- Algumas validacoes dependem de rede/credenciais reais.
- Estado real do schema Supabase deve ser revalidado antes de novas migrations.

Riscos operacionais:

- Venda publica sem webhook final pode causar pagamento aprovado sem liberacao automatica.
- WhatsApp depende de instancia ativa e plano Uazapi.
- Secrets de producao precisam estar separados e completos.
- Backup Postgres completo ainda depende de URL/senha de banco.

Riscos comerciais:

- Revisao juridica ainda recomendada.
- Precificacao deve continuar centralizada para evitar divergencia entre frontend, backend e painel.
- Campanhas pagas so devem iniciar apos gate publico aprovado.

## 12. Proximas fases recomendadas

Ordem recomendada:

1. Validar ambiente atual com `tools/validate_maturity_phase1.py`.
2. Resolver WhatsApp/Uazapi se ainda estiver com HTTP 503.
3. Garantir admin real por role `admin` ou `super_admin`.
4. Revalidar schema Supabase com `tools/verify_schema_phase3.py`.
5. Modularizar backend por dominio.
6. Centralizar precificacao em fonte unica editavel pelo admin.
7. Publicar Render com secrets reais.
8. Configurar DNS e HTTPS.
9. Configurar webhook Mercado Pago final.
10. Rodar gate final de venda publica.

Comando obrigatorio antes de venda publica:

```bash
python -B tools/validate_public_sale_readiness.py --env-file .env.production --live-auth-reading --live-notifications --public-base-url https://madamedoluar.com.br
```

O sistema so deve ser considerado pronto para trafego pago quando esse comando retornar sem `FAIL` e sem `BLOCKED`.

