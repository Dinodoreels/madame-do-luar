# Plano de Implementacao - Redesign Visual do Painel Admin

Projeto: Madame do Luar  
Area: Design System, Frontend e Painel Administrativo  
Data: 2026-05-17  
Status: Implementado no admin estatico atual

## 1. Objetivo

Reformular o painel administrativo do Madame do Luar para parecer uma central SaaS premium de inteligencia espiritual, com visual sofisticado, modular, limpo e cinematografico.

O admin deve deixar de parecer um painel tecnico escuro simples e passar a transmitir:

- plataforma profissional;
- observatorio operacional;
- produto premium de IA;
- luxo silencioso;
- tecnologia sofisticada;
- atmosfera espiritual elegante;
- clareza para operacao diaria.

## 2. Referencia Visual da Imagem

A imagem anexada mostra um dashboard SaaS moderno com:

- sidebar clara, compacta e muito organizada;
- cards com bordas suaves;
- metricas bem distribuidas;
- tabelas limpas;
- filtros visiveis;
- graficos leves;
- bastante respiro;
- hierarquia visual clara;
- cores suaves em vez de contraste agressivo;
- layouts responsivos para desktop e mobile;
- estrutura modular por telas.

Para o Madame do Luar, a referencia nao deve ser copiada literalmente. A estrutura SaaS deve ser adaptada para uma atmosfera mais noturna, lunar e contemplativa.

## 3. Diagnostico do Admin Atual

Arquivos atuais:

- `frontend/admin.html`
- `frontend/admin.css`
- `frontend/admin.js`

O painel atual ja possui:

- login admin;
- sidebar;
- dashboard;
- usuarios;
- leituras;
- pagamentos;
- mensagens;
- rituais;
- planos;
- campanhas;
- CRM;
- prompts IA;
- status;
- logs;
- auditoria;
- falhas;
- configuracoes.

Problemas visuais atuais:

- visual ainda muito escuro e pesado;
- uso de dourado e roxo com pouca sutileza;
- cards simples demais para percepcao premium;
- tabelas funcionais, mas pouco refinadas;
- sidebar sem icones e sem densidade SaaS moderna;
- pouca diferenca visual entre areas criticas e areas informativas;
- falta de graficos visuais reais no admin;
- falta de skeleton/loading premium;
- microinteracoes limitadas;
- experiencia mobile ainda basica;
- login admin com pouca atmosfera cinematografica.

## 4. Direcao de Produto

O painel admin deve parecer:

- Linear + Arc Browser + Notion para estrutura;
- Apple para refinamento e silencio visual;
- dashboard SaaS premium para densidade operacional;
- editorial mistico para identidade;
- cinema contemplativo para atmosfera.

Nao deve parecer:

- cassino;
- app gamer;
- tarot barato;
- infoproduto;
- template neon;
- painel tecnico improvisado;
- fantasia medieval.

## 5. Design System Proposto

### 5.1 Paleta

Base:

- `--md-bg-deep`: preto lunar profundo;
- `--md-bg-night`: azul noite;
- `--md-bg-panel`: carvao frio;
- `--md-bg-elevated`: roxo profundo quase neutro.

Destaques:

- `--md-accent-moon`: prata lunar;
- `--md-accent-gold`: dourado suave;
- `--md-accent-mist`: azul nevoa;
- `--md-accent-lilac`: lilas frio.

Estados:

- sucesso: verde jade suave;
- alerta: amarelo cha suave;
- erro: vermelho coral escuro;
- informacao: azul nevoa.

Regra visual:

- dourado deve ser usado apenas para destaque nobre, nao como cor dominante;
- roxo deve aparecer como profundidade, nao como tema unico;
- fundos devem ter contraste suficiente sem virar preto chapado.

### 5.2 Tipografia

Manter `Inter` como fonte principal.

Recomendada para titulos editoriais:

- `Playfair Display`, `Cormorant Garamond` ou manter uma serifada discreta apenas em marca e hero/login.

Regra:

- tabelas, filtros, botoes e dados usam fonte limpa;
- titulos de pagina podem ter refinamento editorial;
- evitar fonte mistica caricata.

### 5.3 Espacamento

Escala sugerida:

- 4px: micro ajustes;
- 8px: gaps pequenos;
- 12px: controles compactos;
- 16px: cards internos;
- 24px: blocos;
- 32px: secoes;
- 48px: grandes areas.

### 5.4 Radius

Usar radius controlado:

- botoes e inputs: 8px;
- cards pequenos: 10px;
- paineis grandes: 14px;
- badges: 999px.

Evitar cards muito arredondados que parecam infantis.

### 5.5 Sombras e Glow

Sombras:

- suaves, frias e profundas;
- sem brilho forte;
- sem neon.

Glow:

- apenas em hover, foco, metricas importantes e estados especiais;
- intensidade baixa.

### 5.6 Motion

Microinteracoes:

- hover de botoes com deslocamento maximo de 1px;
- fade entre telas;
- blur transition no shell;
- loading com respiracao suave;
- skeleton loading para tabelas e cards.

Evitar:

- movimento constante;
- particulas demais;
- animacoes longas em operacao diaria.

## 6. Arquitetura Visual do Admin

### 6.1 Shell Principal

Novo layout:

- sidebar fixa no desktop;
- sidebar recolhivel no tablet;
- bottom navigation ou drawer no mobile;
- topbar com busca global, status do sistema, usuario admin e botao de refresh;
- workspace em grid modular.

Estrutura:

```text
AdminShell
  Sidebar
  Topbar
  StatusNotice
  ViewContainer
    MetricsRow
    ChartsRow
    DataPanels
    Tables
```

### 6.2 Sidebar Admin

Itens finais:

- Dashboard;
- Usuarios;
- Leituras;
- Pagamentos;
- Creditos;
- Prompts IA;
- Logs;
- Falhas;
- Analytics;
- Configuracoes.

Itens extras ja existentes podem ficar agrupados:

- Operacao: mensagens, status, auditoria, falhas;
- Comercial: rituais, planos, campanhas, CRM;
- Inteligencia: prompts IA, analytics, relatórios.

Melhorias:

- adicionar icones estilo Lucide ou equivalente local;
- item ativo com fundo suave;
- hover discreto;
- labels curtas;
- contador em badges para falhas, mensagens pendentes e PIX pendentes;
- area inferior com status do ambiente e logout.

### 6.3 Topbar

Elementos:

- titulo da tela;
- breadcrumb curto;
- busca global;
- seletor de periodo;
- botao atualizar;
- status health compacto;
- avatar/admin.

Exemplo:

```text
Centro de Controle / Dashboard
[Buscar usuario, pagamento, leitura...] [Ultimos 30 dias] [Atualizar] [Health OK]
```

## 7. Dashboard Admin Proposto

### 7.1 Cards Principais

Cards obrigatorios:

- Receita do dia;
- Receita mensal;
- Usuarios ativos;
- Leituras hoje;
- PIX pendentes;
- Custo IA;
- Erros criticos;
- Conversao free -> premium.

Cada card deve ter:

- label curta;
- valor principal;
- variacao ou contexto;
- icone;
- estado visual;
- link para tela relacionada.

### 7.2 Graficos

Graficos recomendados:

- receita por dia;
- crescimento de usuarios;
- leituras por categoria;
- uso da IA;
- retencao;
- conversao;
- horarios de pico;
- mensagens enviadas vs falhas.

Estilo:

- linhas suaves;
- barras arredondadas;
- grid discreto;
- legendas compactas;
- cores frias com um destaque lunar;
- glow muito sutil.

Implementacao inicial sem biblioteca:

- criar mini charts CSS/SVG simples para o admin estatico atual.

Implementacao futura:

- migrar para Next.js + TypeScript + Recharts.

### 7.3 Paineis Operacionais

Adicionar paineis:

- Alertas recentes;
- Usuarios quentes;
- Pagamentos pendentes;
- Falhas de IA;
- Mensagens pendentes;
- Ultimas leituras.

## 8. Tabelas Premium

Tabelas devem seguir o padrao da imagem:

- linhas limpas;
- altura consistente;
- filtros sempre visiveis;
- busca rapida;
- badges de status;
- acoes compactas;
- paginacao;
- hover suave;
- coluna principal com nome + subtitulo;
- dados financeiros alinhados;
- estado vazio bem desenhado.

Tabelas prioritarias:

1. Usuarios.
2. Pagamentos.
3. Leituras.
4. Mensagens.
5. Logs.
6. Auditoria.
7. CRM.

Estados obrigatorios:

- loading;
- vazio;
- erro;
- filtrado sem resultado;
- sucesso apos acao;
- confirmacao para acoes sensiveis.

## 9. Telas Prioritarias

### 9.1 Login Admin

Objetivo:

- parecer portal premium seguro.

Adicionar:

- fundo cinematografico lunar;
- painel glass leve;
- texto curto de seguranca;
- feedback claro de erro;
- foco visual elegante nos inputs.

### 9.2 Dashboard

Objetivo:

- virar a tela mais forte do admin.

Adicionar:

- metric cards refinados;
- graficos;
- paineis de alertas;
- resumo financeiro;
- resumo de IA;
- resumo de mensagens.

### 9.3 Usuarios

Objetivo:

- operador entender rapidamente quem e o cliente.

Adicionar:

- tabela premium;
- drawer lateral de perfil;
- tags CRM;
- saldo de creditos;
- assinatura;
- historico resumido.

### 9.4 Pagamentos

Objetivo:

- controlar receita e riscos.

Adicionar:

- cards de receita;
- filtros por status;
- destaque para PIX pendente;
- acao de reprocessar;
- historico do webhook;
- badge de `credits_released`.

### 9.5 Leituras

Objetivo:

- acompanhar uso da IA e qualidade de entrega.

Adicionar:

- filtros por status, tema e data;
- custo estimado de IA;
- modelo usado;
- falhas destacadas;
- preview da resposta.

### 9.6 Mensagens

Objetivo:

- operar WhatsApp/email sem abrir banco.

Adicionar:

- status por canal;
- falhas com motivo;
- reenvio seguro;
- fila pendente;
- indicador de simulacao vs envio real.

### 9.7 Analytics

Objetivo:

- concentrar crescimento, receita, retencao e IA.

Adicionar:

- conversao;
- retenção;
- receita;
- custo IA;
- recompra;
- funil free -> pago.

## 10. Componentes Reutilizaveis

Criar padrao visual para:

- `AdminShell`;
- `SidebarItem`;
- `Topbar`;
- `MetricCard`;
- `InsightCard`;
- `ChartPanel`;
- `DataTable`;
- `StatusBadge`;
- `FilterBar`;
- `SearchInput`;
- `ActionMenu`;
- `ConfirmModal`;
- `Drawer`;
- `Toast`;
- `SkeletonBlock`;
- `EmptyState`;
- `ErrorState`;
- `LoadingRitual`.

No admin estatico atual, esses componentes podem ser implementados como classes CSS + funcoes JS reutilizaveis.

## 11. Mobile e Responsividade

Regras:

- sidebar vira drawer ou nav compacta;
- metricas ficam em carrossel horizontal ou grid 1 coluna;
- tabelas viram cards responsivos;
- filtros ficam recolhiveis;
- botoes de acao ficam em menu;
- topbar nao deve quebrar texto;
- cards devem manter altura previsivel.

Breakpoints:

- ate 640px: mobile;
- 641px a 1024px: tablet;
- acima de 1024px: desktop;
- acima de 1440px: desktop amplo.

## 12. Plano de Implementacao por Fases

### Fase 1 - Fundacao Visual

Objetivo: criar o design system no admin atual sem quebrar a logica existente.

Checklist:

- [x] Criar tokens CSS novos em `frontend/admin.css`.
- [x] Revisar paleta para preto lunar, carvao, azul noite, prata e dourado suave.
- [x] Ajustar tipografia e hierarquia.
- [x] Redesenhar botoes, inputs, selects e badges.
- [x] Criar padrao de sombras e bordas.
- [x] Criar estados de foco acessiveis.
- [x] Criar classes de skeleton, empty e error.

Criterio de pronto:

- O admin deve parecer mais leve, premium e consistente sem mudar dados ou endpoints.

### Fase 2 - Shell, Sidebar e Topbar

Objetivo: transformar a estrutura principal em SaaS premium.

Checklist:

- [x] Redesenhar sidebar com grupos.
- [x] Adicionar icones ou marcadores visuais.
- [x] Criar contador para alertas/mensagens/PIX pendentes.
- [x] Melhorar topbar com breadcrumb, busca e health compacto.
- [x] Criar layout responsivo mobile/tablet.
- [x] Melhorar tela de login admin.

Criterio de pronto:

- O admin deve parecer uma plataforma operacional moderna antes mesmo de abrir as tabelas.

### Fase 3 - Dashboard Executivo

Objetivo: transformar dashboard em observatorio operacional.

Checklist:

- [x] Reorganizar metric cards.
- [x] Criar cards de receita do dia, receita mensal, usuarios ativos, leituras hoje, PIX pendentes, custo IA, erros criticos e conversao.
- [x] Criar area de graficos leves.
- [x] Criar painel de alertas recentes.
- [x] Criar painel de usuarios quentes.
- [x] Criar painel de pagamentos pendentes.
- [x] Criar painel de falhas de IA.

Criterio de pronto:

- Admin entende saude, receita, risco e operacao em ate 30 segundos.

### Fase 4 - Tabelas Premium e Filtros

Objetivo: refinar operacao diaria.

Checklist:

- [x] Recriar tabela base premium.
- [x] Padronizar filtros.
- [x] Criar busca rapida por tela.
- [x] Criar badges de status consistentes.
- [x] Criar acoes compactas por linha.
- [x] Criar estados vazio/loading/erro.
- [x] Melhorar usuarios, pagamentos, leituras e mensagens.

Criterio de pronto:

- O painel deve ser confortavel para uso repetido, com dados escaneaveis e acoes claras.

### Fase 5 - Analytics e Graficos

Objetivo: adicionar percepcao de central de inteligencia.

Checklist:

- [x] Criar graficos iniciais em CSS/SVG ou canvas leve.
- [x] Receita por periodo.
- [x] Crescimento de usuarios.
- [x] Leituras por categoria.
- [x] Uso/custo de IA.
- [x] Conversao free -> premium.
- [x] Retencao e recorrencia.

Criterio de pronto:

- O admin deve transmitir leitura estrategica do negocio, nao apenas listagem de registros.

### Fase 6 - Microinteracoes e Polimento

Objetivo: elevar percepcao premium sem excesso.

Checklist:

- [x] Adicionar fade suave entre views.
- [x] Adicionar hover premium em cards e linhas.
- [x] Criar loading cinematografico discreto.
- [x] Criar toasts modernos.
- [x] Criar transicoes de drawer/modal.
- [x] Revisar contraste e acessibilidade.
- [x] Testar mobile, tablet e desktop.

Criterio de pronto:

- A experiencia deve parecer cara, calma e precisa.

### Fase 7 - Evolucao Tecnica Opcional

Objetivo: preparar migracao para stack moderna quando fizer sentido.

Checklist:

- [ ] Mapear admin atual para componentes React.
- [ ] Definir Next.js + TypeScript + TailwindCSS.
- [ ] Definir shadcn/ui.
- [ ] Definir Recharts.
- [ ] Definir Framer Motion.
- [ ] Criar camada API client tipada.
- [ ] Migrar tela por tela sem perder operacao atual.

Criterio de pronto:

- O admin ganha base escalavel sem interromper o produto atual.

## 13. Ordem Recomendada de Execucao

1. Design tokens e base CSS.
2. Login admin.
3. Sidebar e topbar.
4. Dashboard.
5. Tabela de usuarios.
6. Tabela de pagamentos.
7. Tabela de leituras.
8. Mensagens e logs.
9. Analytics.
10. Mobile.
11. Polimento final.

## 14. Validacoes Obrigatorias

A cada fase:

```powershell
node --check frontend\admin.js
python -B tools\check_text_quality.py
python -B tools\validate_public_sale_readiness.py
```

Quando houver mudanca funcional:

```powershell
python -B tools\validate_operation_sprint.py
```

Antes de considerar pronto:

- [ ] Desktop conferido.
- [ ] Mobile conferido.
- [ ] Nenhum texto quebrado.
- [ ] Nenhum dado fake apresentado como real.
- [ ] Nenhum endpoint admin quebrado.
- [ ] Login admin funcionando.
- [ ] Tabelas principais carregando.
- [ ] Estados de erro visiveis.

## 15. Definicao de Pronto

O redesign visual do painel admin sera considerado pronto quando:

- parecer uma central SaaS premium;
- mantiver todos os dados reais atuais;
- melhorar clareza operacional;
- funcionar em mobile, tablet e desktop;
- nao esconder falhas;
- nao inventar metricas falsas;
- nao quebrar login, filtros, tabelas ou acoes;
- passar nas validacoes tecnicas;
- estiver documentado no plano principal e no progresso.

## 16. Proxima Acao Recomendada

Comecar pela Fase 1:

- refatorar `frontend/admin.css` com tokens premium;
- redesenhar login, sidebar, topbar, cards, inputs e tabelas base;
- manter `frontend/admin.js` intacto o maximo possivel na primeira rodada.

Essa abordagem melhora o visual rapidamente sem colocar a operacao em risco.
