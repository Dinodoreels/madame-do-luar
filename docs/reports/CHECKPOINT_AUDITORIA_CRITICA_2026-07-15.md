# Checkpoint de Auditoria Critica - Madame do Luar

Data: 2026-07-15
Escopo: auditoria critica de arquitetura, produto, seguranca, UX, banco, backend, frontend, operacao e escalabilidade.

## Estado verificado

- Sistema local rodando em `http://127.0.0.1:8000`.
- Frontend usuario e admin respondem HTTP 200.
- `.env` local validado com `python tools\validate_environment.py --env-file .env --environment local`.
- Suite `tools\test_suite.py`: 7 PASS, 1 FAIL.
- Falha atual: WhatsApp API retorna HTTP 404 no endpoint configurado.
- Ruflo security scan executado via `npx @claude-flow/cli@latest security scan --depth standard`: 33 issues MEDIUM, todas relacionadas a `innerHTML`.
- Predeploy bloqueado por matriz de producao com placeholders/segredos ausentes em `.env.production.example`.
- O projeto esta funcional localmente, mas nao esta pronto para venda publica.

## Diagnostico executivo

O projeto esta em um ponto perigoso: ja tem muitas funcionalidades de plataforma, mas a fundacao tecnica ainda parece de MVP expandido. Ha sinais claros de "feature creep": CRM, rituais, pagamentos, admin, automacoes, LGPD, IA, cupons e relatorios foram acoplados em poucos arquivos gigantes. Isso gera risco alto de bugs regressivos, dificuldade de escalar equipe, riscos de seguranca e custo operacional crescente.

O maior problema nao e falta de funcionalidades. E excesso de funcionalidades antes de consolidar arquitetura, seguranca, jornadas e operacao.

## Achados criticos

### 1. Arquitetura

- `api.py` tem mais de 3.200 linhas e mistura rotas, auth, regras de negocio, CRM, pagamentos, webhooks, admin, serializacao e helpers.
- `tools/db_client.py` tem mais de 1.400 linhas e concentra acesso a dados, regras financeiras, auth e operacoes administrativas.
- `frontend/app.js` e `frontend/admin.js` passam de 1.000 linhas cada e misturam estado, API client, renderizacao, UX, validacao e regras.
- Nao existe separacao real por dominios: auth, billing, readings, automation, CRM, admin e notification vivem no mesmo eixo.
- Nao ha camada clara de application services/use cases, repositories tipados, DTOs de resposta, controllers separados ou contratos por modulo.
- A habilidade Ruflo DDD nao se aplica diretamente porque nao existe estrutura `src/*/domain/`.

Mudanca recomendada:

- Criar estrutura modular:
  - `app/main.py`
  - `app/core/config.py`
  - `app/core/security.py`
  - `app/modules/auth`
  - `app/modules/readings`
  - `app/modules/billing`
  - `app/modules/automation`
  - `app/modules/notifications`
  - `app/modules/admin`
  - `app/modules/crm`
  - `app/modules/rituals`
  - `app/infra/supabase`
  - `app/infra/queue`
  - `app/shared`
- Extrair use cases: `CreateReading`, `CreatePixPayment`, `ProcessWebhook`, `SendNotification`, `ClassifyCustomer`.
- Adotar contratos Pydantic separados por modulo, com validadores fortes e respostas tipadas.

### 2. Banco de Dados

- Schema consolidado tem muitas tabelas, mas mistura `CREATE TABLE` com varios `ALTER TABLE`, parecendo historico colado e nao uma migration limpa.
- RLS aparece em migration parcial, mas nao ha politica completa no schema consolidado para todas as tabelas sensiveis.
- `users` concentra auth, perfil, consentimentos, assinatura, creditos e marketing; isso aumenta risco e acoplamento.
- `payments` mistura campos legados e novos: `valor`, `amount`, `tipo`, `product_type`, `gateway_ref`, `transaction_id`, `gateway_payload`.
- Falta estrategia explicita de idempotencia forte para compras, consumo de creditos, webhooks e reprocessamentos.
- Falta particionamento/retencao para logs, audit logs, notification logs e message events.
- Filtros via string Supabase REST aumentam risco de bugs e dificultam evolucao.

Mudanca recomendada:

- Criar migrations versionadas reais, uma por alteracao.
- Separar `user_profiles`, `user_consents`, `wallets`, `wallet_transactions`, `subscriptions`.
- Padronizar pagamentos: `payments`, `payment_events`, `payment_products`, `payment_entitlements`.
- Adicionar RLS/policies completas ou garantir uso exclusivo de service role no backend sem expor tabelas.
- Criar indices compostos para consultas reais: `(user_id, created_at)`, `(status, scheduled_at)`, `(gateway, transaction_id)`, `(user_id, status, created_at)`.
- Implementar tabela de idempotencia: `idempotency_keys`.

### 3. Backend

- Rate limit em memoria quebra em multiplas instancias e e perdido em restart.
- JWT e implementado manualmente; melhor usar biblioteca consolidada.
- Tokens ficam stateless sem revogacao real.
- Admin pode depender de `ADMIN_EMAILS` e `ADMIN_DIRECT_ACCESS`; isso e arriscado se vazar para ambiente errado.
- Muitos endpoints aceitam `str`, `float` e `dict` amplos demais.
- Falta OpenAPI organizado por tags/modulos.
- Chamadas Supabase sao sincronas (`requests`) dentro de endpoints async, bloqueando event loop.
- Falta fila robusta para leituras IA e notificacoes.
- Health detalhado consulta sistemas externos e pode ficar lento.

Mudanca recomendada:

- Migrar para `httpx.AsyncClient` ou camada sync isolada em threadpool.
- Usar Redis para rate limit, locks, filas e cache.
- Usar JWT via biblioteca (`python-jose`, `PyJWT`) com `jti`, revogacao e refresh token.
- Remover `ADMIN_DIRECT_ACCESS`.
- Validar rigorosamente modelos com `EmailStr`, `HttpUrl`, enums e constraints.
- Criar endpoints separados de health: `live`, `ready`, `deep`.

### 4. Frontend

- Frontend vanilla ficou grande demais para a complexidade atual.
- 33 riscos Ruflo MEDIUM de XSS por `innerHTML`.
- Token JWT em `localStorage` aumenta impacto de XSS.
- Hero tem duplicacao de conteudo e muito peso visual.
- Arquivos JS/CSS enormes sem componentizacao.
- Links hardcoded para `http://localhost:8000/admin.html`.
- UX depende de muitas secoes na mesma pagina, com risco de abandono e lentidao.
- Acessibilidade e SEO sao parciais.

Mudanca recomendada:

- Migrar para Next.js/React/TypeScript ou ao menos modularizar vanilla em componentes.
- Trocar renderizacao por DOM seguro, templates sanitizados ou biblioteca com escaping.
- Mover auth para cookie HttpOnly/SameSite.
- Criar design system pequeno: Button, Input, Modal, Table, Toast, Card, Tabs, EmptyState.
- Dividir app em rotas: landing, login, dashboard, leitura, pagamentos, perfil, rituais.

### 5. Experiencia do Usuario

Pontos de abandono provaveis:

- Primeiro impacto visual pesado e longo demais antes do valor principal.
- Usuario precisa entender creditos, leitura gratis, planos, rituais e IA ao mesmo tempo.
- Fluxo de pagamento depende de PIX/webhook externo ainda nao plenamente provado em producao.
- Se IA demora, nao ha fila/status assinc robusto.
- Se WhatsApp falha, o usuario perde parte importante da promessa de relacionamento.
- Perfil/admin/creditos/rituais podem parecer complexos demais para usuario B2C inicial.

Mudanca recomendada:

- Reduzir TTV: cadastro -> pergunta -> primeira leitura -> resultado -> proximo passo.
- Deixar creditos/rituais/assinatura depois da primeira entrega de valor.
- Criar onboarding de 3 passos.
- Criar estado claro de "estamos gerando sua leitura" com retry e historico.

### 6. Produto

Remover/suspender temporariamente:

- Marketplace complexo de rituais ate validar core.
- CRM avancado antes de eventos de analytics confiaveis.
- Multiplos modelos de monetizacao simultaneos.
- Admin muito amplo antes de permissoes granularizadas.

Simplificar:

- Uma oferta principal: leitura avulsa + assinatura mensal.
- Uma jornada principal: pergunta -> leitura -> historico -> upgrade.
- Automacoes essenciais: boas-vindas, carrinho abandonado, pos-leitura.

Adicionar:

- Experimentos A/B.
- NPS/feedback depois da leitura.
- Painel de funil real.
- Recomendacao personalizada baseada no historico.

### 7. Performance

Gargalos provaveis:

- Arquivos estaticos grandes e video hero local.
- Chamadas sincronas para Supabase e IA dentro de endpoints async.
- Admin carrega varios blocos e listas por endpoint sem paginacao cursor-based.
- Logs e relatorios podem ficar lentos com volume.
- Rate limiter em memoria pode crescer sem limite por path/IP.

Mudanca recomendada:

- CDN para imagens/video.
- Lazy loading e compressao de assets.
- Filas para IA/notificacoes.
- Cache Redis para settings, planos, rituais e status.
- Paginar por cursor.

### 8. Seguranca

Riscos identificados:

- Senha admin real documentada em `acesso_sistema.md`.
- JWT em `localStorage`.
- XSS por `innerHTML`.
- `ADMIN_DIRECT_ACCESS` existe.
- Service role/Supabase key usada no backend via REST; precisa garantir que nunca va ao frontend.
- Falta 2FA implementado de fato.
- RLS/policies incompletas no schema consolidado.
- Rate limit em memoria nao protege multi-instancia.
- Falta CSP, security headers e politica de cookies.
- Dados sensiveis de leituras podem ser PII emocional/espiritual e exigem cuidado LGPD.

Mudanca recomendada imediata:

- Rotacionar senha admin exposta.
- Remover senha real dos docs.
- Migrar token para cookie HttpOnly.
- Corrigir todos os `innerHTML` com dados dinamicos.
- Remover `ADMIN_DIRECT_ACCESS`.
- Criar CSP restritiva.
- Implementar 2FA admin.

### 9. Escalabilidade

Capacidade estimada:

- 100 usuarios: suporta localmente se IA e Supabase estiverem estaveis.
- 1.000 usuarios: comeca a sofrer em IA sincrona, admin, logs, notificacoes e rate limit em memoria.
- 10.000 usuarios: quebra sem filas, cache, CDN, workers e particionamento de logs.
- 100.000 usuarios: modelo atual nao e adequado.
- 1 milhao: precisa re-arquitetura completa, multi-worker, observabilidade, idempotencia, event bus e custos de IA controlados.

Quebra primeiro:

1. IA sincrona.
2. Notificacoes/WhatsApp.
3. Logs e consultas admin.
4. Assets pesados.
5. Rate limit e estado em memoria.
6. Operacoes financeiras sem idempotencia forte.

### 10. Custos

Riscos de custo:

- IA por leitura sem orcamento por usuario.
- Video/imagens locais sem CDN.
- WhatsApp com retry mal controlado.
- Logs crescendo sem retencao.
- Admin/health fazendo consultas externas repetidas.

Mudanca recomendada:

- Registrar custo real por leitura.
- Criar limite diario por usuario/plano.
- Usar cache para prompts e configuracoes.
- Retencao/arquivamento de logs.
- Dashboard de custo por canal.

### 11. Automacoes

Automacoes que devem existir com fila e idempotencia:

- Boas-vindas.
- Pos-leitura 24h/3d/7d/30d.
- Carrinho abandonado.
- Pagamento aprovado.
- Pagamento expirado.
- Reativacao.
- Recompra.
- Aniversario de cadastro.
- Pedido de feedback.
- Relatorio diario admin.
- Reprocessamento de webhook.

Mudanca recomendada:

- Trocar loop infinito simples por worker com fila: Redis/RQ, Celery, Dramatiq ou APScheduler + locks.
- Guardar idempotency key por automacao.
- Criar painel de tentativas e dead-letter queue.

### 12. Inteligencia Artificial

Melhorias:

- Guardrails de conteudo para evitar aconselhamento medico/legal/financeiro perigoso.
- Memoria por usuario com consentimento.
- Classificacao automatica de tema/emocao/intencao.
- Recomendacao de proximo ritual/leitura.
- Resumo de historico.
- Moderacao de input.
- Avaliacao automatica de qualidade das respostas.
- Cache semantico de leituras comuns.

Risco:

- IA hoje parece parte essencial do endpoint sincrono. Se falha, a jornada principal falha.

### 13. Painel Administrativo

Problemas:

- Permissao admin ainda e ampla: `admin` e `super_admin`, sem RBAC granular por acao.
- Aprovacao manual de pagamento e poderosa demais sem 2FA/dual control.
- Logs e auditoria existem, mas precisam ser imutaveis e pesquisaveis.
- Falta filtro avancado, exportacao controlada e mascaramento de PII.
- Falta trilha de "quem viu dados sensiveis".

Mudanca recomendada:

- RBAC por permissao: `payments.approve`, `users.block`, `prompts.edit`, `logs.view`, `exports.create`.
- 2FA obrigatorio para admins.
- Reautenticacao para acoes financeiras.
- Exportacao assinc com auditoria.

### 14. Analytics essenciais

Eventos obrigatorios:

- `page_view`
- `signup_started`
- `signup_completed`
- `login_success`
- `login_failed`
- `onboarding_started`
- `onboarding_completed`
- `daily_card_started`
- `daily_card_completed`
- `reading_started`
- `reading_ai_started`
- `reading_ai_failed`
- `reading_completed`
- `credits_insufficient`
- `checkout_started`
- `checkout_pix_generated`
- `payment_approved`
- `payment_failed`
- `payment_abandoned`
- `subscription_started`
- `subscription_cancel_requested`
- `subscription_cancelled`
- `ritual_viewed`
- `ritual_purchased`
- `coupon_applied`
- `coupon_failed`
- `profile_updated`
- `whatsapp_opt_in`
- `whatsapp_opt_out`
- `email_opt_in`
- `automation_sent`
- `automation_failed`
- `admin_login`
- `admin_payment_manual_approved`
- `admin_export_created`
- `api_error`
- `xss_blocked`
- `rate_limited`

### 15. Monetizacao

Problemas:

- Oferta complexa: creditos, leitura avulsa, assinatura, ritual, upsell, downsell.
- Sem tracking confiavel de CAC/LTV/churn.
- Retencao depende de WhatsApp, que esta falhando.
- Assinatura precisa provar valor recorrente alem da primeira leitura.

Mudanca recomendada:

- Validar primeiro: leitura avulsa + assinatura simples.
- Criar cohort retention.
- Criar motivos de cancelamento.
- Criar lifecycle de assinatura.
- Medir conversao por etapa.

### 16. Codigo

Debitos:

- Arquivos gigantes.
- Duplicacao de endpoints alias.
- Funcoes com muitas responsabilidades.
- Muitos `except Exception` silenciosos.
- Strings de filtros REST montadas manualmente.
- Testes integrados misturados com producao e dados reais.
- Dependencias antigas no `requirements.txt` vs ambiente instalado mais novo.
- Documentacao com encoding quebrado e senha exposta.

### 17. Checklist de bugs provaveis

- XSS em listas do admin/perfil/rituais.
- Token roubavel via XSS.
- Rate limit ineficaz em deploy multi-instancia.
- Corrida em primeira leitura gratis se duas chamadas simultaneas ocorrerem.
- Corrida em compra de ritual com creditos.
- Webhook duplicado pode liberar credito se idempotencia falhar.
- Filtros Supabase quebram com caracteres especiais.
- `tema` e outros filtros nao escapados podem gerar query REST incorreta.
- Admin direct local pode vazar por configuracao errada.
- `Invoke-WebRequest` falhou para frontend por comportamento PowerShell; precisa teste Playwright real.
- WhatsApp configurado mas endpoint 404.
- Predeploy acusa producao bloqueada.
- Logs podem crescer sem limite.
- Hero duplicado pode quebrar responsividade.
- Links hardcoded localhost em frontend.
- JWT nao tem revogacao apos logout.
- Reset token depende de implementacao em DB; precisa validar expiracao/uso unico com teste adversarial.
- Pydantic usa `str` demais; emails/URLs/status invalidos podem passar.
- Admin approval de pagamento sem 2FA/dual control.
- Falta CSP permite XSS explorar localStorage.

## Priorizacao

### Vermelho - Critico

- Rotacionar senha admin e remover segredo dos docs.
- Corrigir XSS por `innerHTML`.
- Migrar JWT de localStorage para cookie HttpOnly.
- Remover `ADMIN_DIRECT_ACCESS`.
- Corrigir WhatsApp endpoint 404.
- Implementar idempotencia real para pagamento, webhook, credito e ritual.
- Separar backend em modulos antes de adicionar novas features.
- Criar fila para IA/notificacoes.

### Laranja - Importante

- RBAC granular e 2FA admin.
- Redis rate limit/cache.
- Migrations versionadas e RLS/policies completas.
- Refatorar `api.py` e `db_client.py`.
- Substituir chamadas sync bloqueantes ou isolar.
- CDN e otimizacao de assets.
- Analytics de funil.

### Amarelo - Medio

- Design system.
- Testes Playwright.
- Testes unitarios por dominio.
- SEO e acessibilidade.
- Documentacao limpa sem encoding quebrado.
- Paginacao cursor-based.

### Verde - Futuro

- Recomendacao IA avancada.
- Agentes de retencao.
- A/B testing sofisticado.
- Marketplace de rituais expandido.
- Multi-tenant B2B.

## Roadmap tecnico

### Sprint 1 - Seguranca e venda segura

- Rotacionar credenciais expostas.
- Remover senha de `acesso_sistema.md`.
- Corrigir todos os `innerHTML` dinamicos.
- Adicionar CSP e headers.
- Remover/desabilitar `ADMIN_DIRECT_ACCESS`.
- Corrigir WhatsApp.
- Criar teste de regressao para XSS/auth.

### Sprint 2 - Fundacao backend

- Criar estrutura modular.
- Extrair auth, readings, billing, admin, notifications.
- Criar camada de repositories.
- Trocar filtros string por builders seguros.
- Padronizar erros/respostas.
- Criar testes de use cases.

### Sprint 3 - Pagamentos e idempotencia

- Criar `idempotency_keys`.
- Reestruturar payments/events/entitlements.
- Validar webhook Mercado Pago ponta a ponta.
- Criar locks para consumo/liberacao de creditos.
- Reautenticacao/2FA para aprovacao manual.

### Sprint 4 - Filas, automacoes e observabilidade

- Redis + worker.
- Dead-letter queue.
- Jobs para IA e notificacoes.
- Dashboard de jobs.
- Metricas Prometheus/OpenTelemetry ou equivalente.
- Retencao de logs.

### Sprint 5 - Produto, UX e escala

- Simplificar jornada principal.
- Implementar analytics de funil.
- Refatorar frontend para componentes.
- Otimizar assets/CDN.
- Criar experimentos de monetizacao.
- Rodar teste de carga e plano de capacidade.

## Notas finais por area

| Area | Nota |
|---|---:|
| Arquitetura | 3/10 |
| Codigo | 4/10 |
| UX | 5/10 |
| UI | 6/10 |
| Performance | 4/10 |
| Seguranca | 3/10 |
| Escalabilidade | 3/10 |
| Produto | 5/10 |
| Banco de Dados | 5/10 |
| Backend | 5/10 |
| Frontend | 4/10 |
| Monetizacao | 5/10 |
| Retencao | 4/10 |
| Manutenibilidade | 3/10 |

## Tabela de problemas

| Problema | Impacto | Prioridade | Solucao | Tempo estimado | Dificuldade |
|---|---|---|---|---:|---|
| Senha admin em documentacao | Comprometimento imediato | Critico | Remover doc e rotacionar credencial | 1h | Baixa |
| XSS por `innerHTML` | Roubo de JWT/admin | Critico | Render seguro + CSP | 1-2 dias | Media |
| JWT em localStorage | Sessao roubavel | Critico | Cookie HttpOnly/SameSite | 1-2 dias | Media |
| `ADMIN_DIRECT_ACCESS` | Bypass por config errada | Critico | Remover ou travar em build local | 2h | Baixa |
| WhatsApp 404 | Retencao quebrada | Critico | Corrigir provider/rota/check | 2-6h | Media |
| Pagamento sem idempotencia completa | Credito duplicado/perda financeira | Critico | Idempotency keys + locks | 2-4 dias | Alta |
| `api.py` monolitico | Regressao constante | Critico | Modularizar por dominio | 5-10 dias | Alta |
| `db_client.py` monolitico | Bugs em dados | Importante | Repositories tipados | 5-8 dias | Alta |
| Rate limit em memoria | Nao escala | Importante | Redis rate limiter | 1 dia | Media |
| Chamadas sync em async | Lentidao sob carga | Importante | httpx async/threadpool | 2-4 dias | Media |
| RLS incompleto | Vazamento por config | Importante | Policies por tabela | 2-4 dias | Alta |
| Assets grandes locais | LCP ruim/custo | Importante | CDN + compressao | 1-2 dias | Media |
| Admin sem RBAC granular | Abuso interno | Importante | Permissoes por acao | 3-5 dias | Alta |
| Aprovacao manual sem 2FA | Fraude operacional | Importante | 2FA + reauth | 2-4 dias | Media |
| Logs sem retencao | Custo/performance | Medio | Retencao e arquivamento | 1-2 dias | Media |
| Frontend sem componentes | Baixa produtividade | Medio | Componentizacao/React | 5-10 dias | Alta |
| Oferta complexa demais | Abandono | Medio | Simplificar monetizacao | 1-3 dias | Media |
| Analytics insuficiente | Decisao no escuro | Medio | Taxonomia de eventos | 2-5 dias | Media |
| Testes insuficientes | Bugs regressivos | Medio | Unit/API/Playwright | 3-8 dias | Media |

## As 10 mudancas que mais aumentariam a qualidade deste projeto

1. Corrigir XSS e remover JWT do localStorage.
2. Rotacionar senha admin e remover segredos de docs.
3. Modularizar o backend por dominios.
4. Criar idempotencia forte para pagamentos, webhooks e creditos.
5. Implementar fila real para IA e notificacoes.
6. Remover `ADMIN_DIRECT_ACCESS` e criar RBAC + 2FA admin.
7. Refatorar banco para separar perfil, consentimentos, carteira e pagamentos.
8. Corrigir WhatsApp e criar painel de automacoes com dead-letter queue.
9. Simplificar a jornada principal e a monetizacao inicial.
10. Implantar analytics, observabilidade, testes automatizados e deploy gate real.

## Checklist de continuidade

- [ ] Rotacionar senha admin exposta.
- [ ] Remover credencial real de `acesso_sistema.md`.
- [ ] Rodar novo Ruflo security scan apos correcoes.
- [ ] Corrigir todos os `innerHTML` dinamicos em `frontend/admin.js`.
- [ ] Corrigir todos os `innerHTML` dinamicos em `frontend/app.js`.
- [ ] Adicionar CSP e security headers.
- [ ] Migrar auth para cookie HttpOnly.
- [ ] Remover `ADMIN_DIRECT_ACCESS`.
- [ ] Corrigir endpoint WhatsApp 404 e validar envio real com cuidado.
- [ ] Criar tabela `idempotency_keys`.
- [ ] Blindar webhooks Mercado Pago com idempotencia e assinatura.
- [ ] Blindar consumo/liberacao de creditos com locks transacionais.
- [ ] Criar estrutura modular do backend.
- [ ] Extrair modulo `auth`.
- [ ] Extrair modulo `readings`.
- [ ] Extrair modulo `billing`.
- [ ] Extrair modulo `notifications`.
- [ ] Extrair modulo `admin`.
- [ ] Trocar rate limit em memoria por Redis.
- [ ] Colocar IA e notificacoes em fila.
- [ ] Criar dead-letter queue.
- [ ] Criar analytics de funil.
- [ ] Otimizar assets e mover para CDN.
- [ ] Criar testes API.
- [ ] Criar testes Playwright da jornada principal.
- [ ] Criar checklist final de venda publica.

