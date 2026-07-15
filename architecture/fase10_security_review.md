# Revisao de Seguranca - Fase 10

## CORS

O backend agora valida `APP_CORS_ORIGINS` quando `APP_ENV=production`.

Para producao, configurar apenas dominios reais HTTPS, por exemplo:

```env
APP_ENV=production
APP_CORS_ORIGINS=https://madamedoluar.com.br,https://www.madamedoluar.com.br
```

Nao usar `*`, `null`, `localhost` ou `127.0.0.1` em producao.

## Segredo JWT

`JWT_SECRET` e obrigatorio no `.env` e precisa ter pelo menos 32 caracteres. O backend nao usa mais `SUPABASE_KEY` nem segredo aleatorio temporario como fallback.

## Exposicao de chaves

Arquivos estaticos do frontend nao devem conter chaves secretas. Chaves privadas ficam somente no `.env` do servidor.

Itens verificados nesta fase:

- `MERCADO_PAGO_ACCESS_TOKEN` permanece somente no backend.
- `SUPABASE_KEY` permanece somente no backend.
- `OPENAI_API_KEY` e `GEMINI_API_KEY` permanecem somente no backend.
- `MERCADO_PAGO_PUBLIC_KEY` pode ser publica, mas o fluxo atual usa checkout criado no backend.

## Supabase Data API

Para tabelas expostas pela API REST, manter RLS habilitado e conceder o minimo de privilegios. O backend atual usa a chave configurada no servidor, mas a politica de defesa em profundidade deve ser mantida no banco.

## Pendencias operacionais

- Aplicar `architecture/migration_fase10_lgpd_security.sql`.
- Rodar advisors/checagens de seguranca do Supabase quando CLI/MCP autenticado estiver disponivel.
- Validar backup e restore em banco isolado.
