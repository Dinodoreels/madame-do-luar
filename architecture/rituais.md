# POP — Biblioteca e Upsell de Rituais

**Objetivo:**
Gerenciar a biblioteca de rituais espirituais oferecidos aos consulentes, incluindo rituais gratuitos (incluídos na assinatura) e rituais pagos (upsell). Cada ritual possui um PDF com instruções e um áudio guiado. O POP também define como sugerir rituais com base na pergunta do usuário e como processar a compra.

**Entradas:**
| parâmetro | tipo | descrição |
| --- | --- | --- |
| `user_id` | UUID | Identificador do usuário |
| `tema` | texto | Tema da pergunta (amor, prosperidade, proteção etc.) |
| `ritual_id` | UUID | Identificador do ritual a ser entregue (opcional) |
| `acao` | texto | listar, sugerir, comprar |

**Processo:**
1. **Listar rituais:** quando solicitado (ação listar), retornar todos os rituais disponíveis, marcando quais são gratuitos e quais já foram adquiridos pelo usuário (`ritual_purchases`).
2. **Sugerir ritual:** para o tema da pergunta, selecionar um ritual relacionado entre os pagos. Exemplo: tema “amor” → rituais Reconexão Amorosa ou Adoçamento com Mel; tema “prosperidade” → ritual da Prosperidade. Caso o ritual seja gratuito, ele é mostrado como bônus; se for pago, exibir preço e opção de compra.
3. **Compra de ritual (ação comprar):**
4. Validar se o ritual existe e está ativo (`rituals.ativo = true`).
5. Verificar se o usuário já possui o ritual (entrada em `ritual_purchases` com status = approved). Se possuir, apenas entregar os links.
6. Criar pagamento (`payments` com tipo = ritual) e redirecionar para o gateway de pagamento. Salvar status pending em `ritual_purchases`.
7. Ao receber confirmação do gateway (webhook), atualizar `payments.status = approved` e `ritual_purchases.status = approved`.
8. Liberar download do PDF e áudio via links assinados (expiram em tempo determinado).
9. **Entrega:** enviar por e‑mail e/ou WhatsApp os links do PDF e áudio, junto com uma pequena introdução da Madame do Luar.
10. **Histórico:** registrar a compra do ritual em `ritual_purchases` com data e status. Atualizar histórico de uso se o usuário acessar novamente.

**Saídas:**
Dependendo da ação:
- **listar**: lista de rituais (nome, tema, preço, gratuito? já adquirido?).
- **sugerir**: sugestão de um ritual (nome, descrição, preço ou gratuito) baseado no tema da pergunta.
- **comprar**: fluxo de pagamento iniciado e instruções para pagamento. Após aprovação, links de download.
- **download**: links temporários de PDF e áudio do ritual adquirido.

**Casos de Borda:**
- **Usuário não assinante:** se o usuário não possui assinatura, permitir compra de rituais pagos, mas não liberar os gratuitos que são exclusivos do plano.
- **Ritual indisponível:** se `rituals.ativo = false`, não mostrar o ritual. Registrar tentativa de acesso.
- **Pagamento falhou:** se o gateway retornar falha, atualizar `payments.status = failed` e permitir reenvio de pagamento.
- **Limite de downloads:** opcionalmente, limitar o número de vezes que o usuário pode baixar o mesmo ritual para evitar abuso.

*Este POP deve ser revisado quando novos rituais forem criados, preços alterados ou política de acesso modificada.*
