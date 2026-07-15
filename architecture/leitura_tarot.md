# POP — Leitura de Tarot (3 Cartas)

**Objetivo:**
Realizar uma tiragem tradicional de 3 cartas (passado, presente, futuro) baseada na pergunta do consulente. Validar se o usuário possui acesso (gratuito, assinatura ou avulso), sortear as cartas, invocar a IA e persistir a resposta.

**Entradas:**
| parâmetro | tipo | descrição |
| --- | --- | --- |
| `user_id` | UUID | Identificador do usuário |
| `pergunta` | texto | A pergunta enviada pelo usuário |
| `tema` | texto | (Opcional) Tema detectado da pergunta |

**Processo:**
1. **Validação de Acesso:**
   - Checar tabela `users` (`primeira_tiragem_gratis`). Se `true`, permitir e alterar para `false`.
   - Caso contrário, checar `subscriptions` (`status = ativo`). Se `true`, permitir.
   - Caso contrário, checar `payments` para uma compra avulsa válida não utilizada. Se não houver, bloquear e ofertar pagamento/assinatura.
2. **Registro da Pergunta:** Inserir a entrada na tabela `questions`. Guardar o `question_id`.
3. **Sorteio:** Executar `tools/sortear_3_cartas.py` para escolher 3 cartas únicas e definir para cada uma o status `invertida` (booleano).
4. **Montagem do Payload:** Preparar JSON no formato esperado pela IA contendo a pergunta, os nomes das três cartas e suas posições (normal/invertida).
5. **Chamada da IA:** Enviar o payload juntamente com o system prompt `prompts/tres_cartas.md`.
6. **Persistência da Leitura:** Salvar na tabela `readings` (vinculando ao `question_id`) as cartas tiradas, a interpretação completa, conselho e mini-ritual.
7. **Agendamento de Retorno:** (Opcional) Agendar um evento na tabela `message_events` para 24h depois, convidando o consulente a refletir sobre a leitura.
8. **Entrega:** Retornar a leitura formatada e com formatação de UI ou Markdown para o consulente.

**Casos de Borda:**
- **Timeout da IA:** Se a resposta demorar ou falhar, exibir mensagem amigável e tentar novamente (até 3 vezes).
- **Sem saldo/acesso:** Direcionar o usuário imediatamente para o funil de vendas, garantindo que a pergunta dele não seja perdida (salvar em `questions` com status "pendente de pagamento").
