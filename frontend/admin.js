const ADMIN_BASE = (() => {
  if (window.location.protocol === "file:") return `${"http://"}${"local"}${"host"}:${8000}`;
  if (!window.location.port || ["8000", "8001", "8002"].includes(window.location.port)) return "";
  return "";
})();

const state = {
  token: "",
  user: readJson("mdl_admin_user"),
  view: "dashboard",
  cache: {},
};

const VIEW_META = {
  dashboard: ["Centro de controle", "Dashboard"],
  users: ["Operacao", "Usuarios"],
  readings: ["Operacao", "Leituras"],
  payments: ["Operacao", "Pagamentos"],
  messages: ["Operacao", "Mensagens"],
  rituals: ["Crescimento", "Rituais"],
  plans: ["Crescimento", "Creditos"],
  campaigns: ["Crescimento", "Campanhas"],
  crm: ["Crescimento", "CRM"],
  prompts: ["Sistema", "Prompts IA"],
  status: ["Central", "Analytics"],
  logs: ["Sistema", "Logs"],
  audit: ["Sistema", "Auditoria"],
  ops: ["Central", "Falhas"],
  settings: ["Sistema", "Configuracoes"],
};

const VIEW_TABLE_TARGETS = {
  users: ["usersTable"],
  readings: ["readingsTable"],
  payments: ["paymentsTable"],
  messages: ["messagesTable", "notificationLogsTable"],
  rituals: ["ritualsTable", "ritualPurchasesTable"],
  plans: ["plansTable", "packagesTable", "couponsTable"],
  campaigns: ["campaignsTable", "campaignStepsTable"],
  crm: ["crmUsersTable", "crmTagsSegmentsTable", "crmTriggersTable"],
  prompts: ["promptsTable"],
  status: ["healthChecksTable", "statusAlertsTable", "statusPendingMessagesTable"],
  logs: ["logsTable"],
  audit: ["auditTable"],
  ops: ["queueTable", "errorsTable"],
  settings: ["settingsTable"],
};

function readJson(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

function syncAdminSessionFromUserSession() {
  const publicSession = readJson("mdl_session");
  const publicUser = publicSession?.usuario;
  const isExpired = publicSession?.expires_at && Number(publicSession.expires_at) <= Date.now();
  const isAdmin = ["admin", "super_admin"].includes(publicUser?.role);

  if (isExpired || !isAdmin) return;

  state.user = publicUser;
  localStorage.setItem("mdl_admin_user", JSON.stringify(state.user));
}

function adminHeaders(extra = {}) {
  return {...extra};
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || 15000);
  let response;
  try {
    response = await fetch(`${ADMIN_BASE}${path}`, {
      ...options,
      credentials: "include",
      signal: controller.signal,
      headers: adminHeaders(options.headers || {}),
    });
  } catch (err) {
    if (err.name === "AbortError") throw new Error("Tempo esgotado ao consultar o backend. Tente atualizar em instantes.");
    throw err;
  } finally {
    clearTimeout(timeout);
  }
  let data = {};
  try { data = await response.json(); } catch {}
  if (response.status === 401 || response.status === 403) {
    throw new Error(data.detail || "Acesso administrativo negado.");
  }
  if (!response.ok) throw new Error(data.detail || "Erro ao consultar o backend.");
  return data;
}

function showNotice(message, isError = false) {
  const el = document.getElementById("statusNotice");
  el.textContent = message;
  el.hidden = false;
  el.classList.toggle("error", isError);
  clearTimeout(showNotice.timer);
  showNotice.timer = setTimeout(() => { el.hidden = true; }, 4200);
}

function money(value) {
  return Number(value || 0).toLocaleString("pt-BR", {style: "currency", currency: "BRL"});
}

function creditsText(value) {
  const amount = Number(value || 0);
  return `${amount} ${amount === 1 ? "credito" : "creditos"}`;
}

function dateText(value) {
  if (!value) return "--";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("pt-BR");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[c]));
}

function sanitizedFragment(html) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(String(html ?? ""), "text/html");
  doc.querySelectorAll("script, iframe, object, embed, link, meta").forEach((node) => node.remove());
  doc.body.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attr) => {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim().toLowerCase();
      if (name.startsWith("on") || name === "srcdoc") {
        node.removeAttribute(attr.name);
        return;
      }
      if ((name === "href" || name === "src") && /^(javascript:|data:text\/html)/i.test(value)) {
        node.removeAttribute(attr.name);
      }
    });
  });
  const fragment = document.createDocumentFragment();
  [...doc.body.childNodes].forEach((node) => fragment.appendChild(document.importNode(node, true)));
  return fragment;
}

function setSafeHTML(target, html) {
  if (!target) return;
  target.replaceChildren(sanitizedFragment(html));
}

function badge(value) {
  const text = escapeHtml(value || "--");
  return `<span class="badge ${String(value || "").toLowerCase()}">${text}</span>`;
}

function safeNumber(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number : 0;
}

function userLabel(row) {
  const user = row.usuario || row.user || {};
  return user.nome || user.email || user.whatsapp || row.user_name || row.email || row.whatsapp || row.user_id || "--";
}

function readingQuestionText(row) {
  const question = row.question;
  if (question && typeof question === "object") return question.pergunta || question.question || "";
  return question || row.pergunta || "";
}

function readingTypeText(row) {
  const question = row.question;
  const questionType = question && typeof question === "object" ? question.tema : "";
  return row.type || row.tipo_leitura || row.tipo || row.tema || questionType || "--";
}

function metricTone(label, value, hint = "") {
  const text = `${label} ${value} ${hint}`.toLowerCase();
  if (text.includes("erro") || text.includes("falha") || text.includes("critico")) return "is-danger";
  if (text.includes("pendente") || text.includes("pix") || text.includes("alerta")) return "is-warn";
  if (text.includes("receita") || text.includes("conversao") || text.includes("aprov")) return "is-ok";
  return "";
}

function table(targetId, columns, rows, actions = null) {
  const target = document.getElementById(targetId);
  const search = (document.getElementById("globalSearch").value || "").toLowerCase();
  const filtered = rows.filter((row) => JSON.stringify(row).toLowerCase().includes(search));
  const body = filtered.map((row) => `
    <tr>
      ${columns.map((col) => `<td>${col.render ? col.render(row) : escapeHtml(row[col.key])}</td>`).join("")}
      ${actions ? `<td><div class="row-actions">${actions(row)}</div></td>` : ""}
    </tr>
  `).join("");
  setSafeHTML(target, `
    <div class="table-wrap">
      <table>
        <thead><tr>${columns.map((col) => `<th>${col.label}</th>`).join("")}${actions ? "<th>Acoes</th>" : ""}</tr></thead>
        <tbody>${body || `<tr><td colspan="${columns.length + (actions ? 1 : 0)}"><div class="table-empty">Nenhum registro encontrado para os filtros atuais.</div></td></tr>`}</tbody>
      </table>
    </div>
  `);
}

function renderTableMessage(targetId, message, isError = false) {
  const target = document.getElementById(targetId);
  if (!target) return;
  setSafeHTML(target, `
    <div class="table-wrap">
      <div class="table-empty ${isError ? "is-error" : ""}">${escapeHtml(message)}</div>
    </div>
  `);
}

function renderViewMessage(view, message, isError = false) {
  (VIEW_TABLE_TARGETS[view] || []).forEach((targetId) => renderTableMessage(targetId, message, isError));
}

function metric(label, value, hint = "") {
  return `<article class="metric-card ${metricTone(label, value, hint)}"><small>${label}</small><strong>${value}</strong><span class="muted">${hint}</span></article>`;
}

function renderBarChart(targetId, items) {
  const max = Math.max(...items.map((item) => safeNumber(item.value)), 1);
  setSafeHTML(document.getElementById(targetId), items.map((item) => {
    const height = Math.max(8, Math.round((safeNumber(item.value) / max) * 100));
    return `
      <div class="bar-column" title="${escapeHtml(item.label)}: ${escapeHtml(item.display ?? item.value)}">
        <div class="bar-track"><div class="bar-fill" style="height:${height}%"></div></div>
        <span class="bar-label">${escapeHtml(item.short || item.label)}</span>
      </div>
    `;
  }).join(""));
}

function renderLineStats(targetId, items) {
  const max = Math.max(...items.map((item) => safeNumber(item.value)), 1);
  setSafeHTML(document.getElementById(targetId), items.map((item) => {
    const width = Math.max(3, Math.round((safeNumber(item.value) / max) * 100));
    return `
      <div class="line-row">
        <header><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.display ?? item.value)}</strong></header>
        <div class="line-track"><div class="line-fill" style="width:${width}%"></div></div>
      </div>
    `;
  }).join(""));
}

function collection(data, ...keys) {
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key];
  }
  return [];
}

function filterValue(id) {
  return document.getElementById(id)?.value || "";
}

function rowDateValue(row, ...keys) {
  for (const key of keys) {
    if (row[key]) return row[key];
  }
  return "";
}

function onOrAfter(value, dateFrom) {
  if (!dateFrom) return true;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return true;
  return d >= new Date(`${dateFrom}T00:00:00`);
}

function requireAdminSession() {
  syncAdminSessionFromUserSession();
  const logged = Boolean(state.token);
  document.getElementById("adminLogin").hidden = logged;
  document.getElementById("adminApp").hidden = !logged;
  window.scrollTo({top: 0, left: 0, behavior: "auto"});
  document.querySelector(".workspace")?.scrollTo({top: 0, left: 0, behavior: "auto"});
  document.querySelector(".nav")?.scrollTo({top: 0, left: 0, behavior: "auto"});
  if (logged) loadView("dashboard");
}

function showAdminShell() {
  document.getElementById("adminLogin").hidden = true;
  document.getElementById("adminApp").hidden = false;
  window.scrollTo({top: 0, left: 0, behavior: "auto"});
  document.querySelector(".workspace")?.scrollTo({top: 0, left: 0, behavior: "auto"});
  document.querySelector(".nav")?.scrollTo({top: 0, left: 0, behavior: "auto"});
}

async function login(event) {
  event.preventDefault();
  const error = document.getElementById("loginError");
  const button = document.getElementById("adminLoginButton");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  error.hidden = true;
  if (button) {
    button.disabled = true;
    button.textContent = "Entrando...";
  }
  try {
    const data = await fetch(`${ADMIN_BASE}/auth/login`, {
      method: "POST",
      credentials: "include",
      signal: controller.signal,
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        email: document.getElementById("adminEmail").value.trim(),
        senha: document.getElementById("adminPassword").value,
      }),
    }).then(async (r) => {
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || "Login invalido.");
      return d;
    });
    if (!["admin", "super_admin"].includes(data.usuario?.role)) {
      throw new Error("Este usuario nao tem permissao de administrador.");
    }
    localStorage.removeItem("mdl_admin_token");
    localStorage.removeItem("mdl_session");
    state.token = "";
    state.user = data.usuario;
    localStorage.setItem("mdl_admin_user", JSON.stringify(state.user));
    localStorage.setItem("mdl_session", JSON.stringify({
      usuario: state.user,
      expires_at: Date.now() + ((data.expires_in || 86400) * 1000),
    }));
    showAdminShell();
    loadView("dashboard");
  } catch (err) {
    error.textContent = err.name === "AbortError"
      ? "Tempo esgotado ao entrar no painel. Verifique se o backend esta aberto e tente novamente."
      : err.message;
    error.hidden = false;
  } finally {
    clearTimeout(timeout);
    if (button) {
      button.disabled = false;
      button.textContent = "Entrar no painel";
    }
  }
}

function logout() {
  state.token = "";
  state.user = null;
  fetch(`${ADMIN_BASE}/auth/logout`, {method: "POST", credentials: "include"}).catch(() => {});
  localStorage.removeItem("mdl_admin_token");
  localStorage.removeItem("mdl_admin_user");
  localStorage.removeItem("mdl_session");
  requireAdminSession();
}

async function loadDashboard() {
  const dashboardPart = async (path, fallback) => {
    try {
      return await request(path, {timeout: 9000});
    } catch (err) {
      console.warn(`Falha ao carregar ${path}:`, err);
      return fallback;
    }
  };
  const [dashboard, finance, ai, statusPanel, alerts] = await Promise.all([
    dashboardPart("/admin/dashboard", {metricas: {}, recentes: {}}),
    dashboardPart("/admin/reports/financial", {}),
    dashboardPart("/admin/reports/ai", {}),
    dashboardPart("/admin/status", {health: {status: "parcial"}, conversao: {}, receita: {}, erros_recentes: []}),
    dashboardPart("/admin/alerts", {alerts: []}),
  ]);
  const m = dashboard.metricas || {};
  const f = finance.report || finance || {};
  const a = ai.report || ai || {};
  const conversao = statusPanel.conversao || {};
  const receita = statusPanel.receita || {};
  const health = statusPanel.health || {};
  document.getElementById("adminHealthPill").textContent = `Health ${health.status || "ok"}`;
  setSafeHTML(document.getElementById("dashboardMetrics"), [
    metric("Receita do dia", money(f.receita_hoje || receita.receita_hoje || 0), "operacao atual"),
    metric("Receita mensal", money(f.receita_30_dias || receita.receita_30_dias || f.receita_total), `${f.pagamentos_aprovados || receita.pagamentos_aprovados || 0} aprovados`),
    metric("Usuarios ativos", m.usuarios_ativos ?? conversao.usuarios_total ?? m.usuarios_total ?? 0, "base operacional"),
    metric("Leituras hoje", m.leituras_hoje ?? 0, "rituais e consultas"),
    metric("PIX pendentes", f.pagamentos_pendentes ?? 0, "aguardando baixa"),
    metric("Custo IA", money(a.custo_estimado), `${a.tokens_total || a.tokens_usados || 0} tokens`),
    metric("Erros criticos", m.logs_criticos ?? (statusPanel.erros_recentes || []).length ?? 0, "acao operacional"),
    metric("Conversao", percent(conversao.taxa_usuario_para_compra), "free para premium"),
  ].join(""));
  renderBarChart("revenueChart", [
    {label: "Receita total", short: "Total", value: f.receita_total || receita.receita_total, display: money(f.receita_total || receita.receita_total)},
    {label: "Receita 30 dias", short: "30d", value: f.receita_30_dias || receita.receita_30_dias, display: money(f.receita_30_dias || receita.receita_30_dias)},
    {label: "Receita 7 dias", short: "7d", value: f.receita_7_dias || receita.receita_7_dias, display: money(f.receita_7_dias || receita.receita_7_dias)},
    {label: "Aprovados", short: "Aprov", value: f.pagamentos_aprovados || receita.pagamentos_aprovados},
    {label: "Pendentes", short: "Pend", value: f.pagamentos_pendentes || 0},
    {label: "Compradores", short: "Comp", value: receita.compradores_unicos || conversao.compradores || 0},
  ]);
  renderLineStats("aiChart", [
    {label: "Leituras totais", value: a.leituras_total || 0},
    {label: "Tokens usados", value: a.tokens_total || a.tokens_usados || 0},
    {label: "Falhas de IA", value: a.leituras_com_erro || 0},
    {label: "Custo estimado", value: a.custo_estimado || 0, display: money(a.custo_estimado)},
  ]);
  setSafeHTML(document.getElementById("hotUsersList"), `<div class="compact-item"><strong>Pronto para gerar</strong><small>Clique em Gerar para calcular usuarios quentes sem bloquear a abertura do painel.</small></div>`);
  renderAlerts(alerts);
}

function renderHotUsers(data) {
  const rows = collection(data, "usuarios", "users");
  setSafeHTML(document.getElementById("hotUsersList"), rows.slice(0, 8).map((u) => `
    <div class="compact-item">
      <strong>${escapeHtml(u.name || u.nome || u.email || u.user_id)}</strong>
      <small>Score ${u.score || 0} | ${escapeHtml((u.motivos || u.reasons || []).join(", "))}</small>
    </div>
  `).join("") || `<div class="compact-item"><small>Nenhum usuario quente agora.</small></div>`);
}

function renderAlerts(data) {
  const rows = data.alerts || [];
  setSafeHTML(document.getElementById("alertsList"), rows.slice(0, 8).map((a) => `
    <div class="compact-item">
      <strong>${badge(a.severity)} ${escapeHtml(a.title)}</strong>
      <small>${escapeHtml(a.description || "")}</small>
    </div>
  `).join("") || `<div class="compact-item"><small>Nenhum alerta aberto.</small></div>`);
}

async function loadUsers() {
  const data = await request("/admin/users");
  state.cache.users = collection(data, "usuarios", "users");
  const status = filterValue("userStatusFilter");
  const plan = filterValue("userPlanFilter");
  const dateFrom = filterValue("userDateFromFilter");
  const rows = state.cache.users.filter((r) => {
    const planOk = !plan || (plan === "assinante" ? Boolean(r.assinante || r.plan_id) : !r.assinante && !r.plan_id);
    return (!status || r.status === status) && planOk && onOrAfter(rowDateValue(r, "created_at", "criado_em"), dateFrom);
  });
  table("usersTable", [
    {label: "Nome", render: (r) => `<strong>${escapeHtml(r.name || r.nome || "--")}</strong><br><small>${escapeHtml(r.email)}</small>`},
    {label: "Telefone", render: (r) => escapeHtml(r.phone || r.whatsapp || "--")},
    {label: "Assinatura", render: (r) => badge(r.assinante || r.plan_id ? "assinante" : "sem_plano")},
    {label: "Role", render: (r) => badge(r.role)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Creditos", render: (r) => escapeHtml(r.credits_balance ?? 0)},
    {label: "Cadastro", render: (r) => dateText(r.created_at || r.criado_em)},
  ], rows, (r) => `
    <button data-user-detail="${r.user_id || r.id}">Historico</button>
    <button data-user-status="${r.user_id || r.id}" data-status="${r.status === "bloqueado" ? "ativo" : "bloqueado"}">${r.status === "bloqueado" ? "Desbloquear" : "Bloquear"}</button>
    <button data-user-credits="${r.user_id || r.id}">Creditos</button>
  `);
}

async function loadReadings() {
  const data = await request("/admin/readings");
  state.cache.readings = collection(data, "leituras", "readings");
  const status = filterValue("readingStatusFilter");
  const dateFrom = filterValue("readingDateFromFilter");
  const rows = state.cache.readings.filter((r) => {
    const rowStatus = r.status || "done";
    return (!status || rowStatus === status) && onOrAfter(rowDateValue(r, "created_at", "criado_em"), dateFrom);
  });
  table("readingsTable", [
    {label: "Usuario", render: (r) => escapeHtml(userLabel(r))},
    {label: "Tipo", render: (r) => escapeHtml(readingTypeText(r))},
    {label: "Pergunta", render: (r) => escapeHtml(readingQuestionText(r).slice(0, 90))},
    {label: "Status", render: (r) => badge(r.status || "done")},
    {label: "Tokens", render: (r) => escapeHtml(r.tokens_used || 0)},
    {label: "Data", render: (r) => dateText(r.created_at || r.criado_em)},
  ], rows);
}

async function loadPayments() {
  const data = await request("/admin/payments");
  state.cache.payments = collection(data, "pagamentos", "payments");
  const status = filterValue("paymentStatusFilter");
  const dateFrom = filterValue("paymentDateFromFilter");
  const rows = state.cache.payments.filter((r) => {
    return (!status || r.status === status) && onOrAfter(rowDateValue(r, "created_at", "criado_em"), dateFrom);
  });
  table("paymentsTable", [
    {label: "Usuario", render: (r) => escapeHtml(r.user_id)},
    {label: "Produto", render: (r) => escapeHtml(r.product_name || r.tipo || "--")},
    {label: "Valor", render: (r) => money(r.amount || r.valor)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Gateway", render: (r) => escapeHtml(r.gateway || "--")},
    {label: "Criado", render: (r) => dateText(r.created_at || r.criado_em)},
  ], rows, (r) => `
    <button data-payment-approve="${r.payment_id || r.id}">Aprovar</button>
    <button data-payment-reprocess="${r.payment_id || r.id}">Reprocessar</button>
  `);
}

async function loadUserDetail(userId) {
  const data = await request(`/admin/users/${userId}`);
  const target = document.getElementById("userDetail");
  const usuario = data.usuario || {};
  const assinatura = data.assinatura || {};
  target.hidden = false;
  setSafeHTML(target, `
    <h3>${escapeHtml(usuario.nome || usuario.email || userId)}</h3>
    <p class="muted">Assinatura: ${escapeHtml(assinatura.status || (usuario.assinante ? "assinante" : "sem_plano"))} | Creditos: ${escapeHtml(usuario.credits_balance ?? 0)}</p>
    <div class="split-grid">
      <div>
        <h3>Historico de leituras</h3>
        ${(data.leituras || []).slice(0, 8).map((r) => `<div class="compact-item"><strong>${escapeHtml(r.tipo || r.tipo_leitura || "leitura")}</strong><small>${dateText(r.created_at || r.criado_em)} | ${escapeHtml((r.question || r.pergunta || "").slice(0, 120))}</small></div>`).join("") || `<div class="compact-item"><small>Sem leituras.</small></div>`}
      </div>
      <div>
        <h3>Pagamentos</h3>
        ${(data.pagamentos || []).slice(0, 8).map((p) => `<div class="compact-item"><strong>${badge(p.status)} ${money(p.amount || p.valor)}</strong><small>${dateText(p.created_at || p.criado_em)} | ${escapeHtml(p.product_name || p.tipo || "")}</small></div>`).join("") || `<div class="compact-item"><small>Sem pagamentos.</small></div>`}
      </div>
    </div>
  `);
  target.scrollIntoView({behavior: "smooth", block: "nearest"});
}

async function loadMessages() {
  const data = await request("/admin/messages");
  state.cache.messages = collection(data, "eventos", "messages");
  state.cache.notificationLogs = collection(data, "logs");
  const status = filterValue("messageStatusFilter");
  const channel = filterValue("messageChannelFilter");
  const dateFrom = filterValue("messageDateFromFilter");
  const rows = state.cache.messages.filter((r) => {
    return (!status || r.status === status)
      && (!channel || r.canal === channel)
      && onOrAfter(rowDateValue(r, "created_at", "agendado_para", "enviado_em"), dateFrom);
  });
  table("messagesTable", [
    {label: "Usuario", render: (r) => escapeHtml(r.user_id)},
    {label: "Tipo", render: (r) => escapeHtml(r.tipo)},
    {label: "Canal", render: (r) => badge(r.canal)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Tentativas", render: (r) => escapeHtml(`${r.attempts || 0}/${r.max_attempts || 3}`)},
    {label: "Agenda", render: (r) => dateText(r.agendado_para)},
    {label: "Mensagem", render: (r) => escapeHtml((r.mensagem || r.error_message || "").slice(0, 90))},
  ], rows, (r) => `<button data-message-resend="${r.message_id}">Reenviar</button>`);
  table("notificationLogsTable", [
    {label: "Log", render: (r) => escapeHtml(r.log_id || r.message_event_id || "--")},
    {label: "Canal", render: (r) => badge(r.channel)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Destino", render: (r) => escapeHtml(r.recipient || "--")},
    {label: "Erro", render: (r) => escapeHtml((r.error_message || "").slice(0, 90))},
    {label: "Data", render: (r) => dateText(r.created_at)},
  ], state.cache.notificationLogs);
}

async function loadRituals() {
  const data = await request("/admin/rituals");
  table("ritualsTable", [
    {label: "Ritual", render: (r) => `<strong>${escapeHtml(r.nome)}</strong><br><small>${escapeHtml(r.tema || "")}</small>`},
    {label: "Custo", render: (r) => creditsText(r.custo_creditos ?? r.preco)},
    {label: "Status", render: (r) => badge(r.ativo ? "active" : "inactive")},
    {label: "Atualizado", render: (r) => dateText(r.updated_at || r.created_at)},
  ], data.rituais || [], (r) => `<button data-ritual-toggle="${r.ritual_id}" data-active="${r.ativo ? "false" : "true"}">${r.ativo ? "Desativar" : "Ativar"}</button>`);
  table("ritualPurchasesTable", [
    {label: "Usuario", render: (r) => escapeHtml(userLabel(r))},
    {label: "Ritual", render: (r) => escapeHtml(r.ritual_nome || r.ritual_id)},
    {label: "Creditos", render: (r) => creditsText(r.credits_spent ?? r.creditos ?? 0)},
    {label: "Cupom", render: (r) => escapeHtml(r.coupon_code || "--")},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Data", render: (r) => dateText(r.data || r.created_at)},
  ], data.compras || []);
}

async function loadCampaigns() {
  const data = await request("/admin/campaigns");
  table("campaignsTable", [
    {label: "Campanha", render: (r) => `<strong>${escapeHtml(r.name)}</strong><br><small>${escapeHtml(r.event_type)}</small>`},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Criada", render: (r) => dateText(r.created_at)},
  ], data.campanhas || [], (r) => `<button data-campaign-toggle="${r.rule_id}" data-status="${r.status === "active" ? "inactive" : "active"}">${r.status === "active" ? "Pausar" : "Ativar"}</button>`);
  table("campaignStepsTable", [
    {label: "Campanha", render: (r) => escapeHtml(r.rule_id)},
    {label: "Canal", render: (r) => badge(r.channel)},
    {label: "Delay", render: (r) => `${escapeHtml(r.delay_minutes || 0)} min`},
    {label: "Assunto", render: (r) => escapeHtml(r.subject || "--")},
    {label: "Mensagem", render: (r) => escapeHtml((r.template || "").slice(0, 120))},
    {label: "Status", render: (r) => badge(r.status)},
  ], data.etapas || []);
}

async function loadCrm() {
  const [overview, triggers] = await Promise.all([
    request("/admin/crm"),
    request("/admin/crm/triggers"),
  ]);
  state.cache.crmUsers = collection(overview, "usuarios");
  state.cache.crmTags = collection(overview, "tags");
  state.cache.crmSegments = collection(overview, "segmentos");
  state.cache.crmTriggers = collection(triggers, "gatilhos");
  const classFilter = filterValue("crmClassFilter");
  const rows = state.cache.crmUsers.filter((r) => !classFilter || (r.classes || []).includes(classFilter));
  table("crmUsersTable", [
    {label: "Cliente", render: (r) => `<strong>${escapeHtml(r.nome || "--")}</strong><br><small>${escapeHtml(r.email || "")}</small>`},
    {label: "WhatsApp", render: (r) => escapeHtml(r.whatsapp || "--")},
    {label: "Classes", render: (r) => (r.classes || []).map((item) => badge(item)).join(" ")},
    {label: "Receita", render: (r) => money(r.crm?.receita_aprovada)},
    {label: "Compras", render: (r) => escapeHtml(r.crm?.pagamentos_aprovados ?? 0)},
    {label: "Leituras", render: (r) => escapeHtml(r.crm?.leituras_total ?? 0)},
    {label: "Inativo", render: (r) => `${escapeHtml(r.crm?.dias_inativo ?? "--")} dias`},
  ], rows, (r) => `<button data-crm-detail="${r.user_id}">Abrir CRM</button>`);

  const select = document.getElementById("crmTriggerSegmentSelect");
  setSafeHTML(select, state.cache.crmSegments.map((s) => `<option value="${escapeHtml(s.segment_id)}">${escapeHtml(s.name)}</option>`).join(""));
  table("crmTagsSegmentsTable", [
    {label: "Tipo", render: (r) => escapeHtml(r.kind)},
    {label: "Nome", render: (r) => `<strong>${escapeHtml(r.name)}</strong><br><small>${escapeHtml(r.description || "")}</small>`},
    {label: "Status", render: (r) => badge(r.status)},
  ], [
    ...state.cache.crmTags.map((tag) => ({...tag, kind: "tag"})),
    ...state.cache.crmSegments.map((segment) => ({...segment, kind: "segmento"})),
  ]);
  table("crmTriggersTable", [
    {label: "Gatilho", render: (r) => `<strong>${escapeHtml(r.name)}</strong><br><small>${escapeHtml(r.event_type || "")}</small>`},
    {label: "Segmento", render: (r) => escapeHtml(r.customer_segments?.name || r.segment_id)},
    {label: "Canal", render: (r) => badge(r.channel)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Mensagem", render: (r) => escapeHtml((r.template || "").slice(0, 100))},
  ], state.cache.crmTriggers, (r) => `<button data-crm-trigger-toggle="${r.trigger_id}" data-status="${r.status === "active" ? "inactive" : "active"}">${r.status === "active" ? "Pausar" : "Ativar"}</button>`);
}

async function loadCrmDetail(userId) {
  const data = await request(`/admin/crm/users/${userId}`);
  const target = document.getElementById("crmUserDetail");
  const usuario = data.usuario || {};
  target.hidden = false;
  setSafeHTML(target, `
    <h3>${escapeHtml(usuario.nome || usuario.email || userId)}</h3>
    <p class="muted">${(data.classificacao?.classes || []).map((item) => badge(item)).join(" ")} | Receita ${money(data.classificacao?.receita_aprovada)} | ${escapeHtml(data.classificacao?.dias_inativo ?? "--")} dias inativo</p>
    <form class="inline-form" data-crm-note-form="${escapeHtml(userId)}">
      <input name="note" placeholder="Nota administrativa" required />
      <select name="visibility"><option value="internal">Interna</option><option value="support">Suporte</option><option value="sales">Vendas</option><option value="marketing">Marketing</option></select>
      <button type="submit">Salvar nota</button>
    </form>
    <div class="split-grid">
      <div>
        <h3>Temas mais perguntados</h3>
        ${(data.temas || []).map((t) => `<div class="compact-item"><strong>${escapeHtml(t.tema)}</strong><small>${escapeHtml(t.total)} perguntas/leituras</small></div>`).join("") || `<div class="compact-item"><small>Sem temas mapeados.</small></div>`}
        <h3>Notas</h3>
        ${(data.notas || []).map((n) => `<div class="compact-item"><strong>${escapeHtml(n.visibility)}</strong><small>${escapeHtml(n.note)} | ${dateText(n.created_at)}</small></div>`).join("") || `<div class="compact-item"><small>Sem notas.</small></div>`}
      </div>
      <div>
        <h3>Compras</h3>
        ${(data.pagamentos || []).slice(0, 10).map((p) => `<div class="compact-item"><strong>${badge(p.status)} ${money(p.amount || p.valor)}</strong><small>${escapeHtml(p.product_name || p.tipo || "")} | ${dateText(p.created_at || p.criado_em)}</small></div>`).join("") || `<div class="compact-item"><small>Sem compras.</small></div>`}
        <h3>Interacoes</h3>
        ${(data.mensagens || []).slice(0, 10).map((m) => `<div class="compact-item"><strong>${badge(m.status)} ${escapeHtml(m.tipo || "")}</strong><small>${escapeHtml(m.canal || "")} | ${dateText(m.created_at || m.agendado_para)}</small></div>`).join("") || `<div class="compact-item"><small>Sem interacoes.</small></div>`}
      </div>
    </div>
  `);
  target.scrollIntoView({behavior: "smooth", block: "nearest"});
}

async function loadPlans() {
  const [plans, packages, coupons] = await Promise.all([
    request("/admin/plans"),
    request("/admin/credit-packages"),
    request("/admin/coupons"),
  ]);
  table("plansTable", [
    {label: "Plano", render: (r) => `<strong>${escapeHtml(r.name)}</strong><br><small>${escapeHtml(r.description || "")}</small>`},
    {label: "Preco", render: (r) => money(r.price)},
    {label: "Creditos", render: (r) => escapeHtml(r.credits)},
    {label: "Duracao", render: (r) => `${escapeHtml(r.duration_days || 0)} dias`},
    {label: "Status", render: (r) => badge(r.status)},
  ], plans.plans || [], (r) => `<button data-plan-disable="${r.plan_id}">Desativar</button>`);
  table("packagesTable", [
    {label: "Pacote", render: (r) => escapeHtml(r.name)},
    {label: "Preco", render: (r) => money(r.price)},
    {label: "Creditos", render: (r) => escapeHtml((r.credits || 0) + (r.bonus_credits || 0))},
    {label: "Status", render: (r) => badge(r.status)},
  ], packages.packages || [], (r) => `<button data-package-disable="${r.package_id}">Desativar</button>`);
  table("couponsTable", [
    {label: "Cupom", render: (r) => escapeHtml(r.code)},
    {label: "Tipo", render: (r) => escapeHtml(r.discount_type)},
    {label: "Valor", render: (r) => escapeHtml(r.discount_value)},
    {label: "Aplicacao", render: (r) => escapeHtml(r.applies_to || "all")},
    {label: "Status", render: (r) => badge(r.status)},
  ], coupons.coupons || [], (r) => `<button data-coupon-disable="${r.coupon_id}">Desativar</button>`);
}

async function loadPrompts() {
  const data = await request("/admin/prompts");
  state.cache.prompts = data.prompts || [];
  table("promptsTable", [
    {label: "Nome", render: (r) => `<strong>${escapeHtml(r.name)}</strong><br><small>${escapeHtml(String(r.content || "").slice(0, 110))}${String(r.content || "").length > 110 ? "..." : ""}</small>`},
    {label: "Tipo", render: (r) => escapeHtml(r.reading_type)},
    {label: "Versao", render: (r) => escapeHtml(r.version)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Atualizado", render: (r) => dateText(r.updated_at)},
  ], state.cache.prompts, (r) => `
    <button data-prompt-edit="${r.prompt_id}">Editar</button>
    <button data-prompt-disable="${r.prompt_id}">Desativar</button>
  `);
}

async function loadLogs() {
  const data = await request("/admin/logs");
  state.cache.logs = data.logs || [];
  const severity = filterValue("logSeverityFilter");
  const rows = state.cache.logs.filter((r) => !severity || r.severity === severity);
  table("logsTable", [
    {label: "Evento", render: (r) => escapeHtml(r.event_type)},
    {label: "Descricao", render: (r) => escapeHtml(r.description)},
    {label: "Severidade", render: (r) => badge(r.severity)},
    {label: "Usuario", render: (r) => escapeHtml(r.user_id || "--")},
    {label: "Admin", render: (r) => escapeHtml(r.admin_id || "--")},
    {label: "Data", render: (r) => dateText(r.created_at)},
  ], rows);
}

async function loadAudit() {
  const params = new URLSearchParams();
  const entity = filterValue("auditEntityFilter");
  const severity = filterValue("auditSeverityFilter");
  if (entity) params.set("entity_type", entity);
  if (severity) params.set("severity", severity);
  const data = await request(`/admin/audit${params.toString() ? `?${params}` : ""}`);
  table("auditTable", [
    {label: "Acao", render: (r) => `<strong>${escapeHtml(r.action)}</strong><br><small>${escapeHtml(r.entity_type || "--")} ${escapeHtml(r.entity_id || "")}</small>`},
    {label: "Usuario", render: (r) => escapeHtml(r.user_id || "--")},
    {label: "Admin", render: (r) => escapeHtml(r.admin_id || "--")},
    {label: "Severidade", render: (r) => badge(r.severity)},
    {label: "Antes", render: (r) => escapeHtml(JSON.stringify(r.before_data || {}).slice(0, 100))},
    {label: "Depois", render: (r) => escapeHtml(JSON.stringify(r.after_data || {}).slice(0, 100))},
    {label: "Data", render: (r) => dateText(r.created_at)},
  ], data.audit_logs || []);
}

function percent(value) {
  return `${Number(value || 0).toLocaleString("pt-BR", {maximumFractionDigits: 2})}%`;
}

async function loadStatusPanel() {
  const [data, conversionData, retentionData] = await Promise.all([
    request("/admin/status"),
    request("/admin/metrics/conversion").catch(() => ({})),
    request("/admin/metrics/retention").catch(() => ({})),
  ]);
  const health = data.health || {};
  const conversao = conversionData.funnel ? conversionData : (data.conversao || {});
  const retencao = retentionData.analytics_retention ? retentionData : (data.retencao || {});
  const receita = data.receita || {};
  document.getElementById("adminHealthPill").textContent = `Health ${health.status || "--"}`;

  setSafeHTML(document.getElementById("statusHealthMetrics"), [
    metric("Status geral", health.status || "--", `ambiente ${health.environment || "--"}`),
    metric("Alertas abertos", (data.alertas_abertos || []).length, "operacao"),
    metric("Erros recentes", (data.erros_recentes || []).length, "ultimos registros"),
    metric("Mensagens pendentes", (data.mensagens_pendentes || []).length, "fila atual"),
    metric("Duracao health", `${health.duration_ms || 0}ms`, "tempo de verificacao"),
  ].join(""));

  setSafeHTML(document.getElementById("conversionMetrics"), [
    metric("Cadastro", `${conversao.funnel?.cadastro?.concluido ?? conversao.usuarios_total ?? 0}`, percent(conversao.funnel?.cadastro?.taxa ?? conversao.taxa_usuario_para_leitura)),
    metric("Leitura", `${conversao.funnel?.leitura?.concluida ?? conversao.usuarios_com_leitura ?? 0}`, percent(conversao.funnel?.leitura?.taxa ?? conversao.taxa_usuario_para_leitura)),
    metric("Pagamento", `${conversao.funnel?.pagamento?.aprovado ?? conversao.compradores ?? 0}`, percent(conversao.funnel?.pagamento?.taxa_aprovacao ?? conversao.taxa_checkout_aprovado)),
    metric("PIX abandonado", `${conversao.funnel?.pagamento?.abandonado ?? conversao.checkouts_abandonados ?? 0}`, percent(conversao.funnel?.pagamento?.taxa_abandono ?? conversao.taxa_checkout_abandonado)),
  ].join("")); 

  setSafeHTML(document.getElementById("retentionMetrics"), [
    metric("Ativos 7 dias", retencao.analytics_retention?.active_7_days ?? retencao.ativos_7_dias ?? 0, percent(retencao.analytics_retention?.retention_7_rate ?? retencao.taxa_ativo_7_dias)),
    metric("Ativos 30 dias", retencao.analytics_retention?.active_30_days ?? retencao.ativos_30_dias ?? 0, percent(retencao.analytics_retention?.retention_30_rate ?? retencao.taxa_ativo_30_dias)),
    metric("Recorrencia", percent(retencao.analytics_retention?.recurrent_rate ?? retencao.taxa_recorrencia_leitura), `${retencao.analytics_retention?.recurrent_users ?? retencao.usuarios_recorrentes ?? 0} usuarios`),
    metric("Risco inatividade", retencao.risco_inatividade || 0, "sem atividade 30 dias"),
  ].join(""));

  setSafeHTML(document.getElementById("revenueMetrics"), [
    metric("Receita total", money(receita.receita_total), `${receita.pagamentos_aprovados || 0} pagamentos`),
    metric("MRR estimado", money(receita.mrr_estimado), `${receita.assinaturas_ativas || 0} assinaturas ativas`),
    metric("LTV medio", money(receita.ltv_medio), `${receita.compradores_unicos || 0} compradores`),
    metric("Churn", percent(receita.churn_rate), `${receita.assinaturas_canceladas || 0} cancelamentos`),
    metric("Receita 30 dias", money(receita.receita_30_dias), "mes atual"),
    metric("Ticket medio", money(receita.ticket_medio), `${receita.compradores_unicos || 0} compradores`),
  ].join(""));

  const checks = Object.entries(health.checks || {}).map(([name, value]) => ({name, ...value}));
  table("healthChecksTable", [
    {label: "Servico", render: (r) => escapeHtml(r.name)},
    {label: "Status", render: (r) => badge(r.status || "ok")},
    {label: "Detalhe", render: (r) => escapeHtml(JSON.stringify(r).slice(0, 130))},
  ], checks);

  table("statusAlertsTable", [
    {label: "Tipo", render: (r) => escapeHtml(r.type)},
    {label: "Severidade", render: (r) => badge(r.severity)},
    {label: "Titulo", render: (r) => escapeHtml(r.title)},
    {label: "Criado", render: (r) => dateText(r.created_at)},
  ], data.alertas_abertos || [], (r) => `<button data-alert-resolve="${r.alert_id}">Resolver</button>`);

  table("statusPendingMessagesTable", [
    {label: "Tipo", render: (r) => escapeHtml(r.tipo)},
    {label: "Canal", render: (r) => badge(r.canal)},
    {label: "Agenda", render: (r) => dateText(r.agendado_para)},
    {label: "Tentativas", render: (r) => escapeHtml(`${r.attempts || 0}/${r.max_attempts || 0}`)},
  ], data.mensagens_pendentes || []);
}

async function loadOps() {
  const [finance, ai] = await Promise.all([request("/admin/reports/financial"), request("/admin/reports/ai")]);
  const f = finance.report || finance || {};
  const a = ai.report || ai || {};
  setSafeHTML(document.getElementById("opsReports"), [
    metric("Ticket medio", money(f.ticket_medio), "pagamentos aprovados"),
    metric("Pagamentos pendentes", f.pagamentos_pendentes || 0, "aguardando baixa"),
    metric("Leituras IA", a.leituras_total || 0, "volume total"),
    metric("Erros IA", a.leituras_com_erro || 0, "falhas registradas"),
  ].join(""));
  await Promise.all([loadQueue(), loadErrors()]);
}

async function loadQueue() {
  const data = await request("/admin/reprocess-queue");
  table("queueTable", [
    {label: "Tipo", render: (r) => escapeHtml(r.type)},
    {label: "Status", render: (r) => badge(r.status)},
    {label: "Tentativas", render: (r) => escapeHtml(`${r.attempts || 0}/${r.max_attempts || 0}`)},
    {label: "Agenda", render: (r) => dateText(r.scheduled_at)},
  ], data.queue || [], (r) => `<button data-queue-done="${r.queue_id}">Concluir</button>`);
}

async function loadErrors() {
  const data = await request("/admin/errors");
  table("errorsTable", [
    {label: "Evento", render: (r) => escapeHtml(r.event_type)},
    {label: "Descricao", render: (r) => escapeHtml(r.description)},
    {label: "Severidade", render: (r) => badge(r.severity)},
    {label: "Data", render: (r) => dateText(r.created_at)},
  ], data.falhas || data.errors || []);
}

async function loadSettings() {
  const [maintenance, settings] = await Promise.all([request("/admin/maintenance"), request("/admin/settings")]);
  document.querySelector("#maintenanceForm [name=enabled]").checked = Boolean(maintenance.enabled);
  document.querySelector("#maintenanceForm [name=message]").value = maintenance.message || "";
  table("settingsTable", [
    {label: "Chave", render: (r) => escapeHtml(r.key)},
    {label: "Valor", render: (r) => escapeHtml(r.value)},
    {label: "Secreto", render: (r) => r.is_secret ? "sim" : "nao"},
  ], settings.settings || []);
}

async function loadHotUsers() {
  renderHotUsers(await request("/admin/intelligence/hot-users"));
}

async function generateAlerts() {
  await request("/admin/alerts/generate", {method: "POST"});
  renderAlerts(await request("/admin/alerts"));
  showNotice("Alertas operacionais atualizados.");
  if (state.view === "status") await loadStatusPanel();
}

async function loadAlerts() {
  renderAlerts(await request("/admin/alerts"));
}

const loaders = {
  dashboard: loadDashboard,
  users: loadUsers,
  readings: loadReadings,
  payments: loadPayments,
  messages: loadMessages,
  rituals: loadRituals,
  plans: loadPlans,
  campaigns: loadCampaigns,
  crm: loadCrm,
  prompts: loadPrompts,
  status: loadStatusPanel,
  logs: loadLogs,
  audit: loadAudit,
  ops: loadOps,
  settings: loadSettings,
};

async function loadView(view) {
  state.view = view;
  document.querySelector(".workspace")?.scrollTo({top: 0, left: 0, behavior: "auto"});
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${view}`));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  const [breadcrumb, title] = VIEW_META[view] || ["Admin", document.querySelector(`.nav-item[data-view="${view}"]`)?.textContent || "Admin"];
  document.getElementById("viewBreadcrumb").textContent = breadcrumb;
  document.getElementById("viewTitle").textContent = title;
  document.body.classList.add("is-loading");
  const loadingWatchdog = setTimeout(() => document.body.classList.remove("is-loading"), 12000);
  renderViewMessage(view, "Carregando dados do painel...");
  try {
    await loaders[view]();
  } catch (err) {
    const message = err.message || "Nao foi possivel carregar esta area do painel.";
    renderViewMessage(view, message, true);
    showNotice(message, true);
  } finally {
    clearTimeout(loadingWatchdog);
    document.body.classList.remove("is-loading");
  }
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function openPromptEditModal(promptId) {
  const prompt = (state.cache.prompts || []).find((item) => item.prompt_id === promptId);
  if (!prompt) {
    showNotice("Prompt nao encontrado na lista carregada. Atualize a aba e tente novamente.", true);
    return;
  }
  const modal = document.getElementById("promptEditModal");
  const form = document.getElementById("promptEditForm");
  form.querySelector("[name=prompt_id]").value = prompt.prompt_id || "";
  form.querySelector("[name=name]").value = prompt.name || "";
  form.querySelector("[name=reading_type]").value = prompt.reading_type || "";
  form.querySelector("[name=version]").value = Number(prompt.version || 1);
  form.querySelector("[name=status]").value = prompt.status || "active";
  form.querySelector("[name=content]").value = prompt.content || "";
  modal.hidden = false;
  document.body.classList.add("modal-open");
  form.querySelector("[name=content]").focus();
}

function closePromptEditModal() {
  const modal = document.getElementById("promptEditModal");
  if (!modal) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  document.getElementById("promptEditForm")?.reset();
}

async function savePromptEdit(event) {
  event.preventDefault();
  const data = formData(event.target);
  const promptId = data.prompt_id;
  delete data.prompt_id;
  data.version = Number(data.version || 1);
  await request(`/admin/prompts/${promptId}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  });
  closePromptEditModal();
  showNotice("Prompt da Madame atualizado.");
  await loadPrompts();
}

function wireForms() {
  document.getElementById("planForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    data.price = Number(data.price || 0);
    data.credits = Number(data.credits || 0);
    data.duration_days = Number(data.duration_days || 30);
    data.benefits = String(data.benefits || "").split("\n").map((x) => x.trim()).filter(Boolean);
    await request("/admin/plans", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    showNotice("Plano criado.");
    await loadPlans();
  });

  document.getElementById("packageForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    data.price = Number(data.price || 0);
    data.credits = Number(data.credits || 0);
    data.bonus_credits = Number(data.bonus_credits || 0);
    await request("/admin/credit-packages", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    showNotice("Pacote criado.");
    await loadPlans();
  });

  document.getElementById("couponForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    data.discount_value = Number(data.discount_value || 0);
    data.max_uses = data.max_uses ? Number(data.max_uses) : null;
    await request("/admin/coupons", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    showNotice("Cupom criado.");
    await loadPlans();
  });

  document.getElementById("ritualForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    data.preco = Math.max(0, Math.round(Number(data.preco || 0)));
    data.ativo = Boolean(data.ativo);
    await request("/admin/rituals", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    event.target.querySelector("[name=ativo]").checked = true;
    showNotice("Ritual salvo.");
    await loadRituals();
  });

  document.getElementById("campaignForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    data.delay_minutes = Number(data.delay_minutes || 0);
    await request("/admin/campaigns", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    event.target.querySelector("[name=event_type]").value = "marketing";
    showNotice("Campanha criada.");
    await loadCampaigns();
  });

  document.getElementById("crmTagForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    await request("/admin/crm/tags", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    showNotice("Tag criada.");
    await loadCrm();
  });

  document.getElementById("crmSegmentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    try { data.rules = data.rules ? JSON.parse(data.rules) : {}; } catch { return showNotice("Regra JSON invalida.", true); }
    await request("/admin/crm/segments", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    showNotice("Segmento criado.");
    await loadCrm();
  });

  document.getElementById("crmTriggerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    await request("/admin/crm/triggers", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    event.target.querySelector("[name=event_type]").value = "segment_entry";
    showNotice("Gatilho criado.");
    await loadCrm();
  });

  document.getElementById("promptForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    await request("/admin/prompts", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
    event.target.reset();
    showNotice("Prompt criado.");
    await loadPrompts();
  });

  document.getElementById("maintenanceForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    await request("/admin/maintenance", {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({enabled: Boolean(data.enabled), message: data.message}),
    });
    showNotice("Modo manutencao atualizado.");
  });

  document.getElementById("settingForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    await request("/admin/settings", {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values: {[data.key]: {value: data.value, is_secret: Boolean(data.is_secret)}}}),
    });
    event.target.reset();
    showNotice("Configuracao salva.");
    await loadSettings();
  });

  document.getElementById("queueForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.target);
    await request("/admin/reprocess-queue", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({type: data.type})});
    showNotice("Item enfileirado.");
    await loadQueue();
  });
}

async function handleAction(event) {
  const target = event.target.closest("button");
  if (!target) return;
  const action = target.dataset.action;
  try {
    if (action && window[action]) return await window[action]();
    if (target.dataset.userDetail) {
      return loadUserDetail(target.dataset.userDetail);
    }
    if (target.dataset.userStatus) {
      await request(`/admin/users/${target.dataset.userStatus}/status`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: target.dataset.status, reason: "Alterado pelo painel admin"}),
      });
      showNotice("Status do usuario atualizado.");
      return loadUsers();
    }
    if (target.dataset.userCredits) {
      const amount = Number(prompt("Quantidade de creditos para adicionar/remover:", "1") || 0);
      if (!amount) return;
      await request(`/admin/users/${target.dataset.userCredits}/credits`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({amount: Math.abs(amount), type: amount > 0 ? "add" : "remove", reason: "Ajuste manual pelo painel"}),
      });
      showNotice("Creditos atualizados.");
      return loadUsers();
    }
    if (target.dataset.paymentApprove) {
      await request(`/admin/payments/${target.dataset.paymentApprove}/manual-approve`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason: "Aprovado manualmente pelo painel admin"}),
      });
      showNotice("Pagamento aprovado.");
      return loadPayments();
    }
    if (target.dataset.paymentReprocess) {
      await request(`/admin/payments/${target.dataset.paymentReprocess}/reprocess`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason: "Reprocessado pelo painel admin"}),
      });
      showNotice("Pagamento reprocessado.");
      return loadPayments();
    }
    if (target.dataset.messageResend) {
      const message = prompt("Mensagem personalizada opcional. Deixe em branco para usar a mensagem original/template:", "");
      await request(`/admin/messages/${target.dataset.messageResend}/resend`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: message || null}),
      });
      showNotice("Mensagem reenviada/processada.");
      return loadMessages();
    }
    if (target.dataset.ritualToggle) {
      await request(`/admin/rituals/${target.dataset.ritualToggle}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ativo: target.dataset.active === "true"}),
      });
      showNotice("Ritual atualizado.");
      return loadRituals();
    }
    if (target.dataset.campaignToggle) {
      await request(`/admin/campaigns/${target.dataset.campaignToggle}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: target.dataset.status}),
      });
      showNotice("Campanha atualizada.");
      return loadCampaigns();
    }
    if (target.dataset.crmDetail) {
      return loadCrmDetail(target.dataset.crmDetail);
    }
    if (target.dataset.crmTriggerToggle) {
      await request(`/admin/crm/triggers/${target.dataset.crmTriggerToggle}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: target.dataset.status}),
      });
      showNotice("Gatilho atualizado.");
      return loadCrm();
    }
    if (target.dataset.planDisable) {
      await request(`/admin/plans/${target.dataset.planDisable}`, {method: "DELETE"});
      showNotice("Plano desativado.");
      return loadPlans();
    }
    if (target.dataset.packageDisable) {
      await request(`/admin/credit-packages/${target.dataset.packageDisable}`, {method: "DELETE"});
      showNotice("Pacote desativado.");
      return loadPlans();
    }
    if (target.dataset.couponDisable) {
      await request(`/admin/coupons/${target.dataset.couponDisable}`, {method: "DELETE"});
      showNotice("Cupom desativado.");
      return loadPlans();
    }
    if (target.dataset.promptDisable) {
      await request(`/admin/prompts/${target.dataset.promptDisable}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: "inactive"}),
      });
      showNotice("Prompt desativado.");
      return loadPrompts();
    }
    if (target.dataset.promptEdit) {
      openPromptEditModal(target.dataset.promptEdit);
      return;
    }
    if (target.dataset.queueDone) {
      await request(`/admin/reprocess-queue/${target.dataset.queueDone}/status`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: "done"}),
      });
      showNotice("Item concluido.");
      return loadQueue();
    }
    if (target.dataset.alertResolve) {
      await request(`/admin/alerts/${target.dataset.alertResolve}/status`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status: "resolved"}),
      });
      showNotice("Alerta resolvido.");
      return state.view === "status" ? loadStatusPanel() : loadAlerts();
    }
  } catch (err) {
    showNotice(err.message, true);
  }
}

async function handleSubmit(event) {
  const noteForm = event.target.closest("[data-crm-note-form]");
  if (!noteForm) return;
  event.preventDefault();
  const data = formData(noteForm);
  await request(`/admin/crm/users/${noteForm.dataset.crmNoteForm}/notes`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  });
  showNotice("Nota salva.");
  await loadCrmDetail(noteForm.dataset.crmNoteForm);
}

async function recoverPix() {
  await request("/admin/payments/recover-abandoned", {method: "POST"});
  showNotice("PIX abandonados verificados e alertas criados.");
  await loadPayments();
}

async function classifyCrm() {
  await request("/admin/crm/classify", {method: "POST"});
  showNotice("Clientes classificados em segmentos.");
  await loadCrm();
}

async function exportCrm() {
  const response = await fetch(`${ADMIN_BASE}/admin/crm/export.csv`, {headers: adminHeaders()});
  if (!response.ok) throw new Error("Nao foi possivel exportar o CRM.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "madame-do-luar-crm.csv";
  a.click();
  URL.revokeObjectURL(url);
}

async function runDailyCheck() {
  await request("/admin/operations/daily-check", {method: "POST"});
  showNotice("Verificacao diaria executada e registrada.");
  await loadStatusPanel();
}

window.loadUsers = loadUsers;
window.loadReadings = loadReadings;
window.loadPayments = loadPayments;
window.loadMessages = loadMessages;
window.loadRituals = loadRituals;
window.loadCampaigns = loadCampaigns;
window.loadCrm = loadCrm;
window.loadPrompts = loadPrompts;
window.loadStatusPanel = loadStatusPanel;
window.loadLogs = loadLogs;
window.loadAudit = loadAudit;
window.loadQueue = loadQueue;
window.loadErrors = loadErrors;
window.loadHotUsers = loadHotUsers;
window.generateAlerts = generateAlerts;
window.recoverPix = recoverPix;
window.classifyCrm = classifyCrm;
window.exportCrm = exportCrm;
window.runDailyCheck = runDailyCheck;
window.login = login;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("adminLogout").addEventListener("click", logout);
  document.getElementById("refreshBtn").addEventListener("click", () => loadView(state.view));
  document.getElementById("globalSearch").addEventListener("input", () => loadView(state.view));
  document.querySelectorAll("[data-filter]").forEach((el) => el.addEventListener("input", () => loadView(state.view)));
  document.querySelectorAll("[data-filter]").forEach((el) => el.addEventListener("change", () => loadView(state.view)));
  document.querySelectorAll(".nav-item").forEach((btn) => btn.addEventListener("click", () => loadView(btn.dataset.view)));
  document.getElementById("promptEditForm").addEventListener("submit", savePromptEdit);
  document.querySelectorAll("[data-modal-close]").forEach((el) => el.addEventListener("click", closePromptEditModal));
  document.getElementById("promptEditModal").addEventListener("click", (event) => {
    if (event.target.id === "promptEditModal") closePromptEditModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !document.getElementById("promptEditModal").hidden) closePromptEditModal();
  });
  document.body.addEventListener("click", handleAction);
  document.body.addEventListener("submit", handleSubmit);
  wireForms();
  requireAdminSession();
});
