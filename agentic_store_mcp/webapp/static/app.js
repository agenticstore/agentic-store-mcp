/* AgenticStore Setup — app.js */

// ── State ────────────────────────────────────────────────────────────────────

const state = {
  tools: [],
  enabledTools: new Set(),
  selectedClient: null,
};

// ── Section navigation ───────────────────────────────────────────────────────

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".setup-section").forEach((s) => s.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`section-${btn.dataset.section}`).classList.add("active");
  });
});

// ── Utilities ────────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function badge(text, cls) {
  return `<span class="status-badge ${cls}">${text}</span>`;
}

function connectorBadge(slug, connected) {
  const cls = connected ? "badge-connected" : "badge-disconnected";
  return `<span class="connector-badge ${cls}">${slug}</span>`;
}

// ── Section 1: Connectors ────────────────────────────────────────────────────

async function loadConnectors() {
  const container = document.getElementById("connectors-list");
  try {
    const data = await api("GET", "/api/connectors");
    container.innerHTML = data.connectors.map(renderConnector).join("");
    attachConnectorHandlers();
  } catch (e) {
    container.innerHTML = `<div class="status-error">Failed to load connectors: ${e.message}</div>`;
  }
}

function renderConnector(c) {
  const statusText = c.configured ? "Configured" : (c.fields.some((f) => !f.required) ? "Optional" : "Missing");
  const statusCls = c.configured ? "badge-ok" : (c.fields.some((f) => !f.required) ? "badge-optional" : "badge-missing");

  const fieldsHtml = c.fields
    .map(
      (f) => `
      <div class="field-row">
        <label>${f.label}${f.required ? "" : " <em>(optional)</em>"}</label>
        <div class="field-input-row">
          <input type="password" id="field-${c.slug}-${f.name}"
            placeholder="${f.placeholder}"
            autocomplete="off"
            data-slug="${c.slug}" data-field="${f.name}"
            value="${f.has_token ? "••••••••••••" : ""}"
          />
          <button class="btn btn-sm btn-ghost btn-save-token"
            data-slug="${c.slug}" data-field="${f.name}">Save</button>
          ${f.has_token ? `<button class="btn btn-sm btn-ghost btn-remove-token" data-slug="${c.slug}" data-field="${f.name}">Remove</button>` : ""}
        </div>
        <span class="field-desc">${f.description} &nbsp;·&nbsp; Env var: <code>${f.env_var}</code></span>
      </div>`
    )
    .join("");

  const testBtn = c.test_supported
    ? `<button class="btn btn-sm btn-secondary btn-test-connector" data-slug="${c.slug}">Test Connection</button>`
    : "";

  return `
    <div class="connector-card" id="connector-${c.slug}">
      <div class="connector-header">
        <div class="connector-title">
          <h3>${c.name}</h3>
          ${badge(statusText, statusCls)}
        </div>
        <a href="${c.docs_url}" target="_blank" class="btn btn-sm btn-ghost">Docs ↗</a>
      </div>
      <p class="connector-desc">${c.description}</p>
      <div class="connector-fields">${fieldsHtml}</div>
      <div class="connector-actions">
        ${testBtn}
        <span class="test-result" id="test-result-${c.slug}"></span>
      </div>
    </div>`;
}

function attachConnectorHandlers() {
  // Save token
  document.querySelectorAll(".btn-save-token").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const { slug, field } = btn.dataset;
      const input = document.getElementById(`field-${slug}-${field}`);
      const token = input.value.trim();
      if (!token || token.startsWith("•")) {
        alert("Enter a token value first.");
        return;
      }
      try {
        await api("POST", "/api/token", { service: `${slug}_${field}`, token });
        btn.textContent = "Saved ✓";
        setTimeout(() => loadConnectors(), 800);
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });

  // Remove token
  document.querySelectorAll(".btn-remove-token").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const { slug, field } = btn.dataset;
      if (!confirm(`Remove token for ${slug} ${field}?`)) return;
      try {
        await api("DELETE", `/api/token/${slug}_${field}`);
        loadConnectors();
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  });

  // Test connection
  document.querySelectorAll(".btn-test-connector").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const { slug } = btn.dataset;
      const result = document.getElementById(`test-result-${slug}`);

      // Check for any unsaved input in this connector's card
      const card = document.getElementById(`connector-${slug}`);
      const unsaved = [...card.querySelectorAll("input[data-slug]")].some(
        (inp) => inp.value.trim() && !inp.value.startsWith("•")
      );
      if (unsaved) {
        result.textContent = "⚠ Save your token first, then test.";
        result.className = "test-result test-warn";
        return;
      }

      result.textContent = "Testing…";
      result.className = "test-result";
      try {
        const data = await api("POST", `/api/connectors/${slug}/test`);
        result.textContent = data.ok ? `✓ ${data.detail}` : `✗ ${data.detail}`;
        result.className = `test-result ${data.ok ? "test-ok" : "test-fail"}`;
      } catch (e) {
        result.textContent = `✗ ${e.message}`;
        result.className = "test-result test-fail";
      }
    });
  });
}

// ── Section 2: Tools ─────────────────────────────────────────────────────────

async function loadTools() {
  const container = document.getElementById("tools-list");
  try {
    const data = await api("GET", "/api/tools");
    state.tools = data.tools;
    state.enabledTools = new Set(data.tools.map((t) => t.name));
    renderTools();
    updateToolCount();
  } catch (e) {
    container.innerHTML = `<div class="status-error">Failed to load tools: ${e.message}</div>`;
  }
}

function renderTools() {
  const container = document.getElementById("tools-list");

  // Group by module > submodule
  const groups = {};
  for (const tool of state.tools) {
    const key = tool.submodule ? `${tool.module} / ${tool.submodule}` : tool.module;
    if (!groups[key]) groups[key] = [];
    groups[key].push(tool);
  }

  container.innerHTML = Object.entries(groups)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([group, tools]) => {
      const rows = tools
        .map((tool) => {
          const checked = state.enabledTools.has(tool.name) ? "checked" : "";
          const badges = tool.connectors
            .map((slug) => connectorBadge(slug, tool.connector_status[slug]))
            .join("");
          return `
            <label class="tool-row">
              <input type="checkbox" class="tool-toggle" ${checked}
                data-name="${tool.name}" />
              <div class="tool-info">
                <div class="tool-name">${tool.name}</div>
                <div class="tool-desc">${tool.description}</div>
              </div>
              <div class="tool-badges">${badges}</div>
            </label>`;
        })
        .join("");
      return `<div class="submodule-group">
        <div class="submodule-label">${group}</div>
        ${rows}
      </div>`;
    })
    .join("");

  // Attach toggle handlers
  container.querySelectorAll(".tool-toggle").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) state.enabledTools.add(cb.dataset.name);
      else state.enabledTools.delete(cb.dataset.name);
      updateToolCount();
    });
  });
}

function updateToolCount() {
  const el = document.getElementById("tools-count");
  if (el) el.textContent = `${state.enabledTools.size} / ${state.tools.length} selected`;
}

document.getElementById("btn-select-all")?.addEventListener("click", () => {
  state.tools.forEach((t) => state.enabledTools.add(t.name));
  renderTools();
  updateToolCount();
});

document.getElementById("btn-deselect-all")?.addEventListener("click", () => {
  state.enabledTools.clear();
  renderTools();
  updateToolCount();
});

// ── Section 3: Clients ───────────────────────────────────────────────────────

async function loadClients() {
  const container = document.getElementById("clients-list");
  try {
    const data = await api("GET", "/api/clients");
    container.innerHTML = data.clients.map(renderClient).join("");
    attachClientHandlers();
  } catch (e) {
    container.innerHTML = `<div class="status-error">Failed to load clients: ${e.message}</div>`;
  }
}

function renderClient(c) {
  const existsHtml = c.config_exists
    ? `<span class="client-exists exists-yes">config found</span>`
    : `<span class="client-exists exists-no">no config yet</span>`;
  return `
    <label class="client-option" id="client-opt-${c.slug}">
      <input type="radio" name="client" value="${c.slug}" />
      <span class="client-name">${c.name}</span>
      <div>
        <div class="client-path">${c.config_path}</div>
        ${existsHtml}
      </div>
    </label>`;
}

function attachClientHandlers() {
  document.querySelectorAll('input[name="client"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      document.querySelectorAll(".client-option").forEach((o) => o.classList.remove("selected"));
      radio.closest(".client-option").classList.add("selected");
      state.selectedClient = radio.value;
      showApplyPanel();
    });
  });
}

function showApplyPanel() {
  const panel = document.getElementById("apply-panel");
  panel.style.display = "block";

  // Find client data
  api("GET", "/api/clients").then((data) => {
    const c = data.clients.find((cl) => cl.slug === state.selectedClient);
    if (c) {
      document.getElementById("apply-config-path").textContent = c.config_path;
      const launchBtn = document.getElementById("btn-launch");
      if (c.launch_supported) {
        launchBtn.style.display = "inline-flex";
        launchBtn.textContent = `Open ${c.name}`;
      } else {
        launchBtn.style.display = "none";
      }
    }
  });
}

document.getElementById("btn-apply")?.addEventListener("click", async () => {
  if (!state.selectedClient) {
    alert("Select a client first.");
    return;
  }
  const statusEl = document.getElementById("apply-status");
  statusEl.textContent = "Writing config…";
  statusEl.className = "apply-status";
  try {
    const enabledList = [...state.enabledTools];
    const result = await api("POST", "/api/apply", {
      client: state.selectedClient,
      enabled_tools: enabledList,
    });
    statusEl.textContent = `✓ Config written to ${result.path}`;
    statusEl.className = "apply-status status-success";
  } catch (e) {
    statusEl.textContent = `✗ ${e.message}`;
    statusEl.className = "apply-status status-error";
  }
});

document.getElementById("btn-launch")?.addEventListener("click", async () => {
  if (!state.selectedClient) return;
  try {
    await api("POST", "/api/launch", { client: state.selectedClient });
  } catch (e) {
    alert(`Launch failed: ${e.message}`);
  }
});


// ── Section 4: Agent Orchestration ───────────────────────────────────────────

// Sub-tab switching
document.querySelectorAll(".orch-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".orch-tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".orch-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`orch-${tab.dataset.orch}`).classList.add("active");
    // Lazy-load on first open
    if (tab.dataset.orch === "facts") loadFacts();
    if (tab.dataset.orch === "logs") loadLogs();
    if (tab.dataset.orch === "strategy") loadStrategy();
    if (tab.dataset.orch === "checkpoints") loadCheckpoints();
  });
});

// Also load orchestration data when switching to section 4
document.querySelectorAll(".nav-btn").forEach((btn) => {
  if (btn.dataset.section === "orchestration") {
    btn.addEventListener("click", () => {
      loadMemoryStats();
      loadCheckpoints();
    });
  }
});

// ─── Memory Stats ──────────────────────────────────────────────────────────

async function loadMemoryStats() {
  const el = document.getElementById("mem-stats");
  try {
    const data = await api("GET", "/api/memory/status");
    if (data.available === false) {
      el.innerHTML = `<div class="no-items">Memory module unavailable.</div>`;
      return;
    }
    el.innerHTML = `
      <div class="mem-stat-card">
        <div class="label">Facts stored</div>
        <div class="value">${data.fact_count ?? 0}</div>
      </div>
      <div class="mem-stat-card">
        <div class="label">Checkpoints</div>
        <div class="value">${data.checkpoint_count ?? 0}</div>
      </div>
      <div class="mem-stat-card">
        <div class="label">Log size</div>
        <div class="value">${data.log_size_kb ?? 0}</div>
        <div class="sub">KB</div>
      </div>
      <div class="mem-stat-card">
        <div class="label">Last checkpoint</div>
        <div class="value" style="font-size:14px;padding-top:4px">${data.last_checkpoint || "—"}</div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="no-items">Could not load memory stats: ${e.message}</div>`;
  }
}

// ─── Checkpoints ───────────────────────────────────────────────────────────

async function loadCheckpoints() {
  const el = document.getElementById("checkpoints-list");
  try {
    const data = await api("GET", "/api/memory/checkpoints");
    if (!data.checkpoints.length) {
      el.innerHTML = `<div class="no-items">No checkpoints yet. Save one to preserve your session context.</div>`;
      return;
    }
    el.innerHTML = data.checkpoints.map((cp) => `
      <div class="checkpoint-card">
        <div class="cp-main">
          <div class="cp-name">${cp.name}</div>
          <div class="cp-task">${cp.task || "—"}</div>
          <div class="cp-meta">
            ${cp.client ? `<span>${cp.client}</span>` : ""}
            ${cp.timestamp ? `<span>${new Date(cp.timestamp).toLocaleString()}</span>` : ""}
          </div>
        </div>
        <div class="cp-actions">
          <button class="btn btn-sm btn-secondary btn-restore-cp" data-name="${cp.name}">Restore</button>
          <button class="btn btn-sm btn-ghost btn-delete-cp" data-name="${cp.name}">Delete</button>
        </div>
      </div>`).join("");

    el.querySelectorAll(".btn-restore-cp").forEach((btn) => {
      btn.addEventListener("click", () => restoreCheckpoint(btn.dataset.name));
    });
    el.querySelectorAll(".btn-delete-cp").forEach((btn) => {
      btn.addEventListener("click", () => deleteCheckpoint(btn.dataset.name));
    });
  } catch (e) {
    el.innerHTML = `<div class="no-items status-error">Error: ${e.message}</div>`;
  }
}

async function restoreCheckpoint(name) {
  try {
    const data = await api("POST", "/api/memory/restore", { name });
    const cp = data.checkpoint;
    const detail = [
      `Task: ${cp.task || "—"}`,
      cp.decisions?.length ? `Decisions: ${cp.decisions.join("; ")}` : "",
      cp.next_steps?.length ? `Next steps: ${cp.next_steps.join("; ")}` : "",
      cp.context?.notes ? `Notes: ${cp.context.notes}` : "",
    ].filter(Boolean).join("\n");
    alert(`Checkpoint restored: ${name}\n\n${detail}`);
  } catch (e) {
    alert(`Restore failed: ${e.message}`);
  }
}

async function deleteCheckpoint(name) {
  if (!confirm(`Delete checkpoint "${name}"? This cannot be undone.`)) return;
  try {
    await api("DELETE", `/api/memory/checkpoint/${name}`);
    loadCheckpoints();
    loadMemoryStats();
  } catch (e) {
    alert(`Delete failed: ${e.message}`);
  }
}

// New checkpoint form
document.getElementById("btn-new-checkpoint")?.addEventListener("click", () => {
  const form = document.getElementById("new-checkpoint-form");
  form.style.display = form.style.display === "none" ? "block" : "none";
});

document.getElementById("btn-cancel-checkpoint")?.addEventListener("click", () => {
  document.getElementById("new-checkpoint-form").style.display = "none";
});

document.getElementById("btn-save-checkpoint")?.addEventListener("click", async () => {
  const task = document.getElementById("cp-task").value.trim();
  if (!task) { alert("Task description is required."); return; }

  const name = document.getElementById("cp-name").value.trim() || null;
  const decisions = document.getElementById("cp-decisions").value.trim().split("\n").filter(Boolean);
  const nextSteps = document.getElementById("cp-next-steps").value.trim().split("\n").filter(Boolean);
  const notes = document.getElementById("cp-notes").value.trim();
  const statusEl = document.getElementById("cp-save-status");

  statusEl.textContent = "Saving…";
  statusEl.className = "cp-status";
  try {
    const data = await api("POST", "/api/memory/checkpoint", {
      task, name, decisions, next_steps: nextSteps, notes,
    });
    statusEl.textContent = `✓ Saved as "${data.name}"`;
    statusEl.className = "cp-status status-success";
    // Reset form
    ["cp-task", "cp-name", "cp-decisions", "cp-next-steps", "cp-notes"].forEach((id) => {
      document.getElementById(id).value = "";
    });
    loadCheckpoints();
    loadMemoryStats();
    setTimeout(() => {
      document.getElementById("new-checkpoint-form").style.display = "none";
      statusEl.textContent = "";
    }, 2000);
  } catch (e) {
    statusEl.textContent = `✗ ${e.message}`;
    statusEl.className = "cp-status status-error";
  }
});

// ─── Strategy ──────────────────────────────────────────────────────────────

async function loadStrategy() {
  const editor = document.getElementById("strategy-editor");
  try {
    const data = await api("GET", "/api/memory/strategy");
    editor.value = data.content;
  } catch (e) {
    editor.placeholder = `Error loading strategy: ${e.message}`;
  }
}

document.getElementById("btn-save-strategy")?.addEventListener("click", async () => {
  const content = document.getElementById("strategy-editor").value;
  const statusEl = document.getElementById("strategy-status");
  statusEl.textContent = "Saving…";
  try {
    await api("POST", "/api/memory/strategy", { content });
    statusEl.textContent = "✓ Strategy saved";
    statusEl.className = "cp-status status-success";
    setTimeout(() => { statusEl.textContent = ""; }, 2000);
  } catch (e) {
    statusEl.textContent = `✗ ${e.message}`;
    statusEl.className = "cp-status status-error";
  }
});

// ─── Facts ─────────────────────────────────────────────────────────────────

async function loadFacts() {
  const el = document.getElementById("facts-list");
  try {
    const data = await api("GET", "/api/memory/facts");
    if (!data.facts.length) {
      el.innerHTML = `<div class="no-items">No facts stored yet.</div>`;
      return;
    }
    el.innerHTML = data.facts.map((f) => `
      <div class="fact-row">
        <span class="fact-key">${f.key}</span>
        <span class="fact-value">${JSON.stringify(f.value)}</span>
        <span class="fact-category">${f.category}</span>
        <span class="fact-time">${f.updated_at ? new Date(f.updated_at).toLocaleString() : ""}</span>
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="no-items status-error">Error: ${e.message}</div>`;
  }
}

document.getElementById("btn-refresh-facts")?.addEventListener("click", loadFacts);

// ─── Logs ──────────────────────────────────────────────────────────────────

async function loadLogs() {
  const el = document.getElementById("logs-list");
  try {
    const data = await api("GET", "/api/memory/logs?limit=50");
    if (!data.entries.length) {
      el.innerHTML = `<div class="no-items">No log entries yet.</div>`;
      return;
    }
    // Newest first
    const entries = [...data.entries].reverse();
    el.innerHTML = entries.map((e) => `
      <div class="log-row">
        <span class="log-ts">${e.timestamp ? new Date(e.timestamp).toLocaleString() : ""}</span>
        <span class="log-event">${e.event || ""}</span>
        <span class="log-detail">${e.detail || ""}</span>
      </div>`).join("");
  } catch (e) {
    el.innerHTML = `<div class="no-items status-error">Error: ${e.message}</div>`;
  }
}

document.getElementById("btn-refresh-logs")?.addEventListener("click", loadLogs);

// ── Docker detection ──────────────────────────────────────────────────────────

function _buildDockerSnippet(enabledTools) {
  const toolsArg = enabledTools && enabledTools.length
    ? [",\n               \"--tools\", \"" + enabledTools.join(",") + "\""]
    : [];
  const args = [
    "\"run\", \"-i\", \"--rm\"",
    "    \"-v\", \"agentic-store-mcp_agentic-store-memory:/root/.config/agentic-store\"",
    "    \"--network\", \"agentic-store-mcp_default\"",
    "    \"-e\", \"SEARXNG_URL=http://searxng:8080\"" + (toolsArg.length ? "," : ""),
    ...toolsArg.map(a => "    " + a),
    "    \"agentic-store-mcp\"",
  ].join(",\n               ");

  return `{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
               ${args}
      ]
    }
  }
}`;
}

async function initDockerMode() {
  const data = await api("GET", "/api/env").catch(() => ({ is_docker: false }));
  if (!data.is_docker) return;

  // Switch Clients section to Docker UI
  document.getElementById("clients-subtitle").textContent =
    "Running in Docker — copy the config snippet into your client.";
  document.getElementById("clients-native").style.display = "none";
  document.getElementById("clients-docker").style.display = "block";

  // Populate snippets
  const snippet = _buildDockerSnippet([...state.enabledTools]);
  document.getElementById("snippet-claude").textContent = snippet;
  document.getElementById("snippet-cursor").textContent = snippet;

  // Copy buttons
  document.querySelectorAll(".btn-copy").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      navigator.clipboard.writeText(target.textContent).then(() => {
        btn.textContent = "Copied ✓";
        btn.classList.add("copied");
        setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 2000);
      });
    });
  });
}

// ── Troubleshoot — inline "go to tab" links ───────────────────────────────────

document.querySelectorAll(".ts-inline-link[data-goto]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.goto;
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".setup-section").forEach((s) => s.classList.remove("active"));
    const navBtn = document.querySelector(`.nav-btn[data-section="${target}"]`);
    if (navBtn) navBtn.classList.add("active");
    const section = document.getElementById(`section-${target}`);
    if (section) section.classList.add("active");
  });
});

// ── Init ─────────────────────────────────────────────────────────────────────

loadConnectors();
loadTools();
loadClients();
initDockerMode();
