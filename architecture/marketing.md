# POP — Marketing e Onboarding

**Objetivo:**
Converter usuários da funcionalidade gratuita (Carta do Dia) em assinantes e vender rituais pagos, além de acolher o usuário nas primeiras interações com a Madame do Luar.

**Entradas:**
(Processo baseado em triggers e na tabela `marketing_sequences`)

**Processo:**
1. **Onboarding:** Assim que um usuário se cadastra (`users.criado_em`), iniciar a sequência de boas-vindas. Inserir eventos na tabela `message_events` ou `marketing_sequences`.
2. **Regras de Upsell (Conversão):**
   - **Gatilho:** O usuário pede uma leitura de 3 cartas mas não possui acesso.
   - **Ação:** Apresentar a assinatura mensal (Plano Oráculo) ou pagamento avulso. Usar o estilo definido em `prompts/marketing.md`.
3. **Nutrição:** Usuários que consomem a "Carta do Dia" recorrentemente por 7 dias seguidos recebem um convite místico automático para assinar a plataforma.
4. **Reativação:** Assinaturas canceladas ou expiradas disparam uma mensagem de acolhimento (ex: "A Lua sentiu sua ausência..."), com oferta de retorno (downsell ou desconto).

**Casos de Borda:**
- **Assinante Ativo:** Nunca enviar ofertas de assinatura para quem já possui a tag `assinante = true`. Focar apenas na venda de novos rituais.
- **Tom de Voz:** Garantir que o marketing não soe agressivo ou financeiro, mantendo o linguajar etéreo e ancestral.
