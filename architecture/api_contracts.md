# Contratos principais da API

Este documento define o formato que o frontend deve usar para distinguir sucesso,
falha de validacao, falha operacional e indisponibilidade temporaria.

## Erros padronizados

Toda falha controlada retorna HTTP status coerente e corpo JSON neste formato:

```json
{
  "success": false,
  "status": "error",
  "detail": "Mensagem legivel para o frontend",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Mensagem legivel para o frontend",
    "status_code": 422,
    "details": {},
    "request_id": "uuid"
  }
}
```

Campos importantes:

- `detail`: mantido por compatibilidade com o frontend existente.
- `error.code`: codigo estavel para a UI decidir comportamento.
- `error.message`: mensagem segura para exibicao.
- `error.status_code`: mesmo status HTTP da resposta.
- `error.details`: campos invalidos, IDs relacionados ou contexto operacional.
- `error.request_id`: identificador para correlacionar log e suporte.

Codigos relevantes:

- `VALIDATION_ERROR`: payload invalido, campo ausente, tipo incorreto ou campo extra.
- `UNAUTHORIZED`: sessao ausente, invalida ou expirada.
- `FORBIDDEN`: usuario bloqueado ou acesso administrativo negado.
- `PAYMENT_REQUIRED`: saldo insuficiente para leitura.
- `AI_UNAVAILABLE`: IA indisponivel na carta do dia.
- `AI_READING_FAILED`: IA falhou durante leitura; credito preservado ou estornado.
- `MAINTENANCE_MODE`: operacao temporariamente indisponivel.
- `RATE_LIMITED`: excesso de requisicoes.
- `LEGACY_ENDPOINT_DISABLED`: endpoint antigo desativado.
- `SERVICE_UNAVAILABLE`: dependencia externa indisponivel.
- `INTERNAL_ERROR`: falha inesperada.

## Payloads invalidos

Os modelos de entrada rejeitam campos extras. Isso evita que o frontend envie
payloads silenciosamente ignorados.

Exemplo de campo extra:

```json
{
  "pergunta": "O que preciso compreender agora?",
  "campo_inexistente": true
}
```

Resposta esperada: `422 VALIDATION_ERROR`.

## Auth

### POST `/api/auth/registrar`

Entrada:

```json
{
  "nome": "Cliente",
  "email": "cliente@email.com",
  "senha": "senha-segura",
  "whatsapp": "11999999999"
}
```

Sucesso:

```json
{
  "usuario": {},
  "token_type": "bearer",
  "expires_in": 86400,
  "mensagem": "Conta criada com sucesso!"
}
```

Observacao de seguranca: o token de sessao e enviado apenas por cookie `HttpOnly` (`mdl_access_token`). O JWT nao deve ser lido nem armazenado pelo JavaScript do frontend.

### POST `/api/auth/login`

Entrada:

```json
{
  "email": "cliente@email.com",
  "senha": "senha-segura"
}
```

Sucesso: mesmo formato de autenticacao, sem `mensagem`, com cookie `HttpOnly`.

## Leituras

### POST `/api/carta-do-dia`

Requer cookie de sessao `mdl_access_token`. Clientes legados de API ainda podem enviar `Authorization: Bearer <token>` quando explicitamente autorizado.

Entrada aceita: `{}`.

Sucesso:

```json
{
  "carta": "A Lua",
  "invertida": false,
  "simbolo": "&#9790;",
  "mensagem": "texto gerado pela IA",
  "ja_tirou": false
}
```

Se a IA falhar, nao ha mock silencioso. A API retorna `503 AI_UNAVAILABLE`.

### POST `/api/leitura`

Requer `Authorization: Bearer <token>`.

Entrada:

```json
{
  "pergunta": "O que preciso entender sobre meu momento amoroso?",
  "tipo": "tres_cartas"
}
```

Regras de validacao:

- `pergunta` obrigatoria.
- Minimo configuravel por `MIN_TAROT_QUESTION_LENGTH`, padrao `3`.
- Maximo configuravel por `MAX_TAROT_QUESTION_LENGTH`, padrao `600`.
- Deve conter texto legivel com pelo menos uma letra.

Sucesso:

```json
{
  "cartas": [],
  "interpretacao": "texto gerado pela IA",
  "question_id": "uuid",
  "reading_id": "uuid",
  "creditos": {
    "cobrados": 3,
    "primeira_gratis": false,
    "saldo_atual": 7
  }
}
```

Falhas relevantes:

- `402 PAYMENT_REQUIRED`: creditos insuficientes.
- `503 AI_READING_FAILED`: IA falhou; credito preservado ou estornado.

## Pagamentos PIX

### POST `/api/payments/pix/create`

Requer `Authorization: Bearer <token>`.

Entrada:

```json
{
  "product_type": "package",
  "product_id": "uuid",
  "coupon_code": "LUA10"
}
```

Sucesso:

```json
{
  "payment_id": "uuid",
  "status": "pending",
  "gateway": "mercado_pago",
  "transaction_id": "gateway-id",
  "qr_code_url": "url",
  "pix_copy_paste": "codigo",
  "checkout_url": "url",
  "expires_at": "iso-date",
  "credits_to_release": 10,
  "amount": 49.9
}
```

Falhas relevantes:

- `400 PAYMENT_PRODUCT_INVALID`: produto, plano ou pacote invalido.
- `502 BAD_GATEWAY`: gateway nao conseguiu gerar cobranca.

## Endpoint legado

### POST `/api/cadastro`

Status: desativado.

Resposta esperada: `410 LEGACY_ENDPOINT_DISABLED`.

Fluxo atual: usar `/api/auth/registrar` e depois `/api/checkout` ou
`/api/payments/pix/create`, sempre autenticado.
