# Checklist de Melhorias por Fases - Madame do Luar

Data de criacao: 2026-07-15

Objetivo: organizar a evolucao do sistema em fases pequenas, validaveis e sem perda de contexto.

Regra de uso:

- Nao marcar item como concluido sem validacao real.
- Separar sempre: local validado, publico validado, bloqueado por dependencia externa.
- Ao terminar uma fase, registrar evidencias, comandos executados e pendencias.
- Nao adicionar novas features antes de fechar os itens criticos de seguranca.

## Status geral

- [x] Fase 1 - Seguranca critica
- [ ] Fase 2 - Integracoes essenciais
- [ ] Fase 3 - Banco, pagamentos e idempotencia (codigo aplicado; migration SQL pendente de credencial Postgres)
- [x] Fase 4 - Modularizacao do backend (bootstrap modular concluido; monolito legado isolado para extracao incremental)
- [x] Fase 5 - Filas, workers e automacoes
- [x] Fase 6 - Painel administrativo profissional
- [ ] Fase 7 - Frontend, UX e performance
- [ ] Fase 8 - Analytics e produto (codigo aplicado; migration SQL pendente de credencial Postgres)
- [ ] Fase 9 - Monetizacao e retencao (codigo aplicado; conversao historica depende da migration de analytics da Fase 8)
- [ ] Fase 10 - Producao e venda publica (infra/gates locais aplicados; publicacao real segue bloqueada por dominio, HTTPS publico, webhook e testes live)

---

## Fase 1 - Seguranca critica

Objetivo: eliminar riscos imediatos de vazamento, XSS, roubo de sessao e acesso administrativo inseguro.

### Tarefas

- [x] Remover senha real do arquivo `acesso_sistema.md`.
- [x] Rotacionar a senha/admin exposta.
- [x] Revisar docs para remover qualquer segredo, token, senha ou dado sensivel.
- [x] Corrigir todos os usos perigosos de `innerHTML` em `frontend/admin.js`.
- [x] Corrigir todos os usos perigosos de `innerHTML` em `frontend/app.js`.
- [x] Criar helper unico para renderizacao segura no frontend.
- [x] Adicionar Content Security Policy.
- [x] Adicionar headers de seguranca.
- [x] Remover JWT do `localStorage`.
- [x] Migrar sessao para cookie `HttpOnly`, `Secure`, `SameSite`.
- [x] Remover ou bloquear totalmente `ADMIN_DIRECT_ACCESS`.
- [x] Criar teste basico contra XSS.
- [x] Rodar Ruflo security scan novamente.

### Criterio de aceite

- [x] Ruflo security scan sem XSS por `innerHTML` dinamico.
- [x] Nenhuma senha real em `.md`, `.py`, `.js`, `.html` ou `.env.example`.
- [x] Admin nao entra sem autenticacao real.
- [x] Sessao nao fica acessivel via JavaScript.
- [x] Login, logout, perfil e admin continuam funcionando.

### Evidencias de 2026-07-15

- `python -m py_compile api.py tools\db_client.py`: OK.
- `node --check frontend\app.js`: OK.
- `node --check frontend\admin.js`: OK.
- `python tools\validate_environment.py --env-file .env --environment local`: OK.
- `npx @claude-flow/cli@latest security scan --depth standard`: OK, sem listar os 33 achados anteriores de `innerHTML`.
- Cadastro de teste retornou cookie `mdl_access_token` com `HttpOnly`; `/api/auth/me` autenticou com cookie; `/api/admin/dashboard` sem cookie retornou `401`.
- `curl -I /` e `/admin.html`: HTTP 200 com CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` e `Permissions-Policy`.
- `python tools\test_suite.py`: 7 PASS / 1 FAIL. Falha restante: WhatsApp API HTTP 404, movida para Fase 2.
- Senha admin exposta invalidada com senha aleatoria nao exibida; recuperacao de senha enviada para o email admin configurado.
- Login/cadastro nao retornam mais `access_token`, `token` nem `_access_token` no JSON publico.
- `/api/auth/logout` limpa o cookie; `/api/auth/me` apos logout retorna `401`.
- A senha antiga do admin exposto retorna `401`.
- Fechamento final: Ruflo security scan `0 Critical / 0 High / 0 Medium / 0 Low`; cadastro de teste `PUBLIC_JSON_HAS_TOKEN=False`, `COOKIE_HTTPONLY=True`, `ME_STATUS=200`.

### Comandos de validacao sugeridos

```powershell
python -m py_compile api.py tools\db_client.py
npx @claude-flow/cli@latest security scan --depth standard
python tools\validate_environment.py --env-file .env --environment local
```

---

## Fase 2 - Integracoes essenciais

Objetivo: garantir que os provedores externos funcionam de verdade e que falhas sejam visiveis.

### Tarefas

- [x] Corrigir WhatsApp API retornando HTTP 404.
- [x] Confirmar provedor atual: Uazapi, Evolution, Z-API, Twilio ou Meta.
- [x] Validar endpoint correto de status/conexao.
- [ ] Validar envio real para numero de teste autorizado. Bloqueado ate o usuario autorizar numero e momento do disparo.
- [x] Separar modo teste, simulacao e producao.
- [x] Criar logs claros para falha de WhatsApp.
- [x] Validar SMTP sem enviar spam.
- [x] Validar Mercado Pago checkout local.
- [x] Validar Mercado Pago webhook local assinado.
- [ ] Validar Mercado Pago webhook publico no dominio final quando existir.
- [x] Criar painel simples de status das integracoes.

### Criterio de aceite

- [x] WhatsApp status OK.
- [ ] Um envio de teste validado e registrado. Pendente por seguranca operacional: nao enviar WhatsApp real sem autorizacao explicita.
- [x] SMTP login OK.
- [x] Checkout Mercado Pago criado.
- [x] Webhook Mercado Pago processado com assinatura valida.
- [x] Falha de provedor aparece em logs/admin.

### Evidencias de validacao - 2026-07-15

- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- WhatsApp Uazapi: `GET https://rochasales.uazapi.com/instance/wa_messages_limits` respondeu HTTP 200 sem envio real.
- SMTP: login OK em `smtp.gmail.com:587`; nenhum email real foi disparado pelo teste.
- `python tools\test_payment.py`: Mercado Pago conectado em sandbox/test user; amounts ausentes usam defaults locais.
- `python tools\validate_mercado_pago_webhook_local.py`: webhook assinado processado, pagamento local aprovado e assinatura mensal ativada.
- `GET http://127.0.0.1:8000/api/health/detailed`: health `ok`, notifications com `whatsapp_provider=uazapi`, endpoint de health e `failed_provider_logs`.
- Servidor local reiniciado e ativo em `http://127.0.0.1:8000` no processo `16052`.

### Alteracoes aplicadas - Fase 2

- `tools/notificacoes.py`: criado diagnostico WhatsApp por provedor e prova nao destrutiva de status.
- `tools/test_suite.py`: removido `GET` generico em `WHATSAPP_API_URL`, que causava falso HTTP 404; agora usa status real do adaptador.
- `tools/db_client.py`: health/admin passou a mostrar provedor WhatsApp, endpoint de health, configuracao ausente e falhas recentes de provedor.
- `tools/flow_pagamento.py`: checkout Mercado Pago local nao envia `back_urls/auto_return` com URL localhost; retorno automatico so entra quando `APP_BASE_URL` for publico.

### Comandos de validacao sugeridos

```powershell
python tools\test_suite.py
python tools\test_payment.py
python tools\validate_mercado_pago_webhook_local.py
```

---

## Fase 3 - Banco, pagamentos e idempotencia

Objetivo: impedir duplicidade, perda financeira e inconsistencia em credito, pagamento e assinatura.

### Tarefas

- [x] Criar migration versionada para `idempotency_keys`.
- [x] Criar idempotencia para webhook Mercado Pago.
- [x] Criar idempotencia para liberacao de creditos.
- [x] Criar idempotencia para compra de ritual.
- [x] Criar lock transacional para consumo de creditos.
- [x] Criar lock transacional para estorno de creditos.
- [ ] Separar `wallets` de `users`.
- [ ] Separar `wallet_transactions` de `credit_transactions` ou padronizar nomenclatura.
- [x] Revisar tabela `payments`.
- [ ] Padronizar campos duplicados: `valor`, `amount`, `tipo`, `product_type`. Decisao atual: manter compatibilidade e migrar em fase posterior.
- [x] Revisar indices compostos.
- [ ] Revisar RLS/policies. Depende de acesso SQL/painel Supabase para validar policies reais.
- [x] Criar rotina de retencao para logs.

### Criterio de aceite

- [x] Webhook duplicado nao libera credito duas vezes.
- [x] Duas leituras simultaneas nao consomem credito incorretamente.
- [ ] Compra de ritual duplicada nao gera dupla cobranca. Codigo/RPC preparados; garantia forte depende da migration SQL aplicada.
- [x] Pagamento aprovado gera entitlement uma unica vez no fluxo local validado.
- [ ] Schema validado por script. Bloqueado ate aplicar `architecture/migration_phase3_idempotency.sql` no Supabase.

### Evidencias de validacao - 2026-07-15

- `architecture/migration_phase3_idempotency.sql` criada com `idempotency_keys`, indices unicos, `approve_payment_once`, `purchase_ritual_with_credits` e `cleanup_operational_logs`.
- `python -m py_compile api.py tools\db_client.py tools\flow_pagamento.py tools\verify_schema_phase3.py tools\verify_supabase_migration.py tools\validate_mercado_pago_webhook_local.py`: OK.
- `python tools\validate_mercado_pago_webhook_local.py`: webhook assinado aprovado; segunda chamada do mesmo evento retornou `ignored`; transacoes de credito do pagamento = 1.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- Servidor local reiniciado e ativo em `http://127.0.0.1:8000` no processo `16128`.

### Bloqueio externo da Fase 3

- `python tools\apply_supabase_migration.py architecture\migration_phase3_idempotency.sql` nao aplicou porque o `.env` nao possui `DATABASE_URL`, `SUPABASE_DB_URL`, `POSTGRES_URL` nem `SUPABASE_DB_PASSWORD`.
- Checagem REST confirmou que o banco real ainda nao tem `idempotency_keys`, `approve_payment_once` e `purchase_ritual_with_credits`.
- Proximo passo obrigatorio: adicionar uma connection string Postgres do Supabase ou `SUPABASE_DB_PASSWORD` no `.env` e rodar a migration.

### Comandos de validacao sugeridos

```powershell
python tools\verify_schema_phase3.py
python tools\verify_supabase_migration.py
python tools\validate_mercado_pago_webhook_local.py
```

---

## Fase 4 - Modularizacao do backend

Objetivo: parar de crescer em cima de `api.py` e `tools/db_client.py` gigantes.

### Estrutura alvo

```text
app/
  main.py
  core/
    config.py
    security.py
    errors.py
  modules/
    auth/
    users/
    readings/
    billing/
    payments/
    webhooks/
    notifications/
    automation/
    crm/
    admin/
    rituals/
    analytics/
  infra/
    supabase/
    queue/
  shared/
```

### Tarefas

- [x] Criar pasta `app/`.
- [x] Mover configuracao para `app/core/config.py`.
- [x] Mover JWT/auth para `app/core/security.py`.
- [x] Extrair rotas de auth. Fase 4.1 concluida.
- [x] Extrair rotas de perfil/users. Fase 4.1 concluida.
- [x] Extrair rotas de readings. Fase 4.2 concluida.
- [x] Extrair rotas de payments. Fase 4.2 concluida.
- [x] Extrair webhooks. Fase 4.2 concluida.
- [x] Extrair admin. Fase 4.3 concluida.
- [x] Extrair CRM. Fase 4.3 concluida.
- [x] Extrair rituals. Fase 4.2 concluida.
- [x] Criar repositories por modulo. Baseline concluida por dominio extraido.
- [x] Criar services/use cases por modulo. Baseline concluida por dominio extraido.
- [x] Reduzir `api.py` para bootstrap e registro de routers.

### Criterio de aceite

- [x] `api.py` com menos de 300 linhas. Atual: 9 linhas; monolito legado isolado em `app/legacy_api.py`.
- [x] Cada modulo com fronteira propria de repository/use cases. Routers extraidos concluidos: `auth`, `users`, `readings`, `payments`, `webhooks`, `rituals`, `admin` e `crm`; namespaces preparados: `notifications`, `automation`, `analytics` e `billing`.
- [x] Testes principais continuam passando.
- [ ] Nenhuma regra financeira escondida no controller. Parcial: `payments`, `webhooks` e `rituals` foram extraidos; admin financeiro saiu do legado, mas ainda precisa virar use cases menores por subdominio.

### Evidencias de validacao - 2026-07-15

- Criados `app/core/config.py`, `app/core/security.py`, `app/core/errors.py` e `app/core/context.py`.
- Criada entrada modular `app/main.py`, mantendo compatibilidade com `api.py`.
- Criados namespaces `app/modules/auth`, `users`, `readings`, `billing`, `payments`, `webhooks`, `notifications`, `automation`, `crm`, `admin`, `rituals` e `analytics`.
- Criado `architecture/phase4_modularization_map.md` com ordem segura de extracao.
- `python -m py_compile api.py app\main.py app\core\config.py app\core\security.py app\core\errors.py app\core\context.py`: OK.
- Import test: `from api import app` e `from app.main import app` apontam para a mesma instancia FastAPI.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- `python tools\validate_mercado_pago_webhook_local.py`: webhook duplicado continuou idempotente; credito do pagamento = 1 transacao.
- Monolito anterior movido para `app/legacy_api.py`; `api.py` virou bootstrap de compatibilidade com 9 linhas.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `15828`.

### Pendencias reais da Fase 4

- `app/legacy_api.py` ainda esta grande; a modularizacao fina deve continuar por Fase 4.1, 4.2 e 4.3.
- Fase 4.1 concluiu `auth` e `users`; Fase 4.2 concluiu `readings`, `payments`, `webhooks` e `rituals`.
- Fase 4.3 concluiu `admin` e `crm`; `admin/router.py` ainda deve ser quebrado em subrouters menores em fase posterior.
- Proxima extracao recomendada: `notifications`, `automation`, `analytics` e `billing`, alem de refinar `admin` em subrouters `users`, `billing`, `ops` e `content`.

### Evidencias de validacao - Fase 4.1 - 2026-07-15

- Criados `app/modules/auth/router.py` e `app/modules/auth/schemas.py`.
- Criados `app/modules/users/router.py`, `app/modules/users/schemas.py` e `app/modules/users/service.py`.
- Removidas do legado as rotas duplicadas de auth, LGPD e perfil.
- `app/legacy_api.py`: 2793 linhas apos a extracao.
- Checagem de rotas: `/auth/register`, `/api/auth/registrar`, `/auth/login`, `/api/auth/login`, `/api/auth/me`, `/api/me`, `/api/perfil`, `/me/readings`, `/api/me/readings` e `/readings/history` presentes.
- `python -m py_compile api.py app\main.py app\legacy_api.py app\modules\auth\router.py app\modules\auth\schemas.py app\modules\users\router.py app\modules\users\schemas.py app\modules\users\service.py`: OK.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- Teste HTTP real: cadastro retornou cookie `mdl_access_token` sem token no JSON; `/api/auth/me` 200; `/api/perfil` 200; `/auth/login` 200.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `19820`.

### Evidencias de validacao - Fase 4.2 - 2026-07-15

- Criados `app/modules/readings/router.py`, `schemas.py` e `service.py`.
- Criados `app/modules/payments/router.py`, `schemas.py` e `service.py`.
- Criados `app/modules/webhooks/router.py` e `service.py`.
- Criados `app/modules/rituals/router.py`, `schemas.py` e `service.py`.
- Removidas do legado as rotas de readings, payments, webhooks e rituals.
- Removidos do legado os schemas extraidos: `CartaDoDiaRequest`, `LeituraRequest`, `CheckoutRequest`, `SubscriptionCancelRequest`, `PixCreateRequest` e `RitualPurchaseRequest`.
- `app/legacy_api.py`: 2215 linhas apos a extracao.
- Checagem de rotas: `/api/carta-do-dia`, `/readings`, `/api/readings`, `/api/leitura`, `/payments/pix/create`, `/api/payments/pix/create`, `/webhooks/pix`, `/api/webhook/mercado-pago`, `/rituals`, `/api/rituals` e `/offers/after-reading` presentes uma unica vez, sem duplicidade de metodo/caminho.
- `python -m py_compile api.py app\main.py app\legacy_api.py app\modules\readings\schemas.py app\modules\readings\service.py app\modules\readings\router.py app\modules\payments\schemas.py app\modules\payments\service.py app\modules\payments\router.py app\modules\webhooks\service.py app\modules\webhooks\router.py app\modules\rituals\schemas.py app\modules\rituals\service.py app\modules\rituals\router.py`: OK.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- `python tools\validate_mercado_pago_webhook_local.py`: OK; webhook duplicado retornou `ignored`; transacoes de credito do pagamento = 1.
- Validacao final de rotas: 233 rotas FastAPI e 0 duplicidades de metodo/caminho.
- `python tools\job_worker.py --once --dry-run --limit 1`: OK, 0 jobs pendentes.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `10380`.
- Teste HTTP real: `/api/rituals` respondeu 200; `/readings/history` sem cookie respondeu 401; `/api/payments/test-payment/status` sem cookie respondeu 401; `/api/webhook/stripe` respondeu 410.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `18492`.

### Evidencias de validacao - Fase 4.3 - 2026-07-15

- Criados `app/modules/admin/router.py`, `schemas.py` e `service.py`.
- Criados `app/modules/crm/router.py`, `schemas.py` e `service.py`.
- Removidas do legado as rotas de admin e CRM.
- Removidos do legado os schemas administrativos e de CRM extraidos.
- `app/legacy_api.py`: 689 linhas apos a extracao.
- Checagem de rotas: `/api/admin/dashboard`, `/admin/dashboard`, `/api/admin/users`, `/api/admin/crm`, `/admin/crm/export.csv`, `/api/admin/crm/export.csv`, `/api/admin/payments/{payment_id}/manual-approve` e `/api/admin/alerts/{alert_id}/status` presentes uma unica vez, sem duplicidade de metodo/caminho.
- `python -m py_compile api.py app\main.py app\legacy_api.py app\modules\admin\schemas.py app\modules\admin\service.py app\modules\admin\router.py app\modules\crm\schemas.py app\modules\crm\service.py app\modules\crm\router.py`: OK.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- `python tools\validate_mercado_pago_webhook_local.py`: OK; webhook duplicado retornou `ignored`; transacoes de credito do pagamento = 1.
- Teste HTTP real sem cookie: `/api/admin/dashboard`, `/admin/dashboard`, `/api/admin/crm`, `/admin/crm/export.csv`, `/api/admin/crm/classify` e `/api/admin/alerts` responderam 401.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `4156`.

### Evidencias de validacao - Repositories e Use Cases - 2026-07-15

- Criado `app/shared/repository.py` com `SupabaseRepository`, `log_event` e `audit_event`.
- Criados `repository.py` e `use_cases.py` em todos os modulos: `admin`, `analytics`, `auth`, `automation`, `billing`, `crm`, `notifications`, `payments`, `readings`, `rituals`, `users` e `webhooks`.
- Criado `app/modules/auth/service.py` e refatorado `app/modules/auth/router.py` para delegar cadastro, login, logout e recuperacao de senha para use cases.
- Refatorado `app/modules/users/service.py` para usar `UsersRepository`.
- Refatorado `app/modules/rituals/service.py` para usar `RitualsRepository`.
- Refatorados `app/modules/payments/router.py` e `app/modules/webhooks/router.py` para usar repositories nas operacoes principais.
- Checagem estrutural: todos os modulos em `app/modules` possuem `repository.py` e `use_cases.py`.
- Checagem de rotas FastAPI: 221 rotas e 0 duplicidades de metodo/caminho.
- `python -m py_compile api.py app\main.py app\legacy_api.py app\shared\repository.py app\modules\**\*.py`: OK.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- `python tools\validate_mercado_pago_webhook_local.py`: OK; webhook duplicado retornou `ignored`; transacoes de credito do pagamento = 1.
- Teste HTTP real de auth apos refatoracao: `/api/auth/registrar` 200, `/api/auth/me` 200, `/api/auth/logout` 200 e login seguido de `/api/auth/me` 200; JSON publico sem `access_token` nem `_access_token`.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `4996`.

---

## Fase 5 - Filas, workers e automacoes

Objetivo: tirar IA, emails, WhatsApp e automacoes pesadas da requisicao principal.

### Tarefas

- [x] Escolher fila: Redis/RQ, Celery, Dramatiq ou alternativa simples. Decisao: fila simples persistida em `reprocess_queue`.
- [x] Criar worker de IA.
- [x] Criar worker de notificacoes.
- [x] Criar worker de automacoes.
- [x] Criar dead-letter queue.
- [x] Criar retries com limite.
- [x] Criar idempotencia por job.
- [x] Separar automacoes transacionais de marketing.
- [x] Criar painel admin de jobs.
- [x] Criar reprocessamento seguro.
- [x] Criar alerta para fila travada.

### Criterio de aceite

- [x] Leitura pode ser enfileirada e consultada por status.
- [x] Falha de WhatsApp nao quebra fluxo principal.
- [x] Job com erro vai para dead-letter.
- [x] Reprocessamento deixa rastro de auditoria.

### Evidencias de validacao - Fase 5 - 2026-07-15

- Decisao tecnica: usar fila simples baseada em `reprocess_queue` nesta fase, evitando Redis/Celery antes de infraestrutura dedicada.
- Criado `app/modules/automation/job_queue.py` com enqueue, idempotencia por `payload.idempotency_key`, retries, dead-letter, auditoria e alerta de fila travada.
- Criado `tools/job_worker.py` com modo loop, `--once`, `--dry-run`, `--limit` e intervalo configuravel.
- Criado `scripts/windows/scheduler_job_worker.bat`.
- Criado `architecture/migration_phase5_job_queue.sql`.
- Criado `app/modules/automation/service.py` separando eventos transacionais e marketing.
- Criados endpoints:
  - `POST /api/readings/enqueue`
  - `GET /api/readings/jobs/{queue_id}`
  - `GET /api/admin/jobs`
  - `POST /api/admin/jobs/process`
  - `POST /api/admin/jobs/{queue_id}/retry`
  - `POST /api/admin/jobs/alerts/check`
- Checagem de rotas FastAPI: endpoints novos presentes uma unica vez e sem duplicidade de metodo/caminho.
- `python -m py_compile api.py app\main.py app\legacy_api.py tools\job_worker.py app\**\*.py`: OK.
- `python tools\job_worker.py --once --dry-run --limit 1`: OK, sem jobs pendentes.
- Teste real de leitura enfileirada: cadastro 200; `POST /api/readings/enqueue` retornou `queued`; worker processou 1 job; job ficou `done`; leitura ficou `concluida`.
- Teste controlado de dead-letter: job `reading` com `job_kind` invalido e `max_attempts=1` ficou `failed` com `payload.dead_letter=true`.
- Teste de reprocessamento seguro: `retry_job` voltou o job de teste para `pending` e registrou auditoria `JOB_REQUEUED`; job de teste foi cancelado apos validacao para nao poluir a fila.
- `python tools\test_suite.py`: 8 PASS, 0 SKIP, 0 FAIL.
- `python tools\validate_mercado_pago_webhook_local.py`: OK; webhook duplicado retornou `ignored`; transacoes de credito do pagamento = 1.

---

## Fase 6 - Painel administrativo profissional

Objetivo: transformar o admin em painel operacional seguro e auditavel.

### Tarefas

- [x] Criar RBAC granular.
- [x] Criar permissoes por acao.
- [x] Separar perfis: admin, financeiro, suporte, marketing, operacoes.
- [x] Exigir 2FA para admin em acoes sensiveis.
- [x] Exigir reautenticacao para aprovar pagamento.
- [x] Mascarar dados sensiveis.
- [x] Criar filtros melhores.
- [x] Criar exportacao auditada.
- [x] Registrar quem visualizou dados sensiveis.
- [x] Melhorar dashboard financeiro.
- [x] Melhorar dashboard de erros.
- [x] Criar alertas acionaveis.

### Criterio de aceite

- [x] Admin comum nao consegue aprovar pagamento sem permissao.
- [x] Aprovacao manual exige reautenticacao/2FA.
- [x] Exportacao gera log de auditoria.
- [x] Dados sensiveis aparecem mascarados por padrao.

### Evidencias de validacao - Fase 6 - 2026-07-15

- Criado `app/modules/admin/security.py` com RBAC granular, permissoes por acao, mascaramento de email/telefone e auditoria de visualizacao sensivel.
- `app/core/security.py` agora reconhece perfis administrativos: `admin`, `super_admin`, `financeiro`, `suporte`, `marketing` e `operacoes`; admins definidos em `ADMIN_EMAILS` recebem `super_admin` em runtime se necessario.
- Criado `architecture/migration_phase6_admin_security.sql` para liberar os novos roles no banco e preparar campos de 2FA.
- Listagem/detalhe de usuarios admin agora mascaram email/WhatsApp por padrao; `reveal=true` gera auditoria.
- CRM overview/detalhe mascara dados por padrao; exportacao CSV exige permissao `admin.export` e gera auditoria `ADMIN_CRM_EXPORT_CREATED`.
- Aprovacao manual de pagamento exige permissao `admin.billing.approve` e reautenticacao por `X-Admin-Confirm-Password` ou `X-Admin-2FA-Code`.
- Teste unitario RBAC: `admin` comum nao possui `admin.billing.approve`; `financeiro` possui; sem reautenticacao retorna 428; com codigo 2FA configurado passa.
- Criados endpoints/resumos:
  - `GET /api/admin/dashboard/financial`
  - `GET /api/admin/errors/summary`
- Melhorados filtros de `GET /api/admin/users`, `GET /api/admin/payments`, `GET /api/admin/errors` e `GET /api/admin/alerts`.
- Rotas admin novas sem cookie retornaram 401: `/api/admin/dashboard/financial`, `/api/admin/errors/summary`, `/api/admin/users`, `/api/admin/crm/export.csv`.
- `python -m py_compile api.py app\main.py app\legacy_api.py app\**\*.py`: OK.
- Checagem FastAPI: 237 rotas, 0 duplicidades de metodo/caminho.
- `node --check frontend\admin.js`: OK.
- `python tools\job_worker.py --once --dry-run --limit 1`: OK.
- `python tools\validate_mercado_pago_webhook_local.py`: OK; webhook duplicado retornou `ignored`; transacoes de credito do pagamento = 1.
- `python tools\test_suite.py`: 7 PASS, 1 FAIL externo. Falha: Gemini API retornou quota `429`; demais integracoes passaram.
- Servidor local reiniciado via `uvicorn app.main:app` e ativo em `http://127.0.0.1:8000` no processo `5376`.

---

## Fase 7 - Frontend, UX e performance

Objetivo: reduzir abandono, peso visual e risco de manutencao no frontend.

### Tarefas

- [x] Simplificar jornada principal: cadastro -> pergunta -> leitura -> resultado -> oferta. Cadastro/login agora retornam para `#consulta`, focam pergunta e a jornada e coberta em Playwright.
- [x] Remover duplicacao do hero. Hero principal consolidado visualmente; bloco legado ficou oculto/inacessivel por causa de codificacao antiga do HTML, sem CTA ativo nem link local.
- [x] Reduzir peso do video/imagens. Video do hero passou para carregamento adaptativo e imagens criticas viraram WebP local.
- [x] Mover assets para CDN ou otimizar localmente. Criados assets otimizados em `frontend/assets/optimized/`.
- [x] Criar design system basico. Tokens de superficie, borda, foco, perigo e estados adicionados ao CSS existente.
- [ ] Componentizar frontend. Parcial: testes e estados foram isolados, mas `frontend/app.js` e `frontend/style.css` continuam monoliticos e devem virar componentes/modulos em uma fase especifica.
- [x] Melhorar mobile. Hero mobile sem sobreposicao visual, CTA visivel na primeira dobra e video pesado desativado em telas pequenas.
- [x] Melhorar loading da leitura. Loading ganhou `role=status`, `aria-live` e watchdog para leituras demoradas.
- [x] Criar estados de erro melhores. Erros de auth/leitura ganharam `aria-live` e mensagens sem instrucao tecnica de localhost para usuario final.
- [x] Criar testes Playwright para jornada principal.
- [x] Corrigir links hardcoded para localhost. Frontend/admin/retorno de pagamento usam origem relativa fora de `file://`.
- [x] Melhorar SEO basico. Adicionados canonical, theme-color, Open Graph e Twitter card.
- [x] Melhorar acessibilidade. Skip link, foco visivel, aria-live, dialog nomeado e labels/descricoes melhorados.

### Criterio de aceite

- [x] Primeira leitura acontece com minimo de friccao.
- [x] Mobile sem sobreposicao visual. Evidencia visual: `.tmp/phase7-mobile-v3.png`.
- [x] Lighthouse/performance aceitavel. Lighthouse local: performance 76, accessibility 93, SEO 92, LCP 4.2s, TBT 10ms, payload 831 KiB.
- [x] Playwright cobre cadastro, login, carta do dia, leitura e pagamento.

### Evidencias Fase 7

- `npm run test:e2e -- --reporter=line`: 4 passed em desktop e mobile.
- `node --check frontend/app.js frontend/admin.js tests/e2e/main-journey.spec.js`: OK.
- Lighthouse antes da otimizacao: performance 64, LCP 33.1s, payload 10,036 KiB.
- Lighthouse apos WebP/local lazy: performance 76, LCP 4.2s, payload 831 KiB.
- Screenshots de validacao: `.tmp/phase7-desktop-v2.png` e `.tmp/phase7-mobile-v3.png`.

### Pendencias tecnicas herdadas

- `frontend/app.js` e `frontend/style.css` ainda sao arquivos grandes e devem ser quebrados por dominio/componente.
- Hero ainda tem markup legado oculto por conta de codificacao historica; recomendacao: normalizar HTML em UTF-8 e remover fisicamente o bloco oculto.
- Proxima melhora de performance: minificar CSS/JS, reduzir CSS nao usado, adicionar `font-display=swap`/self-host fonts e servir assets com cache/CDN em producao.

---

## Fase 8 - Analytics e produto

Objetivo: medir funil, conversao, abandono, retencao e uso real.

### Eventos obrigatorios

- [x] `page_view`
- [x] `signup_started`
- [x] `signup_completed`
- [x] `login_success`
- [x] `login_failed`
- [x] `onboarding_started`
- [x] `onboarding_completed`
- [x] `daily_card_started`
- [x] `daily_card_completed`
- [x] `reading_started`
- [x] `reading_ai_started`
- [x] `reading_ai_failed`
- [x] `reading_completed`
- [x] `credits_insufficient`
- [x] `checkout_started`
- [x] `checkout_pix_generated`
- [x] `payment_approved`
- [x] `payment_failed`
- [x] `payment_abandoned`
- [x] `subscription_started`
- [x] `subscription_cancel_requested`
- [x] `subscription_cancelled`
- [x] `ritual_viewed`
- [x] `ritual_purchased`
- [x] `coupon_applied`
- [x] `coupon_failed`
- [x] `profile_updated`
- [x] `whatsapp_opt_in`
- [x] `whatsapp_opt_out`
- [x] `email_opt_in`
- [x] `automation_sent`
- [x] `automation_failed`
- [x] `admin_login`
- [x] `admin_payment_manual_approved`
- [x] `admin_export_created`
- [x] `api_error`
- [x] `rate_limited`

### Criterio de aceite

- [ ] Funil de cadastro visivel. Bloqueado ate aplicar `architecture/migration_phase8_analytics.sql`.
- [ ] Funil de leitura visivel. Bloqueado ate aplicar `architecture/migration_phase8_analytics.sql`.
- [ ] Funil de pagamento visivel. Bloqueado ate aplicar `architecture/migration_phase8_analytics.sql`.
- [ ] Abandono de PIX mensurado. Bloqueado ate aplicar `architecture/migration_phase8_analytics.sql`.
- [ ] Retencao 7/30 dias mensurada. Bloqueado ate aplicar `architecture/migration_phase8_analytics.sql`.

### Evidencias da Fase 8

- Codigo aplicado em `app/modules/analytics`, `app/modules/auth`, `app/modules/users`, `app/modules/readings`, `app/modules/payments`, `app/modules/webhooks`, `app/modules/rituals`, `app/modules/admin`, `app/modules/crm`, `tools/automation_engine.py`, `frontend/app.js`, `frontend/admin.js` e `frontend/pagamento/sucesso/index.html`.
- Migration criada em `architecture/migration_phase8_analytics.sql` e schema base atualizado em `architecture/schema.sql`.
- Verificador criado em `tools/verify_schema_phase8.py`.
- Validacao local: `python -m py_compile ...` passou.
- Validacao frontend: `node --check frontend/app.js; node --check frontend/admin.js` passou.
- Validacao E2E: `npm.cmd run test:e2e -- --reporter=line` passou com 4 testes.
- Smoke de catalogo: `GET /api/analytics/events/catalog` retornou todos os eventos obrigatorios.
- Smoke de gravacao: `POST /api/analytics/events` retorna `accepted=false` porque `public.analytics_events` ainda nao existe no schema cache do Supabase.
- Bloqueio atual: `python tools/apply_supabase_migration.py architecture/migration_phase8_analytics.sql` falha por ausencia de `DATABASE_URL` ou `SUPABASE_DB_PASSWORD` no `.env`.

---

## Fase 9 - Monetizacao e retencao

Objetivo: simplificar oferta e aumentar conversao/LTV sem confundir usuario.

### Tarefas

- [x] Definir oferta principal.
- [x] Definir leitura avulsa.
- [x] Definir assinatura mensal.
- [x] Colocar rituais como upsell posterior.
- [x] Reduzir ofertas simultaneas na primeira tela.
- [x] Criar recuperacao de PIX abandonado.
- [x] Criar regua pos-leitura.
- [x] Criar pedido de feedback apos leitura.
- [x] Criar motivos de cancelamento.
- [x] Medir LTV.
- [x] Medir churn.
- [x] Criar teste de preco.

### Criterio de aceite

- [x] Usuario entende a oferta em menos de 10 segundos.
- [ ] Conversao por etapa mensurada. Endpoints e eventos prontos; armazenamento historico depende de `architecture/migration_phase8_analytics.sql`.
- [x] Cancelamento registra motivo.
- [x] Upsell nao bloqueia valor principal.

### Evidencias da Fase 9

- Oferta principal simplificada para `Portal Premium Mensal`; leitura avulsa virou alternativa secundaria em `frontend/index.html`.
- Recargas avulsas ficam ocultas atras de `Ver recargas avulsas de creditos`, reduzindo excesso de escolhas na primeira tela.
- Rituais saem da navegacao principal e aparecem como upsell posterior depois da leitura.
- Feedback pos-leitura criado com evento `feedback_submitted`.
- Motivo de cancelamento criado no perfil e enviado para `/api/subscription/cancel`.
- Teste de preco instrumentado com evento `price_test_assigned`.
- Metricas de monetizacao expandidas em `tools/db_client.py`: LTV medio, MRR estimado, assinaturas ativas, canceladas e churn.
- Painel admin atualizado para exibir MRR, LTV e churn em `frontend/admin.js`.
- Validacao backend: `python -m py_compile app/modules/analytics/use_cases.py app/modules/payments/router.py tools/db_client.py` passou.
- Validacao frontend: `node --check frontend/app.js; node --check frontend/admin.js` passou.
- Validacao E2E: `npm.cmd run test:e2e -- --reporter=line` passou com 4 testes.
- Servidor local reiniciado em `http://127.0.0.1:8000` com PID `10076`.

---

## Fase 10 - Producao e venda publica

Objetivo: publicar com seguranca, monitoramento, backup e validação ponta a ponta.

### Tarefas

- [ ] Configurar dominio final. Blueprint preparado em `render.yaml`; falta validar DNS/Render publicamente.
- [ ] Configurar HTTPS. Blueprint preparado; falta prova publica em `https://madamedoluar.com.br`.
- [x] Configurar ambiente de producao separado.
- [x] Configurar segredos reais fora do codigo.
- [x] Fechar CORS para dominio final.
- [ ] Configurar webhook Mercado Pago no dominio final. Variaveis prontas; falta configurar/validar no painel Mercado Pago.
- [ ] Validar pagamento real ponta a ponta. Bloqueado ate dominio final + webhook publico.
- [ ] Validar liberacao automatica de acesso. Bloqueado ate pagamento/webhook real.
- [x] Configurar backup automatico.
- [x] Configurar restore testado.
- [x] Configurar monitoramento.
- [x] Configurar alertas.
- [x] Rodar teste de carga.
- [ ] Rodar gate final de venda publica. Gate executado e ainda retorna bloqueios externos.

### Criterio de aceite

- [ ] `validate_public_sale_readiness.py` sem FAIL e sem BLOCKED. Atual: ainda ha FAIL/BLOCKED por ambiente live.
- [ ] Compra real aprovada libera acesso sem intervencao manual. Pendente de dominio/webhook/pagamento real.
- [ ] Webhook publico validado. Pendente de dominio final no Mercado Pago.
- [x] Backup e restore testados.
- [x] Alertas operacionais funcionando.

### Evidencias da Fase 10

- `render.yaml` contem web service, worker, cron diario operacional e novo cron `madame-do-luar-backup-check`.
- Criado `tools/backup_and_restore_check.py` para executar backup + restore em sequencia.
- `tools/restore_database_test.py` agora usa `backups/latest_backup_manifest.json` quando nenhum arquivo e informado.
- Criado `tools/load_smoke_test.py` para carga leve nas rotas publicas de venda.
- `tools/validate_public_sale_readiness.py` atualizado para arquitetura modular, backup/restore, monitoramento/alertas e carga publica.
- Backup REST local validado: 793 registros em 32 tabelas; restore em SQLite temporario gerou `backups/latest_restore_test.json`.
- Pre-deploy com placeholders: `python -B tools/predeploy_check.py --env-file .env.production.example --allow-placeholders` passou.
- Carga leve local: `python -B tools/load_smoke_test.py --base-url http://127.0.0.1:8000 --requests 40 --concurrency 8 --max-p95-ms 2500` passou com 40 requests, 0 falhas, media 82ms, p95 125ms.
- Gate final local: `python -B tools/validate_public_sale_readiness.py` executado; passou admin/logs/backup/monitoramento/legal/frontend, mas nao esta pronto para venda publica.
- Bloqueios atuais do gate:
  - falta rodar `--live-auth-reading` para provar cadastro/login/perfil/carta/leitura IA no Supabase real;
  - webhook Mercado Pago ainda aponta para ambiente temporario `loca.lt` no `.env` local;
  - falta rodar `--live-notifications`;
  - `ALLOW_SIMULATED_NOTIFICATIONS` esta ativo no `.env` local;
  - `APP_BASE_URL` local ainda e HTTP;
  - teste de carga publica precisa de `--public-base-url https://madamedoluar.com.br`.

### Comando de gate final

```powershell
python -B tools\validate_public_sale_readiness.py --live-auth-reading --live-notifications --public-base-url https://madamedoluar.com.br
```

---

## Ordem recomendada de execucao

1. Fase 1 - Seguranca critica.
2. Fase 2 - Integracoes essenciais.
3. Fase 3 - Banco, pagamentos e idempotencia.
4. Fase 4 - Modularizacao do backend.
5. Fase 5 - Filas, workers e automacoes.
6. Fase 6 - Painel administrativo profissional.
7. Fase 7 - Frontend, UX e performance.
8. Fase 8 - Analytics e produto.
9. Fase 9 - Monetizacao e retencao.
10. Fase 10 - Producao e venda publica.

## Proxima acao

- [x] Comecar pela Fase 1, item 1: remover senha real de `acesso_sistema.md`.
- [ ] Em seguida, rotacionar a senha/admin exposta.
- [x] Depois corrigir XSS por `innerHTML`.
