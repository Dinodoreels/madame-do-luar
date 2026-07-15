# Task Plan — Madame do Luar SaaS

O presente documento descreve o plano de execução para o desenvolvimento do produto
Madame do Luar, um SaaS de leituras místicas que combina IA, automação e
experiência ritualística. Ele segue o protocolo V.L.A.E.G. (Visão, Link,
Arquitetura, Estilo, Gatilho) e a arquitetura de três camadas A.N.T. O
planejamento está dividido em fases que devem ser cumpridas em ordem. Nenhum
código pode ser escrito antes da definição de dados e a aprovação do
blueprint.

## Fase 0 — Inicialização
- Criar a estrutura de pastas do projeto local (`architecture/`,
`tools/`, `prompts/`, `.tmp/`) e os documentos base (`docs/product/task_plan.md`,
`docs/internal-local/findings.md`, `docs/internal-local/progress.md`, `docs/product/gemini.md`).
- Carregar o Persona da Madame do Luar (ver `docs/product/persona.md`) para
orientar o comportamento da IA.
- Preencher o `.env` com chaves de API (OpenAI/Gemini, Supabase,
gateway de pagamentos, API de WhatsApp). Não colocar chaves em código.
- Registrar no `progress.md` a conclusão da fase de inicialização.

## Fase 1 — Visão e Lógica (V)
**Perguntas de descoberta**
- **Qual é o resultado único desejado?** (Criar um SaaS de leituras e rituais que gere
receita recorrente por assinatura e venda de rituais).
- **Quais integrações serão usadas?** (OpenAI/Gemini, Supabase, API de
pagamento, API de WhatsApp, API de e‑mail, armazenamento de PDF/áudio).
- **Onde residem os dados primários?** (Supabase em tabelas bem definidas;
arquivo de cartas do tarot; biblioteca de rituais com PDF + áudio).
- **Qual é o payload final?** (Mensagens de leitura estruturadas, PDF/áudio de
rituais, e‑mails e mensagens de WhatsApp personalizados).
- **Quais regras comportamentais o sistema deve seguir?** (Vide `docs/product/persona.md`;
tom acolhedor e místico, segurança de IA, não promover medicina ou
finanças, privacidade de dados).

**Ações:**
- Definir o esquema de dados em `docs/product/gemini.md` antes de qualquer
codificação. O modelo inicial inclui tabelas de `users`, `questions`,
`daily_cards`, `readings`, `cards`, `subscriptions`, `payments`,
`rituals`, `ritual_purchases`, `message_events` e `marketing_sequences`.
- Pesquisar referências técnicas e recursos externos (repositórios,
bibliotecas de tarot, API de WhatsApp, etc.) e anotar em `findings.md`.
- Escrever blueprint de alto nível para cada fluxo (carta do dia,
tiragem de 3 cartas, assinatura, rituais, retorno automático,
marketing). Registre no `architecture/` um documento para cada fluxo.
- Registrar no `progress.md` a conclusão da Fase 1.

## Fase 2 — Link (L)
Verificar conexões com todos os serviços externos:
- Testar chave da API de IA com `tools/test_openai.py` ou equivalente.
- Testar conexão com banco de dados (Supabase) usando `tools/test_database.py`.
- Testar gateway de pagamento (`tools/test_payment.py`).
- Testar API de WhatsApp/e‑mail com `tools/test_whatsapp.py` e `tools/test_email.py`.
- Armazenar resultados e eventuais problemas em `findings.md`.
- Não prosseguir para lógica de negócios se alguma conexão falhar. Resolver
pendências e atualizar a documentação antes de avançar.
- Registrar no `progress.md` a conclusão da Fase 2.

## Fase 3 — Arquitetura (A)
Escrever Procedimentos Operacionais Padrão (POPs) dentro de `architecture/`:
- `leitura_tarot.md` — define a lógica de seleção de cartas, interação com a IA
e construção do payload para tiragens de 3 cartas.
- `carta_do_dia.md` — descreve o fluxo de geração da carta do dia
(gratuita), salvamento e bloqueio de múltiplas cartas no mesmo dia.
- `retorno_24h.md` — define o gatilho e o conteúdo das mensagens
automáticas enviadas 24 h, 3 dias, 7 dias e 30 dias após uma
pergunta.
- `rituais.md` — orienta a biblioteca de rituais (3 gratuitos, 7 pagos),
entregáveis (PDF + áudio) e integração com upsell/downsell.
- `marketing.md` — define os fluxos de e‑mail e WhatsApp para
onboarding, retenção e reativação.

Criar prompts em `prompts/` para cada módulo:
- `tres_cartas.md`, `carta_do_dia.md`, `retorno_24h.md`, `marketing.md`.

Implementar ferramentas (scripts) em `tools/` somente depois que os POPs
estiverem escritos e aprovados. Cada script deve ser atômico e
determinístico; não haverá lógica de negócio dentro de funções de IA.
- Documentar casos de borda em cada POP (ex.: usuário sem
assinatura, falha no pagamento, API indisponível).
- Registrar no `progress.md` a conclusão da Fase 3.

## Fase 4 — Estilo (E)
- Refinar o payload: formatar as saídas da IA em blocos bonitos
(por exemplo, markdown para e‑mail, JSON estruturado para API,
mensagens formatadas para WhatsApp). Utilizar a paleta escura,
roxo profundo, dourado e símbolos lunares nas interfaces.
- Prototipar a UI do dashboard do usuário e do painel administrativo
(caso exista), garantindo acessibilidade e responsividade.
- Obter feedback dos usuários ou stakeholders e ajustar.
- Registrar no `progress.md` a conclusão da Fase 4.

## Fase 5 — Gatilho (G)
- Configurar deploy: mover scripts para ambiente em nuvem,
configurar secrets, ajustar variáveis de ambiente.
- Agendar cron jobs ou webhooks para gatilhos automáticos
(mensagens pós‑pergunta, renovações de assinatura, campanhas de
marketing). Utilizar `message_events` para registrar cada
disparo.
- Auditar o sistema: registrar logs, tratar exceções e validar
segurança (limites de requisição, privacidade de dados, conformidade
LGPD/GDPR).
- Documentar procedimentos de manutenção em `docs/product/gemini.md` para
garantir a continuidade.
- Registrar no `progress.md` a conclusão da Fase 5.

Este plano serve como guia para toda a equipe. Qualquer ajuste de
escopo deve ser refletido aqui e nos demais documentos de arquitetura antes
da implementação. A aderência a este plano garante que o sistema será
confiável, escalável e alinhado com a visão de negócio.
