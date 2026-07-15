# POP — Carta do Dia

**Objetivo:**
Entregar ao usuário uma carta diária gratuita do tarot, oferecendo uma mensagem breve sobre a
energia do dia, uma orientação prática e um mini‑ritual simples. O sistema deve impedir múltiplas
cartas no mesmo dia para o mesmo usuário.

**Entradas:**
| parâmetro | tipo | descrição |
| --- | --- | --- |
| `user_id` | UUID | Identificador do usuário |
| `data_hoje` | date | Data atual (respeitando o fuso horário) |

**Processo:**
1. **Verificação de elegibilidade:** consultar `daily_cards` para verificar se já existe uma carta para `user_id` na data atual. Se existir, não sortear novamente; retornar a mensagem existente.
2. **Seleção de carta:** chamar `tools/sortear_1_carta.py` para sortear aleatoriamente uma carta do baralho. Definir aleatoriamente se ela está invertida.
3. **Montagem do payload:** construir objeto JSON com:
   - `carta` (nome);
   - `invertida` (booleano).
4. **Chamada da IA:** enviar o payload e o conteúdo de `prompts/carta_do_dia.md` para a API de IA. A resposta deve conter 5–7 linhas: explicação da energia, o que observar, o que evitar, uma orientação prática e um mini‑ritual.
5. **Persistência:** salvar o registro em `daily_cards` com o nome da carta, orientação invertida, mensagem gerada, nível de energia e data. O campo `criado_em` deve registrar apenas a data (sem hora) para impedir duplicidade.
6. **Resposta ao usuário:** formatar a mensagem para o canal apropriado (UI, WhatsApp ou e‑mail). Incluir link ou sugestão de leitura completa (tiragem de 3 cartas) ao final para incentivar conversão.

**Saídas:**
Mensagem estruturada contendo o nome da carta, orientação (normal ou invertida), interpretação, orientação prática e mini‑ritual. A mensagem deve respeitar o limite de 5–7 linhas.

**Casos de Borda:**
• **Usuário sem conta:** se `user_id` não existir, solicitar cadastro (nome, e‑mail, WhatsApp) antes de exibir a carta do dia.
• **Fuso horário:** considerar o fuso horário do usuário (America/Sao_Paulo) para definir a mudança de dia. Usar comparação de datas sem hora.
• **Falha na IA:** se a IA retornar mensagem vazia ou com formatação incorreta, reexecutar. Limitar tentativas e registrar erro.

*Este POP deve ser atualizado em caso de alteração no mecanismo de sorteio, na estrutura da mensagem ou na política de cartas gratuitas.*
