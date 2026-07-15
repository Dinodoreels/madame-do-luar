# Fase 4 - Mapa de modularizacao

## Estado aplicado

- `app/core/config.py`: settings, paths, CORS, JWT e limites.
- `app/core/security.py`: cookie auth, JWT, usuario atual e admin atual.
- `app/core/errors.py`: payload de erro padronizado e classificacao operacional.
- `app/core/context.py`: contexto de request e limpeza de payload Pydantic.
- `app/modules/*`: namespaces criados para extracao incremental dos routers.
- `app/modules/auth`: cadastro, login, logout e recuperacao de senha extraidos.
- `app/modules/users`: perfil, LGPD, preferencias de contato, creditos, leituras e pagamentos do usuario extraidos.
- `app/modules/readings`: carta do dia, leitura, historico e detalhe extraidos.
- `app/modules/payments`: PIX, checkout, status e cancelamento de assinatura extraidos.
- `app/modules/webhooks`: PIX, Mercado Pago e Stripe legado extraidos.
- `app/modules/rituals`: catalogo publico, compra por creditos e ofertas pos-leitura extraidos.
- `app/modules/admin`: painel operacional, financeiro, conteudo, configuracoes, alertas e relatorios extraidos.
- `app/modules/crm`: visao CRM, tags, segmentos, notas, gatilhos e exportacao CSV extraidos.
- `app/shared/repository.py`: base comum para repositories com operacoes REST/Supabase padronizadas.
- `app/modules/*/repository.py`: fronteira de persistencia criada para todos os modulos.
- `app/modules/*/use_cases.py`: fronteira de use cases criada para todos os modulos.

## Ordem segura para as proximas extracoes

1. `notifications`: email, WhatsApp, preferencias e logs de envio.
2. `automation`: eventos, campanhas, agendamentos e workers.
3. `analytics`: eventos de funil, conversao, abandono e retencao.
4. `billing`: separar operacoes financeiras admin de pagamentos publicos.
5. `admin`: quebrar o router atual em subrouters `users`, `billing`, `ops`, `content`, `reports` e `settings`.

## Regra de migracao

Cada extracao deve mover nesta ordem:

1. schemas Pydantic do dominio;
2. funcoes auxiliares do dominio;
3. repository do dominio;
4. service/use case;
5. router FastAPI;
6. `app.include_router(...)` no bootstrap.

Nao mover regras financeiras para controller. Pagamentos, creditos e webhooks devem chamar services/RPCs idempotentes.

## Regra atual de dependencia

Routers devem depender de `service.py` ou `use_cases.py` para regra de negocio.
Services/use cases devem depender de `repository.py` para persistencia.
Repositories sao o unico ponto aceito para acesso direto recorrente a `db_client`, exceto durante extracoes incrementais documentadas.
