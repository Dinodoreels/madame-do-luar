# POP — Retorno Automático (Follow-up)

**Objetivo:**
Manter o usuário engajado e ativo enviando mensagens automáticas após a realização de uma pergunta/leitura. Os disparos ocorrem em 24 horas, 3 dias, 7 dias ou 30 dias.

**Entradas:**
(Processo autônomo baseado na tabela `message_events`)

**Processo:**
1. **Cronjob / Scheduler:** Um script roda a cada X horas verificando a tabela `message_events`.
2. **Filtro:** Buscar registros onde `status = pending` e `agendado_para <= data/hora_atual`.
3. **Preparo do Conteúdo:**
   - Obter a `pergunta_anterior` acessando a tabela `questions` (via `question_id` do evento).
   - Injetar a pergunta no prompt base localizado em `prompts/retorno_24h.md`.
4. **Geração via IA:** Chamar a IA para gerar a mensagem cerimonial e poética de convite ao retorno.
5. **Disparo:** Enviar a mensagem gerada através da API correspondente (`canal` = whatsapp ou email).
6. **Atualização de Status:**
   - Se sucesso: alterar `status` para `sent` e preencher `enviado_em`.
   - Opcionalmente, criar um novo agendamento para o próximo marco (ex: se era o evento de 24h, criar o evento de 3d).
   - Se falha: registrar no log e manter `pending` para retentativa (com limite).

**Casos de Borda:**
- **Múltiplos disparos pendentes:** Se o usuário fez várias perguntas, priorizar a mais recente ou agregar as energias, para não enviar spam.
- **Cancelamento/Unsubscribe:** Se o usuário solicitar parar de receber, inativar todos os eventos vinculados a ele na tabela `message_events`.
