const API_BASE = (() => {
  const localApi = `${"http://"}${"local"}${"host"}:${8000}/api`;
  if (window.location.protocol === "file:") return localApi;
  return "/api";
})();

const ADMIN_URL = (() => {
  if (window.location.protocol === "file:") return `${"http://"}${"local"}${"host"}:${8000}/admin.html`;
  return "/admin.html";
})();

const CARD_ASSET_BASE = "/imagems/cartas";
const CARD_BACK_IMAGE = "/assets/optimized/card-back.webp";
const ARCANO_MAJOR = [
  {numero: 0, nome: "O Louco", symbol: "&#10022;", image: `${CARD_ASSET_BASE}/parte%20da%20frente%20das%20cartas/CARTA-00.png`},
  {numero: 1, nome: "O Mago", symbol: "&#10026;", image: `${CARD_ASSET_BASE}/parte%20da%20frente%20das%20cartas/CARTA-01.png`},
  {numero: 2, nome: "A Sacerdotisa", aliases: ["Sacerdotisa"], symbol: "&#9789;", image: `${CARD_ASSET_BASE}/parte%20da%20frente%20das%20cartas/CARTA-02.png`},
  {numero: 3, nome: "A Imperatriz", symbol: "&#10048;"},
  {numero: 4, nome: "O Imperador", symbol: "&#9819;"},
  {numero: 5, nome: "O Hierofante", symbol: "&#10013;"},
  {numero: 6, nome: "Os Enamorados", aliases: ["Enamorados"], symbol: "&#9829;"},
  {numero: 7, nome: "O Carro", symbol: "&#10070;"},
  {numero: 8, nome: "A Forca", aliases: ["A For\u00c3\u00a7a", "A Força"], symbol: "&#10038;"},
  {numero: 9, nome: "O Eremita", symbol: "&#10041;"},
  {numero: 10, nome: "A Roda da Fortuna", symbol: "&#9711;"},
  {numero: 11, nome: "A Justica", aliases: ["A Justi\u00c3\u00a7a", "A Justiça"], symbol: "&#9878;"},
  {numero: 12, nome: "O Enforcado", symbol: "&#9790;"},
  {numero: 13, nome: "A Morte", symbol: "&#10013;"},
  {numero: 14, nome: "A Temperanca", aliases: ["A Temperan\u00c3\u00a7a", "A Temperança"], symbol: "&#10023;"},
  {numero: 15, nome: "O Diabo", symbol: "&#9889;"},
  {numero: 16, nome: "A Torre", symbol: "&#9962;"},
  {numero: 17, nome: "A Estrela", symbol: "&#10022;"},
  {numero: 18, nome: "A Lua", symbol: "&#9790;"},
  {numero: 19, nome: "O Sol", symbol: "&#9728;"},
  {numero: 20, nome: "O Julgamento", symbol: "&#10021;"},
  {numero: 21, nome: "O Mundo", symbol: "&#9673;"},
];

function normalizarCartaNome(nome = "") {
  return String(nome)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[\u00c3ã]/g, "a")
    .replace(/[Çç]/g, "c")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function obterArcano(nome) {
  const alvo = normalizarCartaNome(nome);
  return ARCANO_MAJOR.find((card) => {
    const nomes = [card.nome, ...(card.aliases || [])];
    return nomes.some((item) => normalizarCartaNome(item) === alvo);
  }) || null;
}

function caminhoImagemArcano(arcano = {}) {
  if (arcano.image) return arcano.image;
  if (arcano.numero == null) return "";
  const numero = String(arcano.numero).padStart(2, "0");
  return `${CARD_ASSET_BASE}/parte%20da%20frente%20das%20cartas/CARTA-${numero}.png`;
}

function aplicarArteCarta(carta = {}, imageId, containerSelector) {
  const arcano = obterArcano(carta.nome) || {};
  const img = document.getElementById(imageId);
  const container = img?.closest(containerSelector);
  if (!img || !container) return;

  const image = caminhoImagemArcano(arcano);
  container.style.setProperty("--card-back-image", `url("${CARD_BACK_IMAGE}")`);
  container.dataset.cardNumber = arcano.numero ?? "";
  container.dataset.cardTitle = carta.nome || arcano.nome || "Arcano";
  container.dataset.cardSymbol = carta.symbol || arcano.symbol || "☽";
  container.classList.remove("arcano-has-image", "arcano-generated");

  if (image) {
    img.onload = () => {
      img.hidden = false;
      container.classList.add("arcano-has-image");
      container.classList.remove("arcano-generated");
    };
    img.onerror = () => {
      img.hidden = true;
      img.removeAttribute("src");
      container.classList.remove("arcano-has-image");
      container.classList.add("arcano-generated");
    };
    img.src = image;
  } else {
    img.removeAttribute("src");
    img.hidden = true;
    container.classList.add("arcano-generated");
  }
}

function escapeText(value) {
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

async function apiFetch(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {credentials: "include", ...options});
  let data = {};
  try { data = await resp.json(); } catch {}
  return {resp, data};
}

const analyticsState = {
  sessionId: localStorage.getItem("mdl_analytics_session") || window.crypto?.randomUUID?.() || `s_${Date.now()}_${Math.random().toString(16).slice(2)}`,
  anonymousId: localStorage.getItem("mdl_analytics_anonymous") || window.crypto?.randomUUID?.() || `a_${Date.now()}_${Math.random().toString(16).slice(2)}`,
};
localStorage.setItem("mdl_analytics_session", analyticsState.sessionId);
localStorage.setItem("mdl_analytics_anonymous", analyticsState.anonymousId);

function trackEvent(eventName, metadata = {}, entity = {}) {
  const payload = {
    event_name: eventName,
    session_id: analyticsState.sessionId,
    anonymous_id: analyticsState.anonymousId,
    page_url: window.location.href,
    referrer: document.referrer || null,
    source: "frontend",
    entity_type: entity.type || null,
    entity_id: entity.id || null,
    metadata,
  };
  fetch(`${API_BASE}/analytics/events`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  }).catch(() => {});
}

const perfilState = {
  view: "dashboard",
  profile: null,
  readings: [],
  credits: null,
  payments: [],
};

let ultimaLeituraResultado = null;

/* ════ SESSÃO ════ */
function getSession() { try { return JSON.parse(localStorage.getItem("mdl_session")); } catch { return null; } }
function salvarSession(data) {
  localStorage.setItem("mdl_session", JSON.stringify({
    usuario: data.usuario,
    expires_at: Date.now() + ((data.expires_in || 86400) * 1000)
  }));
}
function limparSession() { localStorage.removeItem("mdl_session"); }
function getUsuario() {
  const sess = getSession();
  return sess?.usuario || (sess?.user_id ? sess : null);
}
function getToken() { return getSession()?.usuario ? "cookie-session" : null; }
function authHeaders(extra = {}) {
  return {...extra};
}
function atualizarSessionUsuario(usuario) {
  const sess = getSession();
  if (!sess) return;
  localStorage.setItem("mdl_session", JSON.stringify({...sess, usuario: {...(sess.usuario || {}), ...(usuario || {})}}));
}

function obterIniciaisUsuario(usuario = {}) {
  const fonte = (usuario.nome || usuario.email || "Madame do Luar").trim();
  const partes = fonte.split(/\s+/).filter(Boolean);
  if (partes.length >= 2) {
    return `${partes[0][0]}${partes[partes.length - 1][0]}`.toUpperCase();
  }
  return fonte.slice(0, 2).toUpperCase();
}

function obterAvatarUrl(usuario = {}) {
  return usuario.avatar_url || usuario.avatarUrl || usuario.foto || usuario.foto_url || "";
}

function atualizarAvatar(prefixo, usuario = {}) {
  const img = document.getElementById(`${prefixo}AvatarImg`);
  const fallback = document.getElementById(`${prefixo}AvatarFallback`);
  if (!img || !fallback) return;

  const nome = usuario.nome || usuario.email || "Usuario";
  const avatarUrl = obterAvatarUrl(usuario);
  fallback.textContent = obterIniciaisUsuario(usuario);

  if (avatarUrl) {
    img.src = avatarUrl;
    img.alt = `Foto de ${nome}`;
    img.hidden = false;
    img.onerror = () => {
      img.hidden = true;
      img.removeAttribute("src");
    };
  } else {
    img.hidden = true;
    img.removeAttribute("src");
    img.alt = "";
  }
}

function saldoUsuarioAtual() {
  const usuario = getUsuario() || {};
  const saldo = perfilState.credits?.credits_balance ?? usuario.credits_balance ?? 0;
  return Number.isFinite(Number(saldo)) ? Number(saldo) : 0;
}

function atualizarHeaderSaldo(saldo = saldoUsuarioAtual()) {
  const el = document.getElementById("headerCreditsSaldo");
  if (!el) return;
  el.textContent = Number(saldo || 0).toLocaleString("pt-BR");
}

let headerSaldoSyncing = false;
async function sincronizarSaldoHeader() {
  if (!getToken() || headerSaldoSyncing) return;
  headerSaldoSyncing = true;
  try {
    const {resp, data} = await apiFetch("/me/credits", {headers: authHeaders()});
    if (!resp.ok) return;
    perfilState.credits = data;
    atualizarSessionUsuario({credits_balance: data.credits_balance ?? 0});
    atualizarHeaderSaldo(data.credits_balance ?? 0);
  } catch {
    atualizarHeaderSaldo();
  } finally {
    headerSaldoSyncing = false;
  }
}

function urlImagemValida(url) {
  const value = (url || "").trim();
  if (!value) return true;
  try {
    const parsed = new URL(value);
    return ["http:", "https:"].includes(parsed.protocol);
  } catch {
    return false;
  }
}

function aplicarPreviewAvatar(imgId, fallbackId, nome, avatarUrl) {
  const img = document.getElementById(imgId);
  const fallback = document.getElementById(fallbackId);
  if (!img || !fallback) return;
  fallback.textContent = obterIniciaisUsuario({nome});
  if (avatarUrl && urlImagemValida(avatarUrl)) {
    img.src = avatarUrl;
    img.alt = `Imagem de perfil de ${nome || "usuario"}`;
    img.hidden = false;
    img.onerror = () => {
      img.hidden = true;
      img.removeAttribute("src");
    };
  } else {
    img.hidden = true;
    img.removeAttribute("src");
    img.alt = "";
  }
}

function atualizarPerfilAvatarPreview() {
  aplicarPreviewAvatar(
    "perfilEditAvatarPreviewImg",
    "perfilEditAvatarPreviewFallback",
    document.getElementById("perfilNome")?.value || getUsuario()?.nome || "Madame do Luar",
    document.getElementById("perfilAvatarUrl")?.value || ""
  );
}

function atualizarHeader() {
  const u = getUsuario();
  if (u) {
    document.getElementById("headerVisitante").style.display = "none";
    document.getElementById("headerLogado").style.display   = "flex";
    document.getElementById("headerNome").textContent = "🌙 " + u.nome;
    document.getElementById("headerNome").textContent = u.nome || "Minha conta";
    atualizarHeaderSaldo();
    atualizarLinksAdmin(u);
    atualizarAvatar("header", u);
    sincronizarSaldoHeader();
    document.getElementById("consultaGate").style.display = "none";
    document.getElementById("consultaArea").style.display  = "block";
    document.getElementById("perguntaInput")?.focus({preventScroll: true});
  } else {
    document.getElementById("headerVisitante").style.display = "block";
    document.getElementById("headerLogado").style.display   = "none";
    atualizarLinksAdmin(null);
    document.getElementById("consultaGate").style.display = "block";
    document.getElementById("consultaArea").style.display  = "none";
  }
}

function atualizarLinksAdmin(usuario) {
  const isAdmin = ["admin", "super_admin"].includes(usuario?.role);
  document.querySelectorAll(".admin-only-link").forEach((el) => {
    el.style.display = isAdmin ? "inline-flex" : "none";
    if (isAdmin) el.setAttribute("href", ADMIN_URL);
  });
}

function abrirPainelAdmin(event) {
  if (event) event.preventDefault();
  window.location.href = ADMIN_URL;
}

function logout() {
  apiFetch("/auth/logout", {method: "POST"}).catch(() => {});
  limparSession();
  atualizarHeader();
  mostrarToast("Até logo! Que a Lua ilumine seu caminho.");
}

/* ════ AUTH GATE ════ */
function authGuard(event, destino) {
  if (!getToken()) { event.preventDefault(); trackEvent("signup_started", {entry: destino || "auth_guard"}); abrirAuth('cadastro'); }
}
function authGuardCarta() {
  trackEvent("daily_card_started");
  if (!getToken()) { trackEvent("signup_started", {entry: "daily_card"}); abrirAuth('cadastro'); return; }
  revelarCarta();
}

/* ════ MODAL AUTH ════ */
function abrirAuth(aba) {
  document.getElementById("authOverlay").style.display = "flex";
  document.body.style.overflow = "hidden";
  if ((aba || "login") === "cadastro") trackEvent("signup_started", {entry: "auth_modal"});
  mudarTab(aba || 'login');
}
function fecharAuthModal(event) {
  if (event && event.target !== document.getElementById("authOverlay")) return;
  document.getElementById("authOverlay").style.display = "none";
  document.body.style.overflow = "";
}
function mudarTab(aba) {
  const isCad = aba === 'cadastro';
  document.getElementById("formCadastro").style.display = isCad ? "block" : "none";
  document.getElementById("formLogin").style.display    = isCad ? "none"  : "block";
  document.getElementById("tabCadastro").classList.toggle("active", isCad);
  document.getElementById("tabLogin").classList.toggle("active", !isCad);
  document.getElementById("erroCadastro").style.display = "none";
  document.getElementById("erroLogin").style.display    = "none";
}
function toggleSenha(id) {
  const el = document.getElementById(id);
  el.type = el.type === "password" ? "text" : "password";
}

function mensagemErroAmigavel(msg) {
  const texto = typeof msg === "string" ? msg : (msg?.message || msg?.detail || "");
  const lower = texto.toLowerCase();
  if (lower.includes("users_whatsapp_key") || (lower.includes("duplicate key") && lower.includes("whatsapp"))) {
    return "Este numero de WhatsApp ja esta cadastrado no sistema. Altere para outro numero ou entre na sua conta.";
  }
  if (lower.includes("users_email_key") || (lower.includes("duplicate key") && lower.includes("email"))) {
    return "Este e-mail ja esta cadastrado. Entre na sua conta ou use outro e-mail.";
  }
  return texto || "Nao foi possivel concluir a acao.";
}

function sessaoExpirada() {
  limparSession();
  atualizarHeader();
  fecharPerfilModal();
  abrirAuth('login');
}

async function abrirPerfil(view = "dashboard") {
  if (!getToken()) { abrirAuth('login'); return; }
  document.getElementById("perfilOverlay").style.display = "flex";
  document.body.style.overflow = "hidden";
  mudarPerfilView(view || "dashboard");
  preencherPerfil({usuario: getUsuario(), metricas: {}});
  await carregarPerfil();
  await carregarPainelPerfil();
  if (view && view !== perfilState.view) mudarPerfilView(view);
}

function fecharPerfilModal(event) {
  if (event && event.target !== document.getElementById("perfilOverlay")) return;
  document.getElementById("perfilOverlay").style.display = "none";
  document.body.style.overflow = "";
}

function mudarPerfilView(view) {
  perfilState.view = view || "dashboard";
  document.querySelectorAll("[data-perfil-view]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.perfilView === perfilState.view);
  });
  document.querySelectorAll(".perfil-view").forEach((section) => {
    section.classList.toggle("active", section.id === `perfilView${capitalizePerfilView(perfilState.view)}`);
  });
  if (perfilState.view === "configuracoes") mudarPerfilTab("dados");
  if (["dashboard", "historico", "creditos"].includes(perfilState.view)) {
    renderPerfilPanels();
  }
}

function capitalizePerfilView(view) {
  const map = {
    dashboard: "Dashboard",
    historico: "Historico",
    creditos: "Creditos",
    configuracoes: "Configuracoes",
  };
  return map[view] || "Dashboard";
}

function mudarPerfilTab(tab) {
  if (perfilState.view !== "configuracoes") mudarPerfilView("configuracoes");
  const dados = tab === 'dados';
  document.getElementById("perfilFormDados").style.display = dados ? "grid" : "none";
  document.getElementById("perfilFormSeguranca").style.display = dados ? "none" : "grid";
  document.getElementById("perfilTabDados").classList.toggle("active", dados);
  document.getElementById("perfilTabSeguranca").classList.toggle("active", !dados);
  document.getElementById("erroPerfil").style.display = "none";
  document.getElementById("erroSenha").style.display = "none";
}

function preencherPerfil(data) {
  perfilState.profile = data || perfilState.profile;
  const u = data?.usuario || {};
  const assinatura = data?.assinatura || null;
  const metricas = data?.metricas || {};
  const nome = u.nome || "Minha conta";

  atualizarAvatar("perfil", u);
  document.getElementById("perfilNomeTitulo").textContent = nome;
  document.getElementById("perfilEmail").textContent = u.email || "";
  document.getElementById("perfilNome").value = u.nome || "";
  document.getElementById("perfilEmailInput").value = u.email || "";
  const perfilAvatarUrl = document.getElementById("perfilAvatarUrl");
  if (perfilAvatarUrl) perfilAvatarUrl.value = obterAvatarUrl(u);
  atualizarPerfilAvatarPreview();
  document.getElementById("perfilWhatsapp").value = u.whatsapp || "";
  const whatsappOptIn = document.getElementById("perfilWhatsappOptIn");
  if (whatsappOptIn) whatsappOptIn.checked = u.whatsapp_opt_in !== false && !!u.whatsapp;
  const emailOptIn = document.getElementById("perfilEmailOptIn");
  if (emailOptIn) emailOptIn.checked = !!u.email_opt_in;
  document.getElementById("perfilPlano").textContent = assinatura?.plano || (u.assinante ? "Assinante" : "Gratuito");
  const statusAssinatura = document.getElementById("perfilStatusAssinatura");
  if (statusAssinatura) {
    statusAssinatura.textContent = assinatura?.status || (u.assinante ? "ativo" : "sem assinatura");
  }
  document.getElementById("perfilRenovacao").textContent = assinatura?.renovacao ? formatarData(assinatura.renovacao) : "--";
  const cancelarBtn = document.getElementById("btnCancelarAssinatura");
  if (cancelarBtn) {
    cancelarBtn.style.display = assinatura?.status === "ativo" ? "block" : "none";
  }
  const cancelReasonLabel = document.getElementById("cancelReasonLabel");
  if (cancelReasonLabel) {
    cancelReasonLabel.style.display = assinatura?.status === "ativo" ? "grid" : "none";
  }
  document.getElementById("perfilMetricLeituras").textContent = metricas.leituras || 0;
  document.getElementById("perfilMetricCartas").textContent = metricas.cartas_do_dia || 0;
  document.getElementById("perfilMetricMensagens").textContent = metricas.mensagens || 0;
  const totalAtividade = Number(metricas.leituras || 0) + Number(metricas.cartas_do_dia || 0) + Number(metricas.mensagens || 0);
  const progresso = Math.max(0, Math.min(100, Math.round((totalAtividade / 12) * 100)));
  const progressValue = document.getElementById("perfilProgressValue");
  const progressRing = document.getElementById("perfilProgressRing");
  const levelEl = document.getElementById("perfilNivelEspiritual");
  const streakEl = document.getElementById("perfilStreak");
  const perfilModal = document.getElementById("perfilModal");
  const nivel = progresso >= 85
    ? "Oraculo Interior"
    : progresso >= 58
      ? "Guardiao Astral"
      : progresso >= 28
        ? "Explorador Intuitivo"
        : "Iniciante Lunar";
  const streak = Math.max(0, Math.min(30, Number(metricas.cartas_do_dia || 0)));
  if (progressValue) progressValue.textContent = `${progresso}%`;
  if (progressRing) progressRing.textContent = progresso;
  if (levelEl) levelEl.textContent = nivel;
  if (streakEl) streakEl.textContent = `${streak} ${streak === 1 ? "dia" : "dias"}`;
  if (perfilModal) perfilModal.style.setProperty("--perfil-progress", `${progresso}%`);
  atualizarJornadaPerfil(metricas, progresso, nivel);
}

function getPerfilFavoritos() {
  const userId = getUsuario()?.user_id || getUsuario()?.id || "anon";
  try { return JSON.parse(localStorage.getItem(`mdl_favoritos_${userId}`)) || []; } catch { return []; }
}

function setPerfilFavoritos(items) {
  const userId = getUsuario()?.user_id || getUsuario()?.id || "anon";
  localStorage.setItem(`mdl_favoritos_${userId}`, JSON.stringify(items || []));
}

function formatarDataHora(valor) {
  if (!valor) return "--";
  const normalizado = String(valor).includes("T") ? valor : `${valor}T00:00:00`;
  const data = new Date(normalizado);
  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString("pt-BR");
}

function itemListaPerfil(titulo, texto, meta = "", extra = "") {
  return `<div>${extra}<span>${escapeText(titulo || "--")}</span><small>${escapeText(texto || "")}${meta ? `<br>${escapeText(meta)}` : ""}</small></div>`;
}

function atualizarJornadaPerfil(metricas = {}, progresso = 0, nivel = "Iniciante Lunar") {
  const progressoEl = document.getElementById("perfilJornadaProgresso");
  const ringEl = document.getElementById("perfilJornadaRing");
  const nivelEl = document.getElementById("perfilJornadaNivel");
  const resumoEl = document.getElementById("perfilJornadaResumo");
  if (progressoEl) progressoEl.textContent = `${progresso}%`;
  if (ringEl) ringEl.textContent = progresso;
  if (nivelEl) nivelEl.textContent = nivel;
  if (resumoEl) {
    resumoEl.textContent = `${Number(metricas.leituras || 0)} leituras, ${Number(metricas.cartas_do_dia || 0)} cartas do dia e ${Number(metricas.mensagens || 0)} mensagens ja alimentam sua jornada.`;
  }
}

function renderPerfilPanels() {
  const leituras = perfilState.readings || [];
  const pagamentos = perfilState.payments || [];
  const creditos = perfilState.credits || {};
  const favoritos = getPerfilFavoritos();

  const recentEl = document.getElementById("perfilRecentReadings");
  if (recentEl) {
    setSafeHTML(recentEl, leituras.slice(0, 3).map((r) => itemListaPerfil(
      r.pergunta || "Leitura registrada",
      r.tema || r.emocao || "Pergunta salva no historico",
      formatarDataHora(r.criado_em)
    )).join("") || itemListaPerfil("Primeira leitura", "Disponivel apos sua proxima consulta"));
  }

  const historicoLista = document.getElementById("perfilHistoricoLista");
  const historicoCount = document.getElementById("perfilHistoricoCount");
  if (historicoCount) historicoCount.textContent = leituras.length;
  if (historicoLista) {
    setSafeHTML(historicoLista, leituras.map((r) => itemListaPerfil(
      r.pergunta || "Leitura registrada",
      r.tema || r.emocao || "Sem tema informado",
      formatarDataHora(r.criado_em)
    )).join("") || itemListaPerfil("Nenhuma leitura ainda", "Faca uma nova consulta para alimentar seu historico."));
  }

  const pagamentosLista = document.getElementById("perfilPagamentosLista");
  const pagamentosCount = document.getElementById("perfilPagamentosCount");
  if (pagamentosCount) pagamentosCount.textContent = pagamentos.length;
  if (pagamentosLista) {
    setSafeHTML(pagamentosLista, pagamentos.slice(0, 12).map((p) => itemListaPerfil(
      p.product_name || p.tipo || p.product_type || "Pagamento",
      `${moneyBR(p.amount || p.valor || 0)} - ${p.status || "pendente"}`,
      formatarDataHora(p.created_at || p.approved_at)
    )).join("") || itemListaPerfil("Nenhum pagamento registrado", "Suas compras e assinaturas aparecerao aqui."));
  }

  const favLista = document.getElementById("perfilFavoritosLista");
  if (favLista) {
    setSafeHTML(favLista, favoritos.map((f) => itemListaPerfil(
      f.titulo || "Insight salvo",
      f.texto || "",
      formatarDataHora(f.created_at),
      `<button class="perfil-inline-action" type="button" onclick="removerFavoritoPerfil('${f.id}')">Remover</button>`
    )).join("") || itemListaPerfil("Nenhum favorito salvo", "Use o botao Favoritar depois de uma leitura ou no historico."));
  }

  const saldoEl = document.getElementById("perfilCreditosSaldo");
  const creditosCount = document.getElementById("perfilCreditosCount");
  const creditosLista = document.getElementById("perfilCreditosLista");
  if (saldoEl) saldoEl.textContent = creditos.credits_balance ?? perfilState.profile?.usuario?.credits_balance ?? 0;
  if (creditosCount) creditosCount.textContent = (creditos.transactions || []).length;
  if (creditosLista) {
    setSafeHTML(creditosLista, (creditos.transactions || []).map((t) => itemListaPerfil(
      `${Number(t.amount || 0) > 0 ? "+" : ""}${t.amount || 0} creditos`,
      t.reason || t.type || "Movimentacao",
      formatarDataHora(t.created_at)
    )).join("") || itemListaPerfil("Sem movimentacao", "Compras, bonus e consumo de leituras aparecerao aqui."));
  }

  const padroes = document.getElementById("perfilJornadaPadroes");
  if (padroes) {
    const temas = {};
    leituras.forEach((r) => {
      const tema = (r.tema || r.emocao || "geral").toLowerCase();
      temas[tema] = (temas[tema] || 0) + 1;
    });
    const rows = Object.entries(temas).sort((a, b) => b[1] - a[1]).slice(0, 6);
    setSafeHTML(padroes, rows.map(([tema, total]) => itemListaPerfil(tema, `${total} recorrencia${total === 1 ? "" : "s"}`)).join("") ||
      itemListaPerfil("Padroes em formacao", "Novas leituras vao revelar temas recorrentes."));
  }
}

async function carregarPainelPerfil(force = false) {
  if (!getToken()) return;
  if (!force && perfilState.readings.length && perfilState.credits) {
    renderPerfilPanels();
    return;
  }
  try {
    const [readingsResp, creditsResp, paymentsResp] = await Promise.all([
      apiFetch("/me/readings", {headers: authHeaders()}),
      apiFetch("/me/credits", {headers: authHeaders()}),
      apiFetch("/me/payments", {headers: authHeaders()}),
    ]);
    if ([readingsResp, creditsResp, paymentsResp].some((item) => item.resp.status === 401)) {
      sessaoExpirada();
      return;
    }
    perfilState.readings = readingsResp.resp.ok ? (readingsResp.data.readings || []) : [];
    perfilState.credits = creditsResp.resp.ok ? creditsResp.data : {transactions: []};
    if (creditsResp.resp.ok) {
      atualizarSessionUsuario({credits_balance: creditsResp.data.credits_balance ?? 0});
      atualizarHeaderSaldo(creditsResp.data.credits_balance ?? 0);
    }
    perfilState.payments = paymentsResp.resp.ok ? (paymentsResp.data.payments || []) : [];
    renderPerfilPanels();
  } catch {
    renderPerfilPanels();
    mostrarToast("Nao foi possivel sincronizar todos os paineis agora.");
  }
}

function favoritarHistoricoPerfil(questionId) {
  const item = (perfilState.readings || []).find((r) => r.question_id === questionId);
  if (!item) return;
  salvarFavoritoPerfil({
    id: questionId,
    titulo: item.pergunta || "Leitura favorita",
    texto: item.tema || item.emocao || "Registro salvo do historico",
    created_at: item.criado_em || new Date().toISOString(),
  });
}

function salvarFavoritoPerfil(item = null) {
  const favorito = item || ultimaLeituraResultado;
  if (!favorito) {
    mostrarToast("Nenhuma leitura disponivel para favoritar ainda.");
    return;
  }
  const favoritos = getPerfilFavoritos();
  const id = favorito.id || favorito.question_id || favorito.reading_id || `fav_${Date.now()}`;
  const semDuplicado = favoritos.filter((f) => f.id !== id);
  semDuplicado.unshift({...favorito, id, created_at: favorito.created_at || new Date().toISOString()});
  setPerfilFavoritos(semDuplicado.slice(0, 40));
  mostrarToast("Insight salvo nos favoritos.");
  renderPerfilPanels();
}

function removerFavoritoPerfil(id) {
  setPerfilFavoritos(getPerfilFavoritos().filter((f) => f.id !== id));
  renderPerfilPanels();
}

function limparFavoritosPerfil() {
  if (!confirm("Remover todos os favoritos salvos neste navegador?")) return;
  setPerfilFavoritos([]);
  renderPerfilPanels();
}

function initPerfilNavigation() {
  document.querySelectorAll("[data-perfil-view]").forEach((btn) => {
    btn.addEventListener("click", () => mudarPerfilView(btn.dataset.perfilView));
  });
  document.getElementById("perfilNome")?.addEventListener("input", atualizarPerfilAvatarPreview);
  document.getElementById("perfilAvatarUrl")?.addEventListener("input", atualizarPerfilAvatarPreview);
}

function formatarData(valor) {
  try {
    return new Date(valor + "T00:00:00").toLocaleDateString("pt-BR");
  } catch {
    return valor || "--";
  }
}

async function carregarPerfil() {
  try {
    const {resp, data} = await apiFetch("/perfil", {headers: authHeaders()});
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) { mostrarToast(data.detail || "Nao foi possivel carregar o perfil."); return; }
    atualizarSessionUsuario(data.usuario);
    atualizarHeader();
    preencherPerfil(data);
  } catch {
    mostrarToast("Servico de perfil indisponivel no momento.");
  }
}

async function salvarPerfil(event) {
  event.preventDefault();
  const erroEl = document.getElementById("erroPerfil");
  const btn = document.getElementById("btnSalvarPerfil");
  const nome = document.getElementById("perfilNome").value.trim();
  const avatar_url = document.getElementById("perfilAvatarUrl")?.value.trim() || "";
  const whatsapp = document.getElementById("perfilWhatsapp").value.trim();
  const whatsappOptInEl = document.getElementById("perfilWhatsappOptIn");
  const whatsapp_opt_in = !!(whatsapp && whatsappOptInEl && whatsappOptInEl.checked);
  const emailOptInEl = document.getElementById("perfilEmailOptIn");
  const email_opt_in = !!(emailOptInEl && emailOptInEl.checked);

  erroEl.style.display = "none";
  if (nome.length < 2) { mostrarErro(erroEl, "Informe um nome com pelo menos 2 caracteres."); return; }
  if (!urlImagemValida(avatar_url)) { mostrarErro(erroEl, "Informe uma URL de imagem valida com http ou https."); return; }

  btn.textContent = "Salvando..."; btn.disabled = true;
  try {
    const {resp, data} = await apiFetch("/perfil", {
      method: "PATCH",
      headers: authHeaders({"Content-Type":"application/json"}),
      body: JSON.stringify({nome, avatar_url: avatar_url || null, whatsapp, whatsapp_opt_in, email_opt_in})
    });
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) { mostrarErro(erroEl, mensagemErroAmigavel(data.detail || data.error)); return; }
    atualizarSessionUsuario(data.usuario);
    atualizarHeader();
    preencherPerfil(data);
    trackEvent("profile_updated", {whatsapp_opt_in, email_opt_in}, {type: "users", id: data.usuario?.user_id});
    if (whatsapp_opt_in) trackEvent("whatsapp_opt_in", {}, {type: "users", id: data.usuario?.user_id});
    else trackEvent("whatsapp_opt_out", {}, {type: "users", id: data.usuario?.user_id});
    if (email_opt_in) trackEvent("email_opt_in", {}, {type: "users", id: data.usuario?.user_id});
    mostrarToast("Perfil atualizado com sucesso.");
  } catch {
    mostrarErro(erroEl, "Servico temporariamente indisponivel.");
  } finally {
    btn.textContent = "Salvar Perfil"; btn.disabled = false;
  }
}

async function cancelarAssinatura() {
  const reasonSelect = document.getElementById("cancelReason");
  const reason = reasonSelect?.value || "nao_informado";
  if (!confirm("Cancelar sua assinatura ativa? O acesso sera atualizado no seu perfil.")) return;
  const btn = document.getElementById("btnCancelarAssinatura");
  if (btn) { btn.disabled = true; btn.textContent = "Cancelando..."; }
  try {
    const {resp, data} = await apiFetch("/subscription/cancel", {
      method: "POST",
      headers: authHeaders({"Content-Type": "application/json"}),
      body: JSON.stringify({reason})
    });
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) {
      mostrarToast(data.detail || "Nao foi possivel cancelar a assinatura.");
      return;
    }
    mostrarToast("Assinatura cancelada com sucesso.");
    trackEvent("subscription_cancel_requested", {source: "profile", reason});
    trackEvent("subscription_cancelled", {source: "profile", reason});
    await carregarPerfil();
  } catch {
    mostrarToast("Servico de assinatura indisponivel no momento.");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Cancelar assinatura"; }
  }
}

async function exportarMeusDados() {
  if (!getToken()) { abrirAuth("login"); return; }
  try {
    const resp = await fetch(`${API_BASE}/lgpd/export`, {headers: authHeaders(), credentials: "include"});
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      mostrarToast(data.detail || "Nao foi possivel exportar seus dados.");
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "madame-do-luar-dados.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    mostrarToast("Exportacao de dados gerada.");
  } catch {
    mostrarToast("Servico de exportacao indisponivel no momento.");
  }
}

async function excluirMinhaConta() {
  if (!getToken()) { abrirAuth("login"); return; }
  const confirmation = prompt("Para excluir sua conta, digite EXCLUIR.");
  if (!confirmation) return;
  const reason = prompt("Motivo opcional da exclusao:") || null;
  try {
    const {resp, data} = await apiFetch("/lgpd/account", {
      method: "DELETE",
      headers: authHeaders({"Content-Type": "application/json"}),
      body: JSON.stringify({confirmation, reason})
    });
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) { mostrarToast(data.detail || "Nao foi possivel excluir a conta."); return; }
    limparSession();
    fecharPerfilModal();
    atualizarHeader();
    mostrarToast("Conta excluida e dados pessoais anonimizados.");
  } catch {
    mostrarToast("Servico de exclusao indisponivel no momento.");
  }
}

async function salvarSenha(event) {
  event.preventDefault();
  const erroEl = document.getElementById("erroSenha");
  const btn = document.getElementById("btnSalvarSenha");
  const senha_atual = document.getElementById("perfilSenhaAtual").value;
  const nova_senha = document.getElementById("perfilNovaSenha").value;
  const confirma = document.getElementById("perfilConfirmaSenha").value;

  erroEl.style.display = "none";
  if (!senha_atual || !nova_senha) { mostrarErro(erroEl, "Preencha a senha atual e a nova senha."); return; }
  if (nova_senha.length < 8) { mostrarErro(erroEl, "A nova senha deve ter pelo menos 8 caracteres."); return; }
  if (nova_senha !== confirma) { mostrarErro(erroEl, "A confirmacao nao confere com a nova senha."); return; }

  btn.textContent = "Atualizando..."; btn.disabled = true;
  try {
    const {resp, data} = await apiFetch("/perfil/senha", {
      method: "POST",
      headers: authHeaders({"Content-Type":"application/json"}),
      body: JSON.stringify({senha_atual, nova_senha})
    });
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) { mostrarErro(erroEl, data.detail || "Erro ao atualizar senha."); return; }
    document.getElementById("perfilSenhaAtual").value = "";
    document.getElementById("perfilNovaSenha").value = "";
    document.getElementById("perfilConfirmaSenha").value = "";
    mostrarToast("Senha atualizada com sucesso.");
  } catch {
    mostrarErro(erroEl, "Servico temporariamente indisponivel.");
  } finally {
    btn.textContent = "Atualizar Senha"; btn.disabled = false;
  }
}

/* ════ CADASTRO ════ */
async function submeterCadastro(event) {
  event.preventDefault();
  const nome     = document.getElementById("cadNome").value.trim();
  const email    = document.getElementById("cadEmail").value.trim();
  const senha    = document.getElementById("cadSenha").value;
  const whatsapp = document.getElementById("cadWhatsapp").value.trim();
  const whatsappOptInEl = document.getElementById("cadWhatsappOptIn");
  const emailOptInEl = document.getElementById("cadEmailOptIn");
  const legalAcceptEl = document.getElementById("cadLegalAccept");
  const whatsapp_opt_in = !!(whatsapp && whatsappOptInEl && whatsappOptInEl.checked);
  const email_opt_in = !!(emailOptInEl && emailOptInEl.checked);
  const erroEl   = document.getElementById("erroCadastro");
  const btn      = document.getElementById("btnCadastrar");

  erroEl.style.display = "none";
  if (!nome || nome.length < 2)    { mostrarErro(erroEl, "Informe seu nome completo."); return; }
  if (!email.includes("@"))        { mostrarErro(erroEl, "Informe um e-mail válido."); return; }
  if (senha.length < 6)            { mostrarErro(erroEl, "A senha deve ter no mínimo 6 caracteres."); return; }
  if (!legalAcceptEl?.checked)     { mostrarErro(erroEl, "Aceite os termos, a privacidade e o aviso de IA para continuar."); return; }

  btn.textContent = "Criando conta..."; btn.disabled = true;

  try {
    const {resp, data} = await apiFetch("/auth/registrar", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        nome,
        email,
        senha,
        whatsapp: whatsapp || null,
        whatsapp_opt_in,
        email_opt_in,
        terms_accepted: true,
        privacy_accepted: true,
        ai_notice_accepted: true
      })
    });
    if (!resp.ok) { mostrarErro(erroEl, mensagemErroAmigavel(data.detail || data.error || "Erro ao criar conta.")); return; }
    salvarSession(data);
    trackEvent("signup_completed", {email_opt_in, whatsapp_opt_in}, {type: "users", id: data.usuario?.user_id});
    trackEvent("onboarding_started", {entry: "signup"}, {type: "users", id: data.usuario?.user_id});
    trackEvent("onboarding_completed", {step: "account_created"}, {type: "users", id: data.usuario?.user_id});
    if (whatsapp_opt_in) trackEvent("whatsapp_opt_in", {}, {type: "users", id: data.usuario?.user_id});
    if (email_opt_in) trackEvent("email_opt_in", {}, {type: "users", id: data.usuario?.user_id});
    fecharAuthModal();
    atualizarHeader();
    document.getElementById("consulta")?.scrollIntoView({behavior: "smooth", block: "start"});
    mostrarToast(`Bem-vinda, ${data.usuario.nome}! Sua conta foi criada ✨`);
  } catch {
    mostrarErro(erroEl, "Serviço temporariamente indisponível. Tente novamente.");
  } finally { btn.textContent = "✨ Criar Minha Conta Grátis"; btn.disabled = false; }
}

/* ════ LOGIN ════ */
async function submeterLogin(event) {
  event.preventDefault();
  const email  = document.getElementById("loginEmail").value.trim();
  const senha  = document.getElementById("loginSenha").value;
  const erroEl = document.getElementById("erroLogin");
  const btn    = document.getElementById("btnLogin");

  erroEl.style.display = "none";
  if (!email || !senha) { mostrarErro(erroEl, "Preencha e-mail e senha."); return; }

  btn.textContent = "Entrando..."; btn.disabled = true;

  try {
    const {resp, data} = await apiFetch("/auth/login", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ email, senha })
    });
    if (!resp.ok) { trackEvent("login_failed", {reason: data.detail || "invalid_credentials"}); mostrarErro(erroEl, data.detail || "E-mail ou senha incorretos."); return; }
    salvarSession(data);
    trackEvent("login_success", {}, {type: "users", id: data.usuario?.user_id});
    fecharAuthModal();
    atualizarHeader();
    document.getElementById("consulta")?.scrollIntoView({behavior: "smooth", block: "start"});
    mostrarToast(`Bem-vinda de volta, ${data.usuario.nome}! 🌙`);
  } catch {
    trackEvent("login_failed", {reason: "network_or_service"});
    mostrarErro(erroEl, "Serviço temporariamente indisponível.");
  } finally { btn.textContent = "🔮 Entrar no Portal"; btn.disabled = false; }
}

/* ════ CARTA DO DIA ════ */
let cartaRevelada = false;

async function revelarCarta() {
  if (cartaRevelada) return;
  cartaRevelada = true;

  let carta = {nome: "Carta do dia", symbol: "&#9790;"};
  let mensagem = "Não foi possível carregar a carta do dia agora. Tente novamente em instantes.";

  if (getToken()) {
    try {
      const resp = await fetch(`${API_BASE}/carta-do-dia`, {
        credentials: "include",
        method:"POST", headers:authHeaders({"Content-Type":"application/json"}),
        body: JSON.stringify({})
      });
      if (resp.status === 401) {
        cartaRevelada = false;
        limparSession();
        atualizarHeader();
        abrirAuth('login');
        return;
      }
      if (resp.ok) {
        const data = await resp.json();
        carta = {nome: data.carta, symbol: data.simbolo || carta.symbol};
        mensagem = data.mensagem;
      } else {
        const data = await resp.json().catch(() => ({}));
        mostrarToast(data.detail || "Carta do dia indisponível no momento.");
      }
    } catch {
      mostrarToast("Não consegui conectar com a API da carta do dia.");
    }
  }

  const inner = document.getElementById("cartaDiaInner");
  if(inner) inner.classList.add("flipped");
  const cardSymbol = document.getElementById("cardSymbol");
  const cardName = document.getElementById("cardName");
  const cardMessage = document.getElementById("cardMessage");
  const dailyCardTitle = document.getElementById("dailyCardTitle");
  const dailyCardSymbol = document.getElementById("dailyCardSymbol");
  const messagePanel = document.getElementById("cartaMessagePanel");
  aplicarArteCarta(carta, "dailyArcanoImage", ".card-reveal");
  if (cardSymbol) setSafeHTML(cardSymbol, carta.symbol);
  if (cardName) cardName.textContent = carta.nome;
  if (dailyCardSymbol) setSafeHTML(dailyCardSymbol, carta.symbol);
  if (dailyCardTitle) dailyCardTitle.textContent = carta.nome;
  if (cardMessage) cardMessage.textContent = mensagem;
  if (messagePanel) messagePanel.classList.add("revealed");
  trackEvent("daily_card_completed", {carta: carta.nome}, {type: "daily_cards", id: carta.nome});

  setTimeout(() => {
    const cta = document.getElementById("cartaCta");
    cta.style.display = "flex"; cta.style.flexDirection = "column"; cta.style.alignItems = "center";
  }, 1000);
}

/* ════ CONSULTA 3 CARTAS ════ */
function iniciarConsulta() {
  const input = document.getElementById("perguntaInput");
  const pergunta = input.value.trim();
  if (!pergunta) {
    document.getElementById("chatInput")?.classList.add("input-error");
    setTimeout(()=>document.getElementById("chatInput")?.classList.remove("input-error"),1400);
    return;
  }
  trackEvent("reading_started", {tipo: "tres_cartas", pergunta_length: pergunta.length});
  setChatLoading(true);
  document.getElementById("consultaBox").style.display = "none";
  const res = document.getElementById("consultaResultado");
  res.style.display = "block";
  document.getElementById("resultadoLoading").style.display = "flex";
  document.getElementById("resultadoApiError").style.display = "none";
  document.getElementById("resultadoCartas").style.display = "none";
  res.scrollIntoView({behavior:"smooth",block:"center"});
  startLoadingAnim();
  window.clearTimeout(iniciarConsulta.loadingWatchdog);
  iniciarConsulta.loadingWatchdog = window.setTimeout(() => {
    const msgEl = document.getElementById("loadingMessage");
    if (msgEl) msgEl.textContent = "A leitura ainda esta em processamento. Se demorar, voce pode tentar novamente sem perder sua pergunta.";
  }, 14000);
  chamarAPI(pergunta);
}

let loadingInterval;
function startLoadingAnim() {
  const msgs = [
    "A Madame do Luar está embaralhando o deck...",
    "Conectando com o plano astral...",
    "Lendo as energias do seu momento..."
  ];
  let step = 0;
  const msgEl = document.getElementById("loadingMessage");
  [1,2,3].forEach(i => document.getElementById(`ldot-${i}`)?.classList.remove("active"));
  document.getElementById("ldot-1")?.classList.add("active");
  if(msgEl) msgEl.style.opacity = "0";
  setTimeout(() => { if(msgEl){ msgEl.textContent = msgs[0]; msgEl.style.opacity = "1"; } }, 200);

  loadingInterval = setInterval(() => {
    step = (step + 1) % msgs.length;
    if(msgEl) msgEl.style.opacity = "0";
    setTimeout(() => {
      if(msgEl) { msgEl.textContent = msgs[step]; msgEl.style.opacity = "1"; }
      [1,2,3].forEach(i => document.getElementById(`ldot-${i}`)?.classList.remove("active"));
      document.getElementById(`ldot-${step+1}`)?.classList.add("active");
    }, 400);
  }, 2500);
}
function stopLoadingAnim() {
  clearInterval(loadingInterval);
  window.clearTimeout(iniciarConsulta.loadingWatchdog);
}

async function chamarAPI(pergunta) {
  try {
    trackEvent("reading_ai_started", {tipo: "tres_cartas"});
    const resp = await fetch(`${API_BASE}/leitura`, {
      credentials: "include",
      method:"POST", headers:authHeaders({"Content-Type":"application/json"}),
      body: JSON.stringify({pergunta, tipo: "tres_cartas"})
    });
    if (resp.status === 401) {
      setChatLoading(false);
      limparSession();
      atualizarHeader();
      abrirAuth('login');
      return;
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      const detail = data.error?.details?.errors?.[0];
      const field = Array.isArray(detail?.loc) ? detail.loc[detail.loc.length - 1] : "";
      const friendly = field === "pergunta"
        ? "Revise sua pergunta e envie novamente. Ela precisa estar em texto, com no maximo 600 caracteres."
        : data.error?.message || data.detail || "A leitura não pôde ser concluída agora.";
      if (resp.status === 402) trackEvent("credits_insufficient", {tipo: "tres_cartas"});
      trackEvent("reading_ai_failed", {status: resp.status, message: friendly});
      throw new Error(friendly);
    }
    const data = await resp.json();
    const cartasF = data.cartas.map(c=>({nome:c.nome,invertida:c.invertida,symbol:c.simbolo}));
    exibirResultado({
      cartas: cartasF,
      interpretacao: data.interpretacao,
      pergunta,
      question_id: data.question_id,
      reading_id: data.reading_id,
    });
  } catch (error) {
    trackEvent("reading_ai_failed", {message: error.message || "unknown"});
    exibirErroConsulta(error.message);
  }
}

function exibirErroConsulta(message) {
  setChatLoading(false);
  stopLoadingAnim();
  document.getElementById("resultadoLoading").style.display = "none";
  document.getElementById("resultadoCartas").style.display = "none";
  document.getElementById("resultadoApiErrorText").textContent =
    message || "A API não respondeu. Nenhuma leitura simulada foi exibida.";
  document.getElementById("resultadoApiError").style.display = "block";
}

function exibirResultado(data) {
  setChatLoading(false);
  ultimaLeituraResultado = {
    id: data.reading_id || data.question_id || `leitura_${Date.now()}`,
    reading_id: data.reading_id,
    question_id: data.question_id,
    titulo: data.pergunta || "Leitura de tres cartas",
    texto: String(data.interpretacao || "").replace(/<[^>]+>/g, "").slice(0, 420),
    created_at: new Date().toISOString(),
  };
  trackEvent("reading_completed", {question_id: data.question_id, reading_id: data.reading_id}, {type: "readings", id: data.reading_id});
  localStorage.setItem("mdl_show_post_reading_offers", "1");
  revealPostReadingOffers();
  const c = data.cartas;
  const resultadoCards = document.querySelectorAll(".carta-resultado");
  resultadoCards.forEach((card) => card.classList.remove("card-revealed"));
  aplicarArteCarta(c[0] || {}, "passadoImage", ".carta-resultado-card");
  aplicarArteCarta(c[1] || {}, "presenteImage", ".carta-resultado-card");
  aplicarArteCarta(c[2] || {}, "futuroImage", ".carta-resultado-card");
  setSafeHTML(document.getElementById("passadoSymbol"), c[0]?.symbol || "&#9790;");
  document.getElementById("passadoNome").textContent  = c[0]?.nome   || "...";
  document.getElementById("passadoTag").textContent   = c[0]?.invertida ? "Invertida" : "Normal";
  setSafeHTML(document.getElementById("presenteSymbol"), c[1]?.symbol || "&#9728;");
  document.getElementById("presenteNome").textContent = c[1]?.nome   || "...";
  document.getElementById("presenteTag").textContent  = c[1]?.invertida ? "Invertida" : "Normal";
  setSafeHTML(document.getElementById("futuroSymbol"), c[2]?.symbol || "&#11088;");
  document.getElementById("futuroNome").textContent   = c[2]?.nome   || "...";
  document.getElementById("futuroTag").textContent    = c[2]?.invertida ? "Invertida" : "Normal";
  
  const htmlInterp = `
    <div class="interp-block">
      <div class="interp-header">✧ Mensagem das Cartas ✧</div>
      <div class="interp-text">${escapeText(data.interpretacao)}</div>
    </div>
    <div class="interp-divider">✦ ☽ ✦</div>
    <div class="interp-block interp-ritual">
      <div class="interp-header">✧ Orientação Prática ✧</div>
      <div class="interp-text">${escapeText(data.conselho || "Mantenha a mente aberta e o coração tranquilo. As respostas virão no momento certo.")}</div>
    </div>
  `;
  setSafeHTML(document.getElementById("resultadoTexto"), htmlInterp);
  renderReadingFeedback(data);
  stopLoadingAnim();
  document.getElementById("resultadoLoading").style.display = "none";
  document.getElementById("resultadoCartas").style.display  = "block";
  requestAnimationFrame(() => {
    resultadoCards.forEach((card, index) => {
      setTimeout(() => card.classList.add("card-revealed"), index * 180);
    });
    criarConstelacaoResultado();
  });
  carregarOfertaPosLeitura();
}

function renderReadingFeedback(data) {
  const target = document.getElementById("resultadoTexto");
  if (!target || document.getElementById("readingFeedbackPanel")) return;
  const panel = document.createElement("div");
  panel.className = "reading-feedback-panel";
  panel.id = "readingFeedbackPanel";
  panel.innerHTML = `
    <span>Como foi essa leitura?</span>
    <div class="reading-feedback-actions">
      <button type="button" data-reading-feedback="clareou">Clareou</button>
      <button type="button" data-reading-feedback="preciso_aprofundar">Quero aprofundar</button>
      <button type="button" data-reading-feedback="nao_ajudou">Nao ajudou</button>
    </div>
  `;
  panel.querySelectorAll("[data-reading-feedback]").forEach((button) => {
    button.addEventListener("click", () => {
      const value = button.dataset.readingFeedback;
      trackEvent("feedback_submitted", {
        value,
        question_id: data.question_id,
        reading_id: data.reading_id,
        context: "post_reading",
      }, {type: "readings", id: data.reading_id});
      panel.querySelectorAll("button").forEach((btn) => {
        btn.disabled = true;
        btn.classList.toggle("active", btn === button);
      });
      mostrarToast("Feedback registrado.");
    });
  });
  target.appendChild(panel);
}

function criarConstelacaoResultado() {
  const area = document.getElementById("resultadoCartas");
  if (!area) return;
  area.querySelectorAll(".reading-spark").forEach((spark) => spark.remove());
  for (let i = 0; i < 18; i += 1) {
    const spark = document.createElement("span");
    spark.className = "reading-spark";
    spark.style.setProperty("--spark-x", `${8 + Math.random() * 84}%`);
    spark.style.setProperty("--spark-y", `${8 + Math.random() * 52}%`);
    spark.style.setProperty("--spark-delay", `${Math.random() * 900}ms`);
    area.appendChild(spark);
    setTimeout(() => spark.remove(), 2400);
  }
}

function novaConsulta() {
  document.getElementById("consultaBox").style.display = "flex";
  document.getElementById("consultaResultado").style.display = "none";
  document.getElementById("resultadoApiError").style.display = "none";
  document.getElementById("perguntaInput").value = "";
  document.getElementById("charCount").textContent = "0/300";
  // mostra chips novamente
  const chips = document.getElementById("chipsSugestao");
  if (chips) chips.style.display = "flex";
  resizePerguntaInput();
  updateChatSubmitState();
  document.getElementById("consultaBox").scrollIntoView({behavior:"smooth"});
}

/* ════ CHIPS DE SUGESTÃO ════ */
let rituaisCache = [];
let ritualFiltroAtual = "todos";
let ritualSelecionado = null;

function moneyBR(value) {
  return Number(value || 0).toLocaleString("pt-BR", {style: "currency", currency: "BRL"});
}

function creditosText(value) {
  const amount = Number(value || 0);
  return `${amount} ${amount === 1 ? "credito" : "creditos"}`;
}

async function carregarRituais() {
  const grid = document.getElementById("ritualGrid");
  if (!grid) return;
  try {
    const {resp, data} = await apiFetch("/rituals");
    if (!resp.ok) throw new Error(data.detail || "Nao foi possivel carregar os rituais.");
    rituaisCache = data.rituais || [];
    renderRituais();
  } catch {
    setSafeHTML(grid, `<div class="ritual-empty glass-card">Biblioteca temporariamente indisponivel.</div>`);
  }
}

function filtrarRituais(tipo) {
  ritualFiltroAtual = tipo || "todos";
  document.querySelectorAll("[data-ritual-filter]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.ritualFilter === ritualFiltroAtual);
  });
  renderRituais();
}

function renderRituais() {
  const grid = document.getElementById("ritualGrid");
  if (!grid) return;
  const items = rituaisCache.filter((r) => {
    if (ritualFiltroAtual === "gratuito") return r.gratuito;
    if (ritualFiltroAtual === "pago") return !r.gratuito;
    return true;
  });
  if (!items.length) {
    setSafeHTML(grid, `<div class="ritual-empty glass-card">Nenhum ritual encontrado para este filtro.</div>`);
    return;
  }
  setSafeHTML(grid, items.map((r, index) => `
    <article class="ritual-card ritual-card-arcane" style="--ritual-delay:${index * 80}ms">
      <div class="ritual-card-orbit" aria-hidden="true"></div>
      <div class="ritual-card-top">
        <span class="ritual-pill">${r.gratuito ? "Gratuito" : "Premium"}</span>
        <strong class="ritual-price">${r.gratuito ? "0 creditos" : creditosText(r.custo_creditos ?? r.creditos ?? r.preco)}</strong>
      </div>
      <h3>${escapeText(r.nome)}</h3>
      <p>${escapeText((r.descricao || "").slice(0, 150))}${(r.descricao || "").length > 150 ? "..." : ""}</p>
      <div class="ritual-meta">
        ${r.tem_pdf ? "<span>PDF</span>" : ""}
        ${r.tem_audio ? "<span>Audio</span>" : ""}
        ${r.tema ? `<span>${escapeText(r.tema)}</span>` : ""}
      </div>
      <button class="btn btn-primary" data-ritual-open="${escapeText(r.ritual_id)}">${r.gratuito ? "Ver ritual" : "Comprar com creditos"}</button>
    </article>
  `).join(""));
  grid.querySelectorAll("[data-ritual-open]").forEach((btn) => {
    btn.addEventListener("click", () => abrirRitualDetalhe(btn.dataset.ritualOpen));
  });
  requestAnimationFrame(() => {
    grid.querySelectorAll(".ritual-card").forEach((card) => card.classList.add("ritual-card-visible"));
  });
}

async function abrirRitualDetalhe(ritualId) {
  if (!ritualId) return;
  try {
    const {resp, data} = await apiFetch(`/rituals/${ritualId}`, {headers: authHeaders()});
    if (!resp.ok) throw new Error(data.detail || "Ritual nao encontrado.");
    ritualSelecionado = data.ritual;
    preencherRitualModal(data.ritual, data.compra);
    document.getElementById("ritualOverlay").style.display = "flex";
    document.body.style.overflow = "hidden";
  } catch (error) {
    mostrarToast(error.message || "Nao foi possivel abrir este ritual.");
  }
}

function preencherRitualModal(ritual, compra) {
  document.getElementById("ritualModalTema").textContent = ritual.tema || (ritual.gratuito ? "Ritual gratuito" : "Ritual premium");
  document.getElementById("ritualModalNome").textContent = ritual.nome || "Ritual do Luar";
  document.getElementById("ritualModalDescricao").textContent = ritual.descricao || "";
  const assets = document.getElementById("ritualModalAssets");
  const liberado = ritual.gratuito || compra;
  setSafeHTML(assets, [
    ritual.tem_pdf ? (liberado && ritual.pdf_url ? `<a href="${escapeText(ritual.pdf_url)}" target="_blank" rel="noopener">Abrir PDF</a>` : "<span>PDF incluso</span>") : "",
    ritual.tem_audio ? (liberado && ritual.audio_url ? `<a href="${escapeText(ritual.audio_url)}" target="_blank" rel="noopener">Ouvir audio</a>` : "<span>Audio incluso</span>") : "",
  ].join(""));
  document.getElementById("ritualCouponRow").style.display = ritual.gratuito || compra ? "none" : "block";
  const custoCreditos = ritual.custo_creditos ?? ritual.creditos ?? ritual.preco;
  document.getElementById("ritualModalCta").textContent = compra ? "Ritual liberado" : (ritual.gratuito ? "Liberar ritual gratuito" : `Comprar por ${creditosText(custoCreditos)}`);
  document.getElementById("ritualModalHint").textContent = compra
    ? "Este ritual ja esta vinculado a sua conta."
    : (ritual.gratuito ? "Acesso imediato para usuarios logados." : "O valor sera descontado do seu saldo de creditos. Cupons podem reduzir o custo final.");
}

function fecharRitualModal(event) {
  if (event && event.target !== document.getElementById("ritualOverlay")) return;
  document.getElementById("ritualOverlay").style.display = "none";
  document.body.style.overflow = "";
}

async function comprarRitualSelecionado() {
  if (!ritualSelecionado) return;
  if (!getToken()) { fecharRitualModal(); abrirAuth("cadastro"); return; }
  const btn = document.getElementById("ritualModalCta");
  const coupon_code = document.getElementById("ritualCouponInput")?.value.trim() || null;
  let compraLiberada = false;
  btn.disabled = true;
  btn.textContent = "Preparando acesso...";
  try {
    const {resp, data} = await apiFetch(`/rituals/${ritualSelecionado.ritual_id}/purchase`, {
      method: "POST",
      headers: authHeaders({"Content-Type": "application/json"}),
      body: JSON.stringify({coupon_code, offer_context: "ritual_library"})
    });
    if (resp.status === 401) { sessaoExpirada(); return; }
    if (!resp.ok) { mostrarToast(data.detail || "Nao foi possivel liberar o ritual com creditos."); return; }
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
      return;
    }
    compraLiberada = true;
    if (data.saldo_atual !== undefined && data.saldo_atual !== null) {
      perfilState.credits = {...(perfilState.credits || {}), credits_balance: data.saldo_atual};
      atualizarSessionUsuario({credits_balance: data.saldo_atual});
      atualizarHeaderSaldo(data.saldo_atual);
    } else {
      sincronizarSaldoHeader();
    }
    mostrarToast("Ritual liberado na sua conta.");
    fecharRitualModal();
    await abrirRitualDetalhe(ritualSelecionado.ritual_id);
  } catch {
    mostrarToast("Servico de rituais indisponivel no momento.");
  } finally {
    btn.disabled = false;
    if (ritualSelecionado && !compraLiberada) preencherRitualModal(ritualSelecionado, null);
  }
}

async function carregarOfertaPosLeitura() {
  const actions = document.querySelector("#resultadoCartas .resultado-actions");
  if (!actions || !getToken()) return;
  try {
    const {resp, data} = await apiFetch("/offers/after-reading", {headers: authHeaders()});
    if (!resp.ok || !data.upsell) return;
    const old = document.getElementById("ritualOfferAfterReading");
    if (old) old.remove();
    const offer = document.createElement("div");
    offer.className = "ritual-card";
    offer.id = "ritualOfferAfterReading";
    setSafeHTML(offer, `
      <span class="ritual-pill">Proximo passo</span>
      <h3>${escapeText(data.upsell.nome)}</h3>
      <p>${escapeText(data.upsell.descricao || "Continue a energia da leitura com um ritual guiado.")}</p>
      <button class="btn btn-primary" data-ritual-open="${escapeText(data.upsell.ritual_id)}">Ver ritual recomendado</button>
      ${data.downsell ? `<button class="btn btn-ghost" data-ritual-open="${escapeText(data.downsell.ritual_id)}">Prefiro um ritual gratuito</button>` : ""}
    `);
    offer.querySelectorAll("[data-ritual-open]").forEach((btn) => {
      btn.addEventListener("click", () => abrirRitualDetalhe(btn.dataset.ritualOpen));
    });
    actions.appendChild(offer);
  } catch {}
}

function usarChip(btn) {
  const input = document.getElementById("perguntaInput");
  const chips = document.getElementById("chipsSugestao");
  if (!input) return;

  const textos = {
    "Meu relacionamento":  "O que as cartas revelam sobre meu relacionamento amoroso neste momento?",
    "Minha carreira":      "O que as cartas dizem sobre minha carreira e crescimento profissional?",
    "Meu próximo passo":   "Qual é o próximo passo que devo dar para avançar na minha vida?",
    "Prosperidade":        "O que as cartas revelam sobre minha prosperidade e abundância financeira?",
    "Propósito de vida":   "As cartas podem me mostrar qual é o meu propósito de vida agora?",
  };

  // pega o label do chip (remove o emoji)
  const label = btn.textContent.replace(/^[\u{1F600}-\u{1FFFF}\u2600-\u27FF]\s*/u, "").trim();
  input.value = textos[label] || btn.textContent.trim();
  input.focus();
  resizePerguntaInput();
  updateChatSubmitState();
  // esconde os chips
  if (chips) chips.style.display = "none";
  // conta chars
  document.getElementById("charCount").textContent = `${input.value.length}/300`;
}

/* ════ PAGAMENTO ════ */
let billingCycle = "monthly";
let selectedPricingPlan = "premium";
let planoCheckoutAtual = "assinatura_mensal";
let selectedCreditPackage = "recarga_100";
const CREDIT_PACKAGES = {
  recarga_100: {
    credits: 100,
    label: "100 creditos",
    price: "R$19,90",
    use: "Equivale a 2 tiragens de 3 cartas",
    progress: "22%"
  },
  recarga_300: {
    credits: 300,
    label: "300 creditos",
    price: "R$49,90",
    use: "Equivale a 6 tiragens de 3 cartas",
    progress: "42%"
  },
  recarga_500: {
    credits: 500,
    label: "500 creditos",
    price: "R$79,90",
    use: "Equivale a 10 tiragens de 3 cartas",
    progress: "62%"
  },
  recarga_1500: {
    credits: 1500,
    label: "1.500 creditos",
    price: "R$199,90",
    use: "Equivale a 30 tiragens de 3 cartas",
    progress: "100%"
  }
};

function toggleBillingCycle() {
  billingCycle = billingCycle === "monthly" ? "yearly" : "monthly";
  const yearly = billingCycle === "yearly";
  const sw = document.getElementById("billingSwitch");
  sw?.classList.toggle("active", yearly);
  sw?.setAttribute("aria-pressed", yearly ? "true" : "false");
  updatePricing2Prices();
  updatePricingCta();
}

function updatePricing2Prices() {
  const yearly = billingCycle === "yearly";
  const starterPrice = document.getElementById("starterPrice");
  const starterBilling = document.getElementById("starterBilling");
  const growthPrice = document.getElementById("growthPrice");
  const growthBilling = document.getElementById("growthBilling");

  if (starterPrice) starterPrice.textContent = "R$19,90";
  if (starterBilling) starterBilling.textContent = "Pagamento unico";
  if (growthPrice) growthPrice.textContent = yearly ? "R$397,00" : "R$49,90";
  if (growthBilling) growthBilling.textContent = yearly ? "por ano" : "por mes";
}

function comprarPricingCard(plan) {
  if (plan === "leitura") {
    iniciarPagamento("leitura");
    return;
  }
  const plano = billingCycle === "yearly" ? "assinatura_anual" : "assinatura_mensal";
  if (!getToken()) {
    trackEvent("signup_started", {entry: "checkout", plano});
    abrirAuth("cadastro");
    return;
  }
  processarCheckout(plano);
}

function selecionarPacoteCredito(packageId) {
  if (!CREDIT_PACKAGES[packageId]) return;
  selectedCreditPackage = packageId;
  const config = CREDIT_PACKAGES[packageId];

  document.querySelectorAll(".credit-package-card").forEach((el) => {
    const active = el.dataset.package === packageId;
    el.classList.toggle("active", active);
    el.setAttribute("aria-checked", active ? "true" : "false");
  });

  const select = document.getElementById("creditPackageSelect");
  if (select && select.value !== packageId) select.value = packageId;

  const credits = document.getElementById("creditPackageCredits");
  const name = document.getElementById("creditPackageName");
  const price = document.getElementById("creditPackagePrice");
  const use = document.getElementById("creditPackageUse");
  const bar = document.getElementById("creditPackageBar");

  if (credits) credits.textContent = config.credits.toLocaleString("pt-BR");
  if (name) name.textContent = config.label;
  if (price) price.textContent = config.price;
  if (use) use.textContent = config.use;
  if (bar) bar.style.width = config.progress;
}

function comprarPacoteCreditoSelecionado() {
  if (!getToken()) {
    abrirAuth("cadastro");
    return;
  }
  processarCheckout(selectedCreditPackage);
}

function toggleCreditPackages() {
  const panel = document.getElementById("creditos");
  const trigger = document.querySelector(".secondary-offers-toggle");
  if (!panel) return;
  const willOpen = panel.hasAttribute("hidden");
  panel.toggleAttribute("hidden", !willOpen);
  trigger?.setAttribute("aria-expanded", willOpen ? "true" : "false");
  if (willOpen) trackEvent("secondary_offer_viewed", {type: "credit_packages"});
}

function revealPostReadingOffers() {
  document.querySelectorAll(".post-reading-only").forEach((section) => {
    section.classList.add("is-visible");
  });
}

function setBillingCycle(cycle) {
  billingCycle = cycle;
  document.getElementById("billingMonthly")?.classList.toggle("active", cycle === "monthly");
  document.getElementById("billingYearly")?.classList.toggle("active", cycle === "yearly");

  const isYearly = cycle === "yearly";
  document.getElementById("premiumDescription").textContent = isYearly ? "acompanhamento anual" : "acompanhamento mensal";
  document.getElementById("premiumPrice").textContent = isYearly ? "R$397,00" : "R$49,90";
  document.getElementById("premiumPeriod").textContent = isYearly ? "por ano" : "por mes";
  updatePricingCta();
}

function selectPricingPlan(plan) {
  selectedPricingPlan = plan;
  document.querySelectorAll(".pricing-option").forEach((el) => {
    el.classList.toggle("active", el.dataset.plan === plan);
  });
  updatePricingCta();
}

function updatePricingCta() {
  const cta = document.getElementById("pricingCta");
  const hint = document.getElementById("pricingHint");
  if (!cta || !hint) return;

  if (selectedPricingPlan === "gratuito") {
    cta.textContent = "Comecar gratis";
    hint.textContent = "Crie sua conta e faca sua primeira leitura sem custo.";
  } else if (selectedPricingPlan === "leitura") {
    cta.textContent = "Comprar leitura avulsa";
    hint.textContent = "Pagamento unico, sem assinatura.";
  } else {
    cta.textContent = billingCycle === "yearly" ? "Garantir plano anual" : "Garantir plano mensal";
    hint.textContent = billingCycle === "yearly"
      ? "Economize R$201,80 no acesso anual."
      : "Cobranca segura. Cancele quando quiser.";
  }
}

function comprarPlanoSelecionado() {
  if (selectedPricingPlan === "gratuito") {
    abrirAuth("cadastro");
    return;
  }
  if (selectedPricingPlan === "leitura") {
    iniciarPagamento("leitura");
    return;
  }
  iniciarPagamento(billingCycle === "yearly" ? "assinatura_anual" : "assinatura_mensal");
}

function abrirPaymentModal() {
  document.getElementById("paymentOverlay").style.display = "flex";
  document.body.style.overflow = "hidden";
}

function fecharPaymentModal(event) {
  if (event && event.target !== document.getElementById("paymentOverlay")) return;
  document.getElementById("paymentOverlay").style.display = "none";
  document.body.style.overflow = "";
}

function iniciarPagamento(plano) {
  if (!getToken()) { trackEvent("signup_started", {entry: "checkout", plano}); abrirAuth('cadastro'); return; }
  planoCheckoutAtual = plano || "assinatura_mensal";
  trackEvent("checkout_started", {plano: planoCheckoutAtual});

  if (planoCheckoutAtual === "assinatura_anual" || planoCheckoutAtual === "leitura") {
    processarCheckout(planoCheckoutAtual);
    return;
  }

  // Abre o modal de checkout Mercado Pago.
  abrirPaymentModal();
}

function processarCheckout(forma) {
  if (!getToken()) return;

  fecharPaymentModal();
  mostrarToast("Preparando ambiente seguro de pagamento...");
  trackEvent("checkout_started", {plano: forma, source: "processar_checkout"});
  
  fetch(`${API_BASE}/checkout`, {
    credentials: "include",
    method: "POST",
    headers: authHeaders({"Content-Type": "application/json"}),
    body: JSON.stringify({ plano: forma })
  })
  .then(resp => resp.json().then(data => ({ status: resp.status, ok: resp.ok, data })))
  .then(({ status, ok, data }) => {
    if (status === 401) {
      limparSession();
      atualizarHeader();
      abrirAuth('login');
      return;
    }
    if (!ok) {
      trackEvent("payment_failed", {plano: forma, status, message: data.detail?.message || data.detail || "checkout_failed"});
      mostrarToast(data.detail?.message || data.detail || "Erro ao gerar link de pagamento.");
      return;
    }
    if (data.payment_id) {
      localStorage.setItem("mdl_last_payment_id", data.payment_id);
      trackEvent("checkout_pix_generated", {plano: forma, status: data.status, payment_id: data.payment_id}, {type: "payments", id: data.payment_id});
    }
    window.location.href = data.url;
  })
  .catch(e => {
    mostrarToast("Serviço indisponível no momento. Tente mais tarde.");
  });
}

/* ════ UTILITÁRIOS ════ */
function mostrarErro(el, msg) {
  const texto = String(msg || "");
  el.textContent = texto.includes("temporariamente indispon")
    ? `Nao consegui conectar ao backend em ${API_BASE}. Inicie o servidor local e recarregue a pagina.`
    : texto;
  el.style.display = "block";
}

function mostrarToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.style.display = "block"; t.classList.add("toast-show");
  setTimeout(()=>{ t.classList.remove("toast-show"); setTimeout(()=>t.style.display="none",400); }, 3500);
}

/* ════ ESTRELAS ════ */
function criarEstrelas() {
  const campo = document.getElementById("starField");
  if (!campo) return;
  if (getComputedStyle(campo).display === "none") return;
  for (let i=0; i<48; i++) {
    const s = document.createElement("div"); s.className="star";
    const tam = Math.random()*2.5+0.5, dur = Math.random()*4+2;
    s.style.cssText=`left:${Math.random()*100}%;top:${Math.random()*100}%;width:${tam}px;height:${tam}px;--dur:${dur}s;animation-delay:${Math.random()*dur}s;opacity:${Math.random()*0.5+0.1}`;
    campo.appendChild(s);
  }
}

/* ════ HEADER SCROLL ════ */
function initHeader() {
  const h = document.getElementById("header");
  window.addEventListener("scroll",()=>{ h.style.background=window.scrollY>60?"rgba(13,5,24,0.95)":"rgba(13,5,24,0.8)"; });
}

/* ════ CHAR COUNT ════ */
function initCharCount() {
  const input=document.getElementById("perguntaInput"), count=document.getElementById("charCount");
  if(!input) return;
  input.addEventListener("input",()=>{
    count.textContent=`${input.value.length}/300`;
    resizePerguntaInput();
    updateChatSubmitState();
  });
  input.addEventListener("keydown",(event)=>{
    if (event.key === "Enter" && !event.shiftKey) {
      if (!input.value.trim()) return;
      event.preventDefault();
      iniciarConsulta();
    }
  });
  resizePerguntaInput();
  updateChatSubmitState();
}

function resizePerguntaInput() {
  const input = document.getElementById("perguntaInput");
  if (!input) return;
  input.style.height = "0px";
  const lineHeight = parseInt(getComputedStyle(input).lineHeight, 10) || 24;
  const minHeight = lineHeight + 20;
  input.style.height = `${Math.max(input.scrollHeight, minHeight)}px`;
}

function updateChatSubmitState() {
  const input = document.getElementById("perguntaInput");
  const btn = document.getElementById("btnConsultar");
  if (!input || !btn) return;
  btn.disabled = !input.value.trim() || btn.classList.contains("loading");
}

function setChatLoading(isLoading) {
  const btn = document.getElementById("btnConsultar");
  const input = document.getElementById("perguntaInput");
  if (!btn || !input) return;
  btn.classList.toggle("loading", isLoading);
  btn.disabled = isLoading || !input.value.trim();
  input.disabled = isLoading;
}

/* ════ SCROLL ANIMATIONS ════ */
function initScrollAnimations() {
  // Observer para classe .reveal (nova)
  const revealObs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add("visible");
        revealObs.unobserve(e.target); // anima uma vez só
      }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

  document.querySelectorAll(".reveal").forEach(el => revealObs.observe(el));

  // Observer para cards que não têm .reveal (legacy)
  const cardObs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.style.opacity = "1";
        e.target.style.transform = "translateY(0)";
        cardObs.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll(".step-card:not(.reveal), .depoimento-card:not(.reveal), .pricing-card:not(.reveal), .glass-card:not(.reveal)").forEach(el => {
    el.style.opacity = "0";
    el.style.transform = "translateY(30px)";
    el.style.transition = "opacity 0.65s ease, transform 0.65s ease";
    cardObs.observe(el);
  });
}

function initPricingParticles() {
  const canvas = document.getElementById("pricingParticles");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  let particles = [];

  function resize() {
    const rect = canvas.parentElement?.getBoundingClientRect() || { width: window.innerWidth, height: window.innerHeight };
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.max(18, Math.floor((rect.width * rect.height) / 12000));
    particles = Array.from({ length: count }, () => ({
      x: Math.random() * rect.width,
      y: Math.random() * rect.height,
      v: Math.random() * 0.25 + 0.05,
      o: Math.random() * 0.35 + 0.15
    }));
  }

  function draw() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    ctx.clearRect(0, 0, w, h);
    particles.forEach((p) => {
      p.y -= p.v;
      if (p.y < 0) {
        p.x = Math.random() * w;
        p.y = h + Math.random() * 40;
        p.v = Math.random() * 0.25 + 0.05;
        p.o = Math.random() * 0.35 + 0.15;
      }
      ctx.fillStyle = `rgba(250,250,250,${p.o})`;
      ctx.fillRect(p.x, p.y, 0.7, 2.2);
    });
    requestAnimationFrame(draw);
  }

  resize();
  draw();
  window.addEventListener("resize", resize);
}

function initScrollProgress() {
  const pb = document.getElementById("scrollProgress");
  if (!pb) return;
  window.addEventListener('scroll', () => {
    const scrollTotal = document.documentElement.scrollTop;
    const heightTotal = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrolled = (scrollTotal / heightTotal) * 100;
    pb.style.width = scrolled + "%";
  });
}

function initHeroParallax() {
  const hero = document.getElementById("hero");
  if (!hero) return;
  window.addEventListener("scroll", () => {
    const s = window.scrollY;
    if (s > 800) return;
    const cards = document.querySelector(".hero-cards");
    const madame = document.querySelector(".hero-madame");
    if (cards) cards.style.transform = `translateY(${s * 0.2}px)`;
    if (madame) madame.style.transform = `translateY(${s * 0.1}px)`;
  });
}

function initHeroMedia() {
  const video = document.querySelector(".hero-video");
  if (!video) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const narrow = window.matchMedia("(max-width: 768px)").matches;
  const saveData = navigator.connection?.saveData;
  if (reduceMotion || narrow || saveData) {
    video.removeAttribute("autoplay");
    video.pause?.();
    return;
  }
  video.querySelectorAll("source[data-src]").forEach((source) => {
    source.src = source.dataset.src;
    source.removeAttribute("data-src");
  });
  video.load();
  video.play().catch(() => {});
}

/* ════ INIT ════ */
document.addEventListener("DOMContentLoaded",()=>{
  trackEvent("page_view", {path: window.location.pathname, title: document.title});
  const priceVariant = localStorage.getItem("mdl_price_test_variant") || "premium_monthly_primary";
  localStorage.setItem("mdl_price_test_variant", priceVariant);
  trackEvent("price_test_assigned", {variant: priceVariant});
  criarEstrelas(); initHeader(); initCharCount(); initScrollAnimations(); initPricingParticles();
  initScrollProgress(); initHeroParallax(); initHeroMedia();
  initPerfilNavigation();
  carregarRituais();
  updatePricing2Prices();
  updatePricingCta();
  selecionarPacoteCredito(selectedCreditPackage);
  if (localStorage.getItem("mdl_show_post_reading_offers") === "1") revealPostReadingOffers();
  atualizarHeader();
});

window.addEventListener("beforeunload", () => {
  const paymentId = localStorage.getItem("mdl_last_payment_id");
  if (paymentId && !sessionStorage.getItem(`mdl_payment_returned_${paymentId}`)) {
    trackEvent("payment_abandoned", {payment_id: paymentId, reason: "page_unload"}, {type: "payments", id: paymentId});
  }
});

