/* ============================================================
   IdeaHub — Lógica JavaScript (Kanban + Vista Dual + Mobile)
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
  const toastContainer = document.getElementById("toast-container");
  const saveIndicator = document.getElementById("save-indicator");

  // Modal Nueva Idea
  const newIdeaModal = document.getElementById("new-idea-modal");
  const newIdeaForm = document.getElementById("new-idea-form");
  const newIdeaInput = document.getElementById("new-idea-input");
  const newIdeaPriority = document.getElementById("new-idea-priority");
  const btnCloseNewModal = document.getElementById("btn-close-new-modal");
  const btnCancelNewModal = document.getElementById("btn-cancel-new-modal");
  const newIdeaBackdrop = document.getElementById("new-idea-backdrop");

  // --- Utilidad Toast ---
  function showToast(message, duration = 2500) {
    if (!toastContainer) return;
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      toast.style.transition = "all 0.2s ease";
      setTimeout(() => toast.remove(), 200);
    }, duration);
  }

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
      setTimeout(() => document.getElementById("login-error").classList.add("hidden"), 2500);
    }
  });

  // Auto-login si ya existe token en sesión
  if (token) {
    loginScreen.classList.add("hidden");
    kanbanScreen.classList.remove("hidden");
    loadIdeas();
  }

  document.getElementById("btn-logout").addEventListener("click", () => {
    sessionStorage.removeItem("ideahub_token");
    token = "";
    kanbanScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
    passwordInput.value = "";
    showToast("Sesión cerrada");
  });

  // --- Carga de Ideas ---
  async function loadIdeas() {
    try {
      const q = searchInput.value.trim();
      const url = q ? `/ideas?q=${encodeURIComponent(q)}` : "/ideas";
      ideas = await api(url);
      renderBoard();
    } catch (err) {
      console.error("Error al cargar ideas:", err);
    }
  }

  // --- Render Kanban ---
  function renderBoard() {
    for (const col of COLUMNS) {
      const colId = col === "agent_ready" ? "col-agent_ready" : "col-" + col;
      const container = document.querySelector(`#${colId} .column-cards`);
      if (container) container.innerHTML = "";
    }

    const q = searchInput.value.trim().toLowerCase();
    const filtered = q
      ? ideas.filter(i => (i.title && i.title.toLowerCase().includes(q)) ||
                           (i.spec_body && i.spec_body.toLowerCase().includes(q)))
      : ideas;

    for (const idea of filtered) {
      const card = document.createElement("div");
      card.className = "idea-card";
      card.dataset.id = idea.id;
      
      const priority = idea.priority || "medium";
      const status = idea.status || "inbox";
      const appBtnHtml = idea.app_url && idea.app_url.trim()
        ? `<a href="${esc(idea.app_url)}" target="_blank" rel="noopener noreferrer" class="card-app-btn" title="Abrir panel desplegado (${esc(idea.app_url)})" onclick="event.stopPropagation()">
             <span>🚀</span> Abrir App
           </a>`
        : "";

      card.innerHTML = `
        <div class="card-header-meta">
          <span class="card-id-chip">#${esc(idea.id)}</span>
          <span class="card-priority prio-${esc(priority)}">${esc(priority)}</span>
        </div>
        <div class="card-title">${esc(idea.title || "Sin título")}</div>
        <div class="card-meta">
          <span class="card-badge status-${esc(status)}">${esc(status)}</span>
          ${appBtnHtml}
        </div>`;
      
      card.addEventListener("click", () => openDualView(idea.id));
      
      const colContainer = document.querySelector(`[data-status="${idea.status}"] .column-cards`);
      if (colContainer) colContainer.appendChild(card);
    }

    // Actualizar menú desplegable de aplicaciones en el navbar
    renderAppsMenu();

    // Contadores por columna y píldoras móviles
    for (const col of COLUMNS) {
      const colEl = document.getElementById(`col-${col}`);
      const cards = colEl ? colEl.querySelectorAll(".column-cards > .idea-card") : [];
      const count = cards.length;

      if (colEl) {
        const countEl = colEl.querySelector(".column-count");
        if (countEl) countEl.textContent = String(count);
      }

      const pillCountEl = document.getElementById(`count-${col}`);
      if (pillCountEl) pillCountEl.textContent = String(count);
    }
  }

  // --- Render Menú de Apps Desplegadas ---
  function renderAppsMenu() {
    const listEl = document.getElementById("apps-menu-list");
    const countEl = document.getElementById("apps-count-badge");
    if (!listEl || !countEl) return;

    const deployed = ideas.filter(i => i.app_url && i.app_url.trim() !== "");
    countEl.textContent = String(deployed.length);

    if (deployed.length === 0) {
      listEl.innerHTML = '<span class="apps-menu-empty">Sin aplicaciones activas</span>';
      return;
    }

    listEl.innerHTML = deployed.map(i => `
      <a href="${esc(i.app_url)}" target="_blank" rel="noopener noreferrer" class="apps-menu-item" title="${esc(i.title || 'Idea #' + i.id)}">
        <span class="apps-item-icon">🚀</span>
        <div class="apps-item-info">
          <div class="apps-item-title">#${esc(i.id)} ${esc(i.title || "Sin título")}</div>
          <div class="apps-item-url">${esc(i.app_url)}</div>
        </div>
      </a>
    `).join("");
  }

  const btnAppsMenu = document.getElementById("btn-apps-menu");
  const appsMenuDropdown = document.getElementById("apps-menu-dropdown");
  if (btnAppsMenu && appsMenuDropdown) {
    btnAppsMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      appsMenuDropdown.classList.toggle("hidden");
    });
    document.addEventListener("click", (e) => {
      if (!appsMenuDropdown.contains(e.target) && e.target !== btnAppsMenu) {
        appsMenuDropdown.classList.add("hidden");
      }
    });
  }

  // --- Búsqueda en tiempo real ---
  let searchTimeout;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(loadIdeas, 200);
  });

  // --- Modal Nueva Idea (Ergonómico) ---
  function openNewIdeaModal() {
    if (!newIdeaModal) return;
    newIdeaModal.classList.remove("hidden");
    newIdeaInput.value = "";
    newIdeaPriority.value = "medium";
    setTimeout(() => newIdeaInput.focus(), 50);
  }

  function closeNewIdeaModal() {
    if (!newIdeaModal) return;
    newIdeaModal.classList.add("hidden");
  }

  document.getElementById("btn-new-idea").addEventListener("click", openNewIdeaModal);
  if (btnCloseNewModal) btnCloseNewModal.addEventListener("click", closeNewIdeaModal);
  if (btnCancelNewModal) btnCancelNewModal.addEventListener("click", closeNewIdeaModal);
  if (newIdeaBackdrop) newIdeaBackdrop.addEventListener("click", closeNewIdeaModal);

  if (newIdeaForm) {
    newIdeaForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const raw = newIdeaInput.value.trim();
      if (!raw) return;

      const priority = newIdeaPriority ? newIdeaPriority.value : "medium";
      closeNewIdeaModal();

      try {
        const data = await api("/ideas", {
          method: "POST",
          body: { raw_input: raw, source_type: "text" }
        });

        // Si se seleccionó prioridad distinta a medium, sincronizarla
        if (priority && priority !== "medium" && data && data.id) {
          try {
            await api(`/ideas/${data.id}`, { method: "PUT", body: { priority } });
            data.priority = priority;
          } catch (_) {}
        }

        ideas.push(data);
        renderBoard();
        showToast("💡 Idea guardada en Inbox");
      } catch (err) {
        showToast("Error al guardar la idea");
        console.error(err);
      }
    });
  }

  // --- Navegación por Píldoras en Móvil ---
  const colPills = document.querySelectorAll(".col-pill");
  colPills.forEach(pill => {
    pill.addEventListener("click", () => {
      colPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");

      const colName = pill.dataset.col;
      const targetCol = document.getElementById(`col-${colName}`);
      if (targetCol) {
        targetCol.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      }
    });
  });

  // Sincronizar píldora activa con el scroll del usuario en móvil
  const kanbanBoardEl = document.getElementById("kanban-board");
  if (kanbanBoardEl && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
          const status = entry.target.dataset.status;
          colPills.forEach(p => {
            if (p.dataset.col === status) {
              p.classList.add("active");
              p.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
            } else {
              p.classList.remove("active");
            }
          });
        }
      });
    }, {
      root: kanbanBoardEl,
      threshold: 0.5
    });

    document.querySelectorAll(".kanban-column").forEach(col => observer.observe(col));
  }

  // --- Vista Dual ---
  async function openDualView(ideaId) {
    currentIdeaId = ideaId;
    const idea = ideas.find(i => i.id === ideaId) || await api(`/ideas/${ideaId}`);

    // ID displays
    const idDisplay = document.getElementById("idea-id-display");
    if (idDisplay) idDisplay.textContent = ideaId;

    const copyCmdId = document.getElementById("copy-cmd-id");
    if (copyCmdId) copyCmdId.textContent = ideaId;

    // Título en cabecera
    const titleEl = document.getElementById("dual-idea-title");
    if (titleEl) titleEl.textContent = idea.title || `Idea #${ideaId}`;

    // Selects
    statusSelect.innerHTML = COLUMNS.map(s => `<option value="${s}" ${idea.status === s ? "selected" : ""}>${s}</option>`).join("");
    prioritySelect.innerHTML = ["low","medium","high","critical"].map(p => `<option value="${p}" ${idea.priority === p ? "selected" : ""}>${p}</option>`).join("");

    // Editor
    specEditor.value = idea.spec_body || "";
    if (saveIndicator) saveIndicator.textContent = "Sincronizado";

    // App URL & Banner
    const appUrlInput = document.getElementById("app-url-input");
    if (appUrlInput) appUrlInput.value = idea.app_url || "";

    const appBanner = document.getElementById("dual-app-banner");
    const openAppBtn = document.getElementById("btn-open-deployed-app");
    if (appBanner && openAppBtn) {
      if (idea.app_url && idea.app_url.trim()) {
        openAppBtn.href = idea.app_url;
        appBanner.classList.remove("hidden");
      } else {
        appBanner.classList.add("hidden");
      }
    }

    // Mobile tabs reset
    const tabLog = document.getElementById("tab-log");
    const tabEditor = document.getElementById("tab-editor");
    const dualLogCol = document.getElementById("dual-log-col");
    const dualEditorCol = document.getElementById("dual-editor-col");
    if (tabLog && tabEditor) {
      tabLog.classList.add("active");
      tabEditor.classList.remove("active");
      if (dualLogCol) dualLogCol.classList.remove("mobile-hidden");
      if (dualEditorCol) dualEditorCol.classList.add("mobile-hidden");
    }

    // Bitácora entries
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

  function closeDualView() {
    dualView.classList.add("hidden");
    currentIdeaId = null;
  }

  document.getElementById("btn-close-dual").addEventListener("click", closeDualView);
  document.getElementById("dual-view-backdrop").addEventListener("click", closeDualView);

  // Atajo de teclado: Escape cierra modales
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (newIdeaModal && !newIdeaModal.classList.contains("hidden")) {
        closeNewIdeaModal();
      } else if (dualView && !dualView.classList.contains("hidden")) {
        closeDualView();
      }
    }
  });

  // Guardar spec editado
  specEditor.addEventListener("blur", async () => {
    if (!currentIdeaId) return;
    try {
      if (saveIndicator) saveIndicator.textContent = "Guardando...";
      await api(`/ideas/${currentIdeaId}`, { method: "PUT", body: { spec_body: specEditor.value } });
      if (saveIndicator) saveIndicator.textContent = "✓ Sincronizado";
      const idea = ideas.find(i => i.id === currentIdeaId);
      if (idea) idea.spec_body = specEditor.value;
    } catch (err) {
      if (saveIndicator) saveIndicator.textContent = "Error al guardar";
    }
  });

  // Cambiar estado
  statusSelect.addEventListener("change", async () => {
    if (!currentIdeaId) return;
    try {
      await api(`/ideas/${currentIdeaId}/status`, { method: "POST", body: { status: statusSelect.value } });
      const idea = ideas.find(i => i.id === currentIdeaId);
      if (idea) idea.status = statusSelect.value;
      renderBoard();
      showToast(`Estado cambiado a ${statusSelect.value}`);
    } catch (err) {
      showToast("Error al actualizar estado");
    }
  });

  // Cambiar prioridad
  prioritySelect.addEventListener("change", async () => {
    if (!currentIdeaId) return;
    try {
      await api(`/ideas/${currentIdeaId}`, { method: "PUT", body: { priority: prioritySelect.value } });
      const idea = ideas.find(i => i.id === currentIdeaId);
      if (idea) idea.priority = prioritySelect.value;
      renderBoard();
      showToast(`Prioridad cambiada a ${prioritySelect.value}`);
    } catch (err) {
      showToast("Error al actualizar prioridad");
    }
  });

  // Cambiar App URL
  const appUrlInput = document.getElementById("app-url-input");
  if (appUrlInput) {
    appUrlInput.addEventListener("blur", async () => {
      if (!currentIdeaId) return;
      const val = appUrlInput.value.trim();
      try {
        if (saveIndicator) saveIndicator.textContent = "Guardando...";
        await api(`/ideas/${currentIdeaId}`, { method: "PUT", body: { app_url: val } });
        if (saveIndicator) saveIndicator.textContent = "✓ Sincronizado";
        const idea = ideas.find(i => i.id === currentIdeaId);
        if (idea) idea.app_url = val;

        const appBanner = document.getElementById("dual-app-banner");
        const openAppBtn = document.getElementById("btn-open-deployed-app");
        if (appBanner && openAppBtn) {
          if (val) {
            openAppBtn.href = val;
            appBanner.classList.remove("hidden");
          } else {
            appBanner.classList.add("hidden");
          }
        }
        renderBoard();
        showToast("App URL guardada");
      } catch (err) {
        if (saveIndicator) saveIndicator.textContent = "Error al guardar";
        showToast("Error al guardar App URL");
      }
    });
  }

  // --- Añadir nota a Bitácora ---
  logForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentIdeaId || !logInput.value.trim()) return;
    try {
      await api(`/ideas/${currentIdeaId}/log`, { method: "POST", body: { entry_text: logInput.value.trim(), source_type: "note" } });
      logInput.value = "";
      await openDualView(currentIdeaId);
      await loadIdeas();
      showToast("Nota agregada a la bitácora");
    } catch (err) {
      showToast("Error al agregar nota");
    }
  });

  // --- Estructurar con IA ---
  document.getElementById("btn-ai-structure").addEventListener("click", async () => {
    if (!currentIdeaId) return;
    const btn = document.getElementById("btn-ai-structure");
    const origText = btn.textContent;
    btn.textContent = "⏳ Estructurando...";
    btn.disabled = true;
    try {
      await api(`/ideas/${currentIdeaId}/structure`, { method: "POST" });
      await openDualView(currentIdeaId);
      await loadIdeas();
      showToast("✨ Idea estructurada exitosamente");
    } catch (err) {
      showToast("Error en estructuración con IA");
    } finally {
      btn.textContent = origText;
      btn.disabled = false;
    }
  });

  // --- Copiar comando ---
  document.getElementById("btn-copy-command").addEventListener("click", () => {
    const id = document.getElementById("idea-id-display").textContent;
    const cmd = `idea-cli init ${id}`;
    navigator.clipboard.writeText(cmd).then(() => {
      showToast(`✓ Copiado: ${cmd}`);
    }).catch(() => {
      showToast(`Comando: ${cmd}`);
    });
  });

  // --- Mobile Tabs en Vista Dual ---
  const tabLogBtn = document.getElementById("tab-log");
  const tabEditorBtn = document.getElementById("tab-editor");
  const dualLogColEl = document.getElementById("dual-log-col");
  const dualEditorColEl = document.getElementById("dual-editor-col");

  if (tabLogBtn && tabEditorBtn) {
    tabLogBtn.addEventListener("click", () => {
      tabLogBtn.classList.add("active");
      tabLogBtn.setAttribute("aria-selected", "true");
      tabEditorBtn.classList.remove("active");
      tabEditorBtn.setAttribute("aria-selected", "false");
      if (dualLogColEl) dualLogColEl.classList.remove("mobile-hidden");
      if (dualEditorColEl) dualEditorColEl.classList.add("mobile-hidden");
    });

    tabEditorBtn.addEventListener("click", () => {
      tabEditorBtn.classList.add("active");
      tabEditorBtn.setAttribute("aria-selected", "true");
      tabLogBtn.classList.remove("active");
      tabLogBtn.setAttribute("aria-selected", "false");
      if (dualEditorColEl) dualEditorColEl.classList.remove("mobile-hidden");
      if (dualLogColEl) dualLogColEl.classList.add("mobile-hidden");
    });
  }

  // --- Utilidades ---
  function esc(str) {
    if (!str) return "";
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }
})();
