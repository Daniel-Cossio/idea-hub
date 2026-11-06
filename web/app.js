/* ============================================================
   IdeaHub — Lógica JavaScript (Kanban + Vista Dual)
   ============================================================ */
(function () {
  "use strict";

  // --- Estado ---
  let ideas = [];
  let currentIdeaId = null;
  let token = sessionStorage.getItem("ideahub_token") || "";

  // --- Columnas Kanban ---
  const COLUMNS = ["inbox", "refining", "agent_ready", "in_progress", "done", "archived"];
  const ICONS = {
    inbox: "📥", refining: "🔍", agent_ready: "⚡",
    in_progress: "🚀", done: "✅", archived: "📦"
  };

  // --- DOM Refs ---
  const loginScreen = document.getElementById("login-screen");
  const kanbanScreen = document.getElementById("kanban-screen");
  const dualView = document.getElementById("dual-view");
  const passwordInput = document.getElementById("password-input");
  const searchInput = document.getElementById("search-input");
  const logEntries = document.getElementById("log-entries");
  const specEditor = document.getElementById("spec-editor");
  const statusSelect = document.getElementById("status-select");
  const prioritySelect = document.getElementById("priority-select");
  const logForm = document.getElementById("log-form");
  const logInput = document.getElementById("log-entry-input");

  // --- API Helper ---
  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const resp = await fetch(`/api${path}`, { ...options, headers, body: options.body && JSON.stringify(options.body) });
    if (!resp.ok) throw new Error(`API ${resp.status}: ${resp.statusText}`);
    return resp.json();
  }

  // --- Login ---
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await api("/auth/login", { method: "POST", body: { password: passwordInput.value } });
      token = data.token;
      sessionStorage.setItem("ideahub_token", token);
      loginScreen.classList.add("hidden");
      kanbanScreen.classList.remove("hidden");
      loadIdeas();
    } catch (err) {
      document.getElementById("login-error").classList.remove("hidden");
      setTimeout(() => document.getElementById("login-error").classList.add("hidden"), 2000);
    }
  });

  document.getElementById("btn-logout").addEventListener("click", () => {
    sessionStorage.removeItem("ideahub_token");
    token = "";
    kanbanScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
  });

  // --- Carga de Ideas ---
  async function loadIdeas() {
    const q = searchInput.value;
    const url = q ? `/ideas?q=${encodeURIComponent(q)}` : "/ideas";
    ideas = await api(url);
    renderBoard();
  }

  // --- Render Kanban ---
  function renderBoard() {
    for (const col of COLUMNS) {
      const container = document.querySelector(`#${col === "agent_ready" ? "col-agent_ready" : "col-" + col} .column-cards`);
      container.innerHTML = "";
    }
    const filtered = searchInput.value
      ? ideas.filter(i => i.title.toLowerCase().includes(searchInput.value.toLowerCase()) ||
                           i.spec_body.toLowerCase().includes(searchInput.value.toLowerCase()))
      : ideas;

    for (const idea of filtered) {
      const card = document.createElement("div");
      card.className = "idea-card";
      card.dataset.id = idea.id;
      card.innerHTML = `
        <div class="card-title">${esc(idea.title)}</div>
        <div class="card-meta">
          <span class="card-badge status-${idea.status}">${idea.status}</span>
          <span>${idea.id}</span>
        </div>`;
      card.addEventListener("click", () => openDualView(idea.id));
      const colContainer = document.querySelector(`[data-status="${idea.status}"] .column-cards`);
      if (colContainer) colContainer.appendChild(card);
    }

    // Contadores
    for (const col of COLUMNS) {
      const colEl = document.getElementById(`col-${col}`);
      if (colEl) {
        const countEl = colEl.querySelector(".column-count");
        const cards = colEl.querySelectorAll(".column-cards > .idea-card");
        countEl.textContent = String(cards.length);
      }
    }
  }

  // --- Búsqueda ---
  let searchTimeout;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(loadIdeas, 200);
  });

  // --- Botón Nueva Idea ---
  document.getElementById("btn-new-idea").addEventListener("click", async () => {
    const raw = prompt("Escribe tu idea:");
    if (!raw) return;
    const data = await api("/ideas", { method: "POST", body: { raw_input: raw, source_type: "text" } });
    ideas.push(data);
    renderBoard();
  });

  // --- Vista Dual ---
  async function openDualView(ideaId) {
    currentIdeaId = ideaId;
    const idea = ideas.find(i => i.id === ideaId) || await api(`/ideas/${ideaId}`);

    document.getElementById("idea-id-display").textContent = ideaId;

    // Status/Priority selects
    statusSelect.innerHTML = COLUMNS.map(s => `<option value="${s}" ${idea.status === s ? "selected" : ""}>${s}</option>`).join("");
    prioritySelect.innerHTML = ["low","medium","high","critical"].map(p => `<option value="${p}" ${idea.priority === p ? "selected" : ""}>${p}</option>`).join("");

    // Editor
    specEditor.value = idea.spec_body || "";

    // Log entries
    logEntries.innerHTML = "";
    if (idea.capture_log) {
      for (const line of idea.capture_log.split("\n").filter(Boolean)) {
        const entry = document.createElement("div");
        entry.className = "log-entry";
        const match = line.match(/\[(.+)\]\s*(\S+):\s*(.+)/);
        if (match) {
          entry.innerHTML = `<div class="log-timestamp">${match[1]}</div><div><span class="log-source">${match[2]}</span> ${esc(match[3])}</div>`;
        } else {
          entry.textContent = line;
        }
        logEntries.appendChild(entry);
      }
    }

    dualView.classList.remove("hidden");
  }

  document.getElementById("btn-close-dual").addEventListener("click", () => {
    dualView.classList.add("hidden");
    currentIdeaId = null;
  });
  document.getElementById("dual-view-backdrop").addEventListener("click", () => {
    dualView.classList.add("hidden");
    currentIdeaId = null;
  });

  // Guardar spec editado
  specEditor.addEventListener("blur", async () => {
    if (!currentIdeaId) return;
    await api(`/ideas/${currentIdeaId}`, { method: "PUT", body: { spec_body: specEditor.value } });
  });

  // Cambiar estado
  statusSelect.addEventListener("change", async () => {
    if (!currentIdeaId) return;
    await api(`/ideas/${currentIdeaId}/status`, { method: "POST", body: { status: statusSelect.value } });
    const idea = ideas.find(i => i.id === currentIdeaId);
    if (idea) idea.status = statusSelect.value;
    renderBoard();
  });

  // --- Añadir nota ---
  logForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentIdeaId || !logInput.value.trim()) return;
    await api(`/ideas/${currentIdeaId}/log`, { method: "POST", body: { entry_text: logInput.value.trim(), source_type: "note" } });
    logInput.value = "";
    openDualView(currentIdeaId);
    loadIdeas();
  });

  // --- Estructurar con IA ---
  document.getElementById("btn-ai-structure").addEventListener("click", async () => {
    if (!currentIdeaId) return;
    const btn = document.getElementById("btn-ai-structure");
    btn.textContent = "⏳ Estructurando...";
    btn.disabled = true;
    await api(`/ideas/${currentIdeaId}/structure`, { method: "POST" });
    btn.textContent = "✨ Estructurar con IA";
    btn.disabled = false;
    loadIdeas();
  });

  // --- Copiar comando ---
  document.getElementById("btn-copy-command").addEventListener("click", () => {
    const id = document.getElementById("idea-id-display").textContent;
    const cmd = `idea-cli init ${id}`;
    navigator.clipboard.writeText(cmd).then(() => {
      const btn = document.getElementById("btn-copy-command");
      const orig = btn.textContent;
      btn.textContent = "✓ Copiado!";
      setTimeout(() => btn.textContent = orig, 1500);
    });
  });

  // --- Utilidades ---
  function esc(str) { const d = document.createElement("div"); d.textContent = str; return d.innerHTML; }
})();
