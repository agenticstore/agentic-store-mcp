/* AgenticStore Setup — app.js */

// ── State ────────────────────────────────────────────────────────────────────

const state = {
  tools: [],
  enabledTools: new Set(),
  selectedClient: null,
  selectedClientName: null,
};

// ── Section navigation ───────────────────────────────────────────────────────

// Top-level sections: "firewall" | "mcp-hub"
function activateSection(sectionId) {
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".setup-section").forEach((s) => s.classList.remove("active"));
  const btn = document.querySelector(`.nav-btn[data-section="${sectionId}"]`);
  const section = document.getElementById(`section-${sectionId}`);
  if (btn) btn.classList.add("active");
  if (section) section.classList.add("active");
}

// MCP Hub sub-panels: "connectors" | "tools" | "clients" | "orchestration" | "troubleshoot"
function activateMcpPanel(panelId) {
  document.querySelectorAll(".mcp-tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".mcp-panel").forEach((p) => p.classList.remove("active"));
  const tab = document.querySelector(`.mcp-tab[data-mcp="${panelId}"]`);
  const panel = document.getElementById(`mcp-panel-${panelId}`);
  if (tab) tab.classList.add("active");
  if (panel) panel.classList.add("active");
  // Lazy-load data when switching to these panels
  if (panelId === "orchestration") { loadMemoryStats(); loadCheckpoints(); }
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const sec = btn.dataset.section;
    activateSection(sec);
    location.hash = sec;
    if (sec === "firewall") {
      loadFirewallStatus();
      loadFirewallConfig();
      loadSystemProxyStatus();
      _startLogAutoRefresh();
    } else {
      _stopLogAutoRefresh();
    }
  });
});

document.querySelectorAll(".mcp-tab").forEach((tab) => {
  tab.addEventListener("click", () => activateMcpPanel(tab.dataset.mcp));
});

// Restore section from URL hash on page load
(function () {
  const hash = location.hash.replace("#", "");
  // Top-level sections
  if (hash === "firewall" || hash === "mcp-hub") {
    activateSection(hash);
    return;
  }
  // Legacy hash values — route to mcp-hub and activate correct panel
  const mcpPanels = ["connectors", "tools", "clients", "orchestration", "troubleshoot"];
  if (mcpPanels.includes(hash)) {
    activateSection("mcp-hub");
    activateMcpPanel(hash);
  }
})();

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
      state.selectedClientName = c.name;
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

document.getElementById("btn-launch")?.addEventListener("click", () => {
  if (!state.selectedClient) return;
  const name = state.selectedClientName || state.selectedClient;
  document.getElementById("restart-client-name").textContent = name;
  document.getElementById("restart-client-name2").textContent = name;
  document.getElementById("restart-modal").style.display = "flex";
});

document.getElementById("modal-cancel")?.addEventListener("click", () => {
  document.getElementById("restart-modal").style.display = "none";
});

document.getElementById("modal-confirm")?.addEventListener("click", async () => {
  const syncFirst = document.getElementById("modal-sync-env")?.checked ?? true;
  document.getElementById("restart-modal").style.display = "none";
  const statusEl = document.getElementById("apply-status");
  statusEl.textContent = syncFirst ? "Syncing environment…" : "Restarting…";
  statusEl.className = "apply-status";
  try {
    await api("POST", "/api/restart", { client: state.selectedClient, sync_first: syncFirst });
    statusEl.textContent = `✓ ${state.selectedClientName || state.selectedClient} restarted`;
    statusEl.className = "apply-status status-success";
  } catch (e) {
    statusEl.textContent = `✗ Restart failed: ${e.message}`;
    statusEl.className = "apply-status status-error";
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

// Orchestration data is loaded inside activateMcpPanel("orchestration")

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
    // All troubleshoot links lead to MCP Hub sub-panels
    activateSection("mcp-hub");
    activateMcpPanel(target);
  });
});

// ── Init ─────────────────────────────────────────────────────────────────────

loadConnectors();
loadTools();
loadClients();
initDockerMode();
// Firewall is the default active section — load its data on boot
loadFirewallStatus();
loadFirewallConfig();
loadSystemProxyStatus();

// ── Section 5: Prompt Firewall ────────────────────────────────────────────────

// Sub-tab switching for firewall
document.querySelectorAll(".orch-tab[data-fw]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".orch-tab[data-fw]").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll("#section-firewall .orch-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`fw-${tab.dataset.fw}`).classList.add("active");
    if (tab.dataset.fw === "logs") loadFirewallLogs();
    if (tab.dataset.fw === "recordings") { loadRecordings(); loadRecordingToggleState(); }
  });
});

// Firewall init is handled in the main nav-btn click handler above

async function loadFirewallStatus() {
  try {
    const data = await api("GET", "/api/firewall/status");
    const dot = document.getElementById("fw-status-dot");
    const text = document.getElementById("fw-status-text");
    const port = document.getElementById("fw-status-port");
    const btn = document.getElementById("btn-fw-toggle");
    const hint = document.getElementById("fw-setup-hint");

    dot.className = `fw-dot ${data.running ? "fw-dot-on" : "fw-dot-off"}`;
    text.textContent = data.running ? "Proxy running" : "Proxy stopped";
    port.textContent = data.running ? `localhost:${data.port}` : "";
    btn.textContent = data.running ? "Stop Proxy" : "Start Proxy";
    btn.className = `btn ${data.running ? "btn-ghost" : "btn-primary"}`;
    hint.style.display = data.running ? "block" : "none";
    const clientsCard = document.getElementById("fw-clients-card");
    if (clientsCard) clientsCard.style.display = data.running ? "block" : "none";
    if (data.running) loadClientStatus();

    // Update endpoints with actual port
    ["fw-endpoint-anthropic", "fw-endpoint-openai", "fw-endpoint-google"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        const suffix = id === "fw-endpoint-openai" ? "/openai" : id === "fw-endpoint-google" ? "/google" : "";
        el.textContent = `http://localhost:${data.port}${suffix}`;
      }
    });

    document.getElementById("fw-stat-total").textContent = data.requests_total;
    document.getElementById("fw-stat-redacted").textContent = data.redacted_total;
    document.getElementById("fw-stat-blocked").textContent = data.blocked_total;

    // Ollama status
    const ollamaEl = document.getElementById("fw-ollama-status");
    if (ollamaEl) {
      ollamaEl.innerHTML = data.ollama_available
        ? `<span style="color:var(--success)">✓ Ollama is running</span>`
        : `<span style="color:var(--text-muted)">⚠ Ollama not detected — <a href="https://ollama.com/download" target="_blank" style="color:var(--accent-hover)">Install Ollama ↗</a> to enable LLM layer</span>`;
    }
  } catch (e) {
    console.error("Firewall status error:", e);
  }
}

async function loadFirewallConfig() {
  try {
    const data = await api("GET", "/api/firewall/config");

    // Deterministic toggles
    document.getElementById("fw-det-pii").checked = data.deterministic?.pii ?? true;
    document.getElementById("fw-det-secrets").checked = data.deterministic?.secrets ?? true;
    document.getElementById("fw-det-paths").checked = data.deterministic?.file_paths ?? true;
    document.getElementById("fw-det-ips").checked = data.deterministic?.ip_addresses ?? true;

    // Mode
    const modeVal = data.mode || "redact";
    document.querySelectorAll('input[name="fw-mode"]').forEach((r) => {
      r.checked = r.value === modeVal;
      r.closest(".fw-mode-option")?.classList.toggle("selected", r.value === modeVal);
    });

    // LLM
    const llmEnabled = data.llm?.enabled ?? false;
    document.getElementById("fw-llm-enabled").checked = llmEnabled;
    document.getElementById("fw-llm-controls").style.display = llmEnabled ? "block" : "none";

    // Predefined prompt
    const predPrompt = document.getElementById("fw-predefined-prompt");
    if (predPrompt) predPrompt.value = data.predefined_prompt || "";

    // Custom rules
    const rulesEl = document.getElementById("fw-custom-rules");
    if (rulesEl) rulesEl.value = (data.llm?.custom_rules || []).join("\n");

    // Load models if LLM enabled
    if (llmEnabled) loadFirewallModels(data.llm?.model);
  } catch (e) {
    console.error("Firewall config error:", e);
  }
}

async function loadFirewallModels(selectedModel) {
  const select = document.getElementById("fw-model-select");
  if (!select) return;
  try {
    const data = await api("GET", "/api/firewall/models");
    if (!data.available) {
      select.innerHTML = `<option value="">Ollama not available</option>`;
      return;
    }
    select.innerHTML = `<option value="">— select a model —</option>` +
      data.models.map((m) => `<option value="${m.name}" ${m.name === selectedModel ? "selected" : ""}>${m.name}</option>`).join("");
  } catch (e) {
    select.innerHTML = `<option value="">Error loading models</option>`;
  }
}

// Toggle start/stop proxy
document.getElementById("btn-fw-toggle")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-fw-toggle");
  const isRunning = btn.textContent.trim() === "Stop Proxy";
  btn.disabled = true;
  btn.textContent = isRunning ? "Stopping…" : "Starting…";
  try {
    await api("POST", isRunning ? "/api/firewall/stop" : "/api/firewall/start");
    await loadFirewallStatus();
  } catch (e) {
    alert(`Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
});

// LLM enable toggle
document.getElementById("fw-llm-enabled")?.addEventListener("change", (e) => {
  const controls = document.getElementById("fw-llm-controls");
  controls.style.display = e.target.checked ? "block" : "none";
  if (e.target.checked) loadFirewallModels();
});

// Mode radio
document.querySelectorAll('input[name="fw-mode"]').forEach((r) => {
  r.addEventListener("change", () => {
    document.querySelectorAll(".fw-mode-option").forEach((o) => o.classList.remove("selected"));
    r.closest(".fw-mode-option")?.classList.add("selected");
  });
});

// Refresh models button
document.getElementById("btn-fw-refresh-models")?.addEventListener("click", () => loadFirewallModels());

// Pull model
document.getElementById("btn-fw-pull-model")?.addEventListener("click", async () => {
  const input = document.getElementById("fw-model-input");
  const modelName = input.value.trim();
  if (!modelName) { alert("Enter a model name first."); return; }

  const btn = document.getElementById("btn-fw-pull-model");
  const progress = document.getElementById("fw-pull-progress");
  const bar = document.getElementById("fw-pull-bar");
  const status = document.getElementById("fw-pull-status");

  btn.disabled = true;
  progress.style.display = "block";
  bar.style.width = "5%";
  status.textContent = "Starting download…";

  try {
    const resp = await fetch("/api/firewall/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const chunk = JSON.parse(line.slice(6));
          if (chunk.error) throw new Error(chunk.error);
          if (chunk.done) {
            bar.style.width = "100%";
            status.textContent = "Download complete ✓";
            loadFirewallModels(modelName);
            input.value = "";
            break;
          }
          if (chunk.total && chunk.completed) {
            const pct = Math.round((chunk.completed / chunk.total) * 100);
            bar.style.width = `${pct}%`;
          }
          if (chunk.status) status.textContent = chunk.status;
        } catch (parseErr) { /* skip */ }
      }
    }
  } catch (e) {
    status.textContent = `✗ ${e.message}`;
    status.style.color = "var(--danger)";
  } finally {
    btn.disabled = false;
  }
});

// Save firewall settings
document.getElementById("btn-fw-save")?.addEventListener("click", async () => {
  const statusEl = document.getElementById("fw-save-status");
  statusEl.textContent = "Saving…";
  statusEl.className = "cp-status";

  const customRulesText = document.getElementById("fw-custom-rules")?.value || "";
  const customRules = customRulesText.split("\n").map((s) => s.trim()).filter(Boolean);
  const selectedModel = document.getElementById("fw-model-select")?.value || null;
  const modeEl = document.querySelector('input[name="fw-mode"]:checked');

  try {
    await api("POST", "/api/firewall/config", {
      deterministic: {
        pii: document.getElementById("fw-det-pii").checked,
        secrets: document.getElementById("fw-det-secrets").checked,
        file_paths: document.getElementById("fw-det-paths").checked,
        ip_addresses: document.getElementById("fw-det-ips").checked,
      },
      llm: {
        enabled: document.getElementById("fw-llm-enabled").checked,
        model: selectedModel,
        custom_rules: customRules,
      },
      mode: modeEl?.value || "redact",
    });
    statusEl.textContent = "✓ Settings saved";
    statusEl.className = "cp-status status-success";
    setTimeout(() => { statusEl.textContent = ""; }, 2000);
  } catch (e) {
    statusEl.textContent = `✗ ${e.message}`;
    statusEl.className = "cp-status status-error";
  }
});

// Copy endpoint buttons
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-fw-copy");
  if (!btn) return;
  const target = document.getElementById(btn.dataset.target);
  if (!target) return;
  navigator.clipboard.writeText(target.textContent).then(() => {
    btn.textContent = "Copied ✓";
    setTimeout(() => { btn.textContent = "Copy"; }, 2000);
  });
});

// Audit log
async function loadFirewallLogs() {
  const el = document.getElementById("fw-logs-list");
  try {
    const data = await api("GET", "/api/firewall/logs?limit=100");
    if (!data.entries.length) {
      el.innerHTML = `<div class="no-items">No audit entries yet. Start the firewall and send a request through Claude.</div>`;
      return;
    }
    const persistNote = `<div class="fw-log-persist-note">Showing ${data.entries.length} entries — log persists across restarts. <a href="#" onclick="document.getElementById('btn-fw-clear-logs').click();return false">Clear</a> to reset.</div>`;
    el.innerHTML = persistNote + data.entries.map((e, i) => {
      if (e.event === "session_start") {
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleString(undefined, {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}) : "";
        return `<div class="fw-log-session-sep">── Session started ${ts} ──</div>`;
      }
      const eventCls = e.event === "clean" ? "fw-log-event-clean"
        : e.event === "redacted" ? "fw-log-event-redacted"
        : e.event === "blocked" ? "fw-log-event-blocked"
        : "fw-log-event-other";
      const safeBadge = e.safe
        ? `<span class="fw-log-badge badge-ok">safe</span>`
        : `<span class="fw-log-badge badge-warn">unsafe</span>`;
      const ts = e.timestamp ? new Date(e.timestamp).toLocaleString(undefined, {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"}) : "";
      const findings = e.findings || [];
      const hasFindings = findings.length > 0;
      const findingsHtml = hasFindings ? `
        <div class="fw-log-findings" id="fw-log-findings-${i}" style="display:none">
          ${findings.map(f => `
            <div class="fw-finding-row">
              <span class="fw-finding-type">${f.type || f.layer || ""}</span>
              <span class="fw-finding-original">${escapeHtml(String(f.original || ""))}</span>
              <span class="fw-finding-arrow">→</span>
              <span class="fw-finding-replacement">${escapeHtml(String(f.replacement || f.reason || ""))}</span>
            </div>`).join("")}
        </div>` : "";
      return `
        <div class="fw-log-row ${hasFindings ? "fw-log-row-expandable" : ""}" data-idx="${i}">
          <span class="fw-log-ts">${ts}</span>
          <span class="fw-log-event ${eventCls}">${e.event}</span>
          ${safeBadge}
          <span class="fw-log-detail">${e.detail}</span>
          ${hasFindings ? `<span class="fw-log-expand-icon" id="fw-log-icon-${i}" title="Expand">▶</span>` : ""}
        </div>
        ${findingsHtml}`;
    }).join("");
  } catch (e) {
    el.innerHTML = `<div class="no-items status-error">Error: ${e.message}</div>`;
  }
}

function toggleLogFindings(i) {
  const el = document.getElementById(`fw-log-findings-${i}`);
  const icon = document.getElementById(`fw-log-icon-${i}`);
  if (!el) return;
  const open = el.style.display !== "none";
  el.style.display = open ? "none" : "block";
  if (icon) icon.textContent = open ? "▶" : "▼";
}

// Event delegation: only toggle when the expand icon is clicked (not the full row)
// This lets users select/copy text in the row and findings without collapsing
document.getElementById("fw-logs-list")?.addEventListener("click", (e) => {
  const icon = e.target.closest(".fw-log-expand-icon");
  if (!icon) return;
  const row = icon.closest(".fw-log-row");
  if (!row) return;
  const idx = parseInt(row.dataset.idx, 10);
  if (!isNaN(idx)) toggleLogFindings(idx);
});

// Detection tester
document.getElementById("btn-fw-tester-run")?.addEventListener("click", async () => {
  const input = document.getElementById("fw-tester-input");
  const resultEl = document.getElementById("fw-tester-result");
  const btn = document.getElementById("btn-fw-tester-run");
  const text = input?.value?.trim();
  if (!text) return;

  btn.disabled = true;
  btn.textContent = "Scanning…";
  resultEl.style.display = "none";

  try {
    const res = await fetch("/api/firewall/test/sanitize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      resultEl.innerHTML = `<div style="color:var(--danger)">Error ${res.status}: ${err.detail || "Request failed"}</div>`;
      resultEl.style.display = "block";
      return;
    }
    const data = await res.json();
    const findings = data.findings || [];

    if (!findings.length) {
      resultEl.innerHTML = `<div class="fw-tester-clean">✓ No findings — text is clean</div>`;
    } else {
      resultEl.innerHTML = `
        <div class="fw-tester-summary">${findings.length} finding${findings.length !== 1 ? "s" : ""} detected${data.llm_used ? " (det + LLM)" : " (deterministic)"}</div>
        ${findings.map(f => `
          <div class="fw-finding-row">
            <span class="fw-finding-type">${f.type}</span>
            <span class="fw-finding-layer">${f.layer}</span>
            <span class="fw-finding-original">${escapeHtml(String(f.original || ""))}</span>
            <span class="fw-finding-arrow">→</span>
            <span class="fw-finding-replacement">${escapeHtml(String(f.replacement || f.reason || ""))}</span>
          </div>`).join("")}
        <div class="fw-tester-redacted"><strong>Redacted:</strong> ${escapeHtml(data.redacted)}</div>`;
    }
    resultEl.style.display = "block";
  } catch (e) {
    resultEl.innerHTML = `<div style="color:var(--danger)">Error: ${e.message}</div>`;
    resultEl.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "Scan";
  }
});

document.getElementById("btn-fw-refresh-logs")?.addEventListener("click", loadFirewallLogs);

document.getElementById("btn-fw-clear-logs")?.addEventListener("click", async () => {
  if (!confirm("Clear all firewall audit logs?")) return;
  await api("DELETE", "/api/firewall/logs");
  loadFirewallLogs();
  loadFirewallStatus();
});


// Auto-refresh audit log every 4s while logs sub-tab is visible
let _fwLogInterval = null;

function _startLogAutoRefresh() {
  if (_fwLogInterval) return;
  _fwLogInterval = setInterval(() => {
    const logsPanel = document.getElementById("fw-logs");
    if (logsPanel?.classList.contains("active")) loadFirewallLogs();
  }, 4000);
  const liveEl = document.getElementById("fw-log-live");
  if (liveEl) liveEl.style.display = "inline";
}

function _stopLogAutoRefresh() {
  clearInterval(_fwLogInterval);
  _fwLogInterval = null;
  const liveEl = document.getElementById("fw-log-live");
  if (liveEl) liveEl.style.display = "none";
}

// Auto-refresh is started/stopped in the main nav-btn click handler above

// ── System Proxy ──────────────────────────────────────────────────────────────

const SYS_STEPS = [
  { id: "ca_generate", label: "Generate CA certificate",         hint: "" },
  { id: "ca_install",  label: "Trust CA in login keychain",       hint: "No password required" },
  { id: "net_proxy",   label: "Configure macOS network proxy",   hint: "" },
  { id: "tls_start",   label: "Start TLS proxy",                 hint: "" },
];

async function loadSystemProxyStatus() {
  try {
    const data = await api("GET", "/api/firewall/system/status");

    // Update badges
    const setBadge = (id, ok, label) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = ok ? `${label} ✓` : `${label} —`;
      el.className = `fw-sys-badge ${ok ? "fw-sys-badge-ok" : "fw-sys-badge-off"}`;
    };
    setBadge("badge-ca",  data.ca_installed,       "CA");
    setBadge("badge-net", data.proxy_configured,   "Network");
    setBadge("badge-tls", data.tls_proxy_running,  "Proxy");

    // Toggle install/uninstall buttons
    const installBtn   = document.getElementById("btn-sys-install");
    const uninstallBtn = document.getElementById("btn-sys-uninstall");
    if (installBtn && uninstallBtn) {
      installBtn.style.display   = data.fully_active ? "none"         : "inline-flex";
      uninstallBtn.style.display = data.fully_active ? "inline-flex"  : "none";
    }
  } catch (e) {
    console.error("System proxy status error:", e);
  }
}

function _buildModalSteps(stepIds) {
  const container = document.getElementById("fw-sys-steps");
  container.innerHTML = stepIds.map(({ id, label, hint }) => `
    <div class="fw-sys-step-row" id="sys-step-${id}">
      <span class="fw-step-icon">○</span>
      <div class="fw-step-text">
        <div class="fw-step-msg">${label}</div>
        ${hint ? `<div class="fw-step-hint">${hint}</div>` : ""}
        <div class="fw-step-err" id="sys-step-err-${id}" style="display:none"></div>
      </div>
    </div>`).join("");
}

function _updateStep(id, status, message, error) {
  const row = document.getElementById(`sys-step-${id}`);
  if (!row) return;
  const icon = row.querySelector(".fw-step-icon");
  const msg  = row.querySelector(".fw-step-msg");
  const err  = row.querySelector(".fw-step-err");

  row.className = `fw-sys-step-row step-${status}`;

  if (status === "running") {
    icon.innerHTML = `<span class="fw-spinner"></span>`;
    if (message) msg.textContent = message;
  } else if (status === "done") {
    icon.textContent = "✓";
    icon.style.color = "var(--success)";
    if (message) msg.textContent = message;
  } else if (status === "error") {
    icon.textContent = "✗";
    icon.style.color = "var(--danger)";
    if (error) { err.textContent = error; err.style.display = "block"; }
  }
}

async function _runSysProxyFlow(endpoint, title, steps) {
  // Show modal
  document.getElementById("fw-sys-modal-title").textContent = title;
  document.getElementById("fw-sys-modal-footer").style.display = "none";
  _buildModalSteps(steps);
  document.getElementById("fw-sys-modal").style.display = "flex";

  try {
    const resp = await fetch(endpoint, { method: "POST" });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.step !== "complete") {
            _updateStep(ev.step, ev.status, ev.message, ev.error);
          }
        } catch (_) { /* skip */ }
      }
    }
  } catch (e) {
    console.error("System proxy flow error:", e);
  }

  // Show done button, refresh status
  document.getElementById("fw-sys-modal-footer").style.display = "flex";
  loadSystemProxyStatus();
  loadFirewallStatus();
}

document.getElementById("btn-sys-install")?.addEventListener("click", () => {
  _runSysProxyFlow(
    "/api/firewall/system/install",
    "Installing System Proxy",
    SYS_STEPS
  );
});

document.getElementById("btn-sys-uninstall")?.addEventListener("click", () => {
  if (!confirm("Remove the system proxy? AI traffic will go directly to provider APIs.")) return;
  _runSysProxyFlow(
    "/api/firewall/system/uninstall",
    "Removing System Proxy",
    [
      { id: "tls_stop",   label: "Stop TLS proxy",                   hint: "" },
      { id: "net_proxy",  label: "Remove network proxy settings",    hint: "" },
      { id: "ca_remove",  label: "Remove CA from login keychain",    hint: "" },
    ]
  );
});

document.getElementById("btn-sys-modal-close")?.addEventListener("click", () => {
  document.getElementById("fw-sys-modal").style.display = "none";
});

// ── Client connect ────────────────────────────────────────────────────────────

async function loadClientStatus() {
  try {
    const data = await (await fetch("/api/firewall/client/status")).json();
    _setClientBadge("claude", !!data.ANTHROPIC_BASE_URL);
    _setClientBadge("cursor", !!data.OPENAI_BASE_URL);
  } catch (_) {}
}

function _setClientBadge(id, connected) {
  const badge = document.getElementById(`fw-client-${id}-badge`);
  const btn = document.querySelector(`#fw-client-${id} .fw-client-connect-btn`);
  if (badge) {
    badge.textContent = connected ? "connected" : "disconnected";
    badge.className = `fw-client-badge ${connected ? "badge-connected" : "badge-disconnected"}`;
  }
  if (btn) {
    btn.textContent = connected ? "Disconnect" : "Connect";
    btn.dataset.action = connected ? "disconnect" : "connect";
    btn.className = `btn btn-sm ${connected ? "btn-ghost" : "btn-primary"} fw-client-connect-btn`;
  }
}

document.querySelectorAll(".fw-client-connect-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const client = btn.dataset.client;
    const action = btn.dataset.action;
    btn.disabled = true;
    try {
      const resp = await fetch(`/api/firewall/client/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(`Failed: ${err.detail}`);
      } else {
        await loadClientStatus();
        const clientId = client === "claude_code" ? "claude" : "cursor";
        const notice = document.getElementById(`fw-restart-${clientId}`);
        if (notice) notice.style.display = action === "connect" ? "block" : "none";
        // Show env var banner on connect (Claude only)
        const banner = document.getElementById(`fw-env-banner-${clientId}`);
        if (banner) banner.classList.toggle("visible", action === "connect");
      }
    } catch (e) {
      alert(`Error: ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  });
});

// ── Recordings ──────────────────────────────────────────────────────────────

let _recordings = [];  // cached so toggleRecording can inject on demand

async function loadRecordings() {
  const list = document.getElementById("fw-recs-list");
  if (!list) return;
  try {
    const data = await (await fetch("/api/firewall/recordings?limit=50")).json();
    _recordings = data.entries || data.recordings || [];
    const sizeEl = document.getElementById("fw-rec-size");
    if (sizeEl && data.size_kb != null) {
      sizeEl.textContent = `${data.size_kb.toFixed(1)} KB`;
    }
    if (!_recordings.length) {
      list.innerHTML = '<div class="fw-empty">No recordings yet. Enable recording and run a prompt.</div>';
      return;
    }
    // Render summary rows only — prompt text is injected lazily on expand
    // No inline onclick — event delegation handles clicks (avoids index-0 stale-closure bug)
    list.innerHTML = _recordings.map((r, i) => `
      <div class="fw-rec-row" data-rec-index="${i}">
        <div class="fw-rec-header">
          <span class="fw-rec-icon">▶</span>
          <span class="fw-rec-provider">${escapeHtml(r.provider || "")}</span>
          <span class="fw-rec-model">${escapeHtml(r.model || "")}</span>
          <span class="fw-rec-badge ${r.redacted ? 'badge-warn' : 'badge-ok'}">${r.redacted ? `✦ ${r.findings_count} finding${r.findings_count !== 1 ? 's' : ''}` : '✓ clean'}</span>
          <span class="fw-rec-chars">${r.char_count} chars</span>
          <span class="fw-rec-time">${new Date(r.timestamp).toLocaleString()}</span>
        </div>
        <div class="fw-rec-body" id="fw-rec-body-${i}" style="display:none"></div>
      </div>
    `).join("");
  } catch (e) {
    list.innerHTML = `<div class="fw-empty" style="color:var(--danger)">Error loading recordings: ${e.message}</div>`;
  }
}

function toggleRecording(index) {
  const body = document.getElementById(`fw-rec-body-${index}`);
  const row = document.querySelector(`.fw-rec-row[data-rec-index="${index}"]`);
  if (!body || !row) return;
  const open = body.style.display !== "none";
  if (open) {
    body.style.display = "none";
  } else {
    // Lazy inject prompt text on first expand
    if (!body.dataset.loaded) {
      const r = _recordings[index];
      if (r && r.prompt != null) {
        body.innerHTML = `<pre class="fw-rec-prompt">${escapeHtml(String(r.prompt))}</pre>`;
        body.dataset.loaded = "1";
      } else {
        body.innerHTML = `<div class="fw-empty">Prompt text unavailable.</div>`;
      }
    }
    body.style.display = "block";
  }
  const icon = row.querySelector(".fw-rec-icon");
  if (icon) icon.textContent = open ? "▶" : "▼";
  row.classList.toggle("fw-rec-expanded", !open);
}

// Event delegation on recordings list — avoids inline onclick stale-closure issues
document.getElementById("fw-recs-list")?.addEventListener("click", (e) => {
  // Don't collapse if user is selecting text inside an expanded prompt
  if (window.getSelection && window.getSelection().toString().length > 0) return;
  const header = e.target.closest(".fw-rec-header");
  if (!header) return;
  const row = header.closest(".fw-rec-row");
  if (!row) return;
  const idx = parseInt(row.dataset.recIndex, 10);
  if (!isNaN(idx)) toggleRecording(idx);
});

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function loadRecordingToggleState() {
  try {
    const cfg = await (await fetch("/api/firewall/config")).json();
    const chk = document.getElementById("fw-rec-toggle");
    if (chk) chk.checked = cfg.recording === true;
    const status = document.getElementById("fw-rec-status");
    if (status) status.textContent = cfg.recording ? "Recording is ON — prompts are being saved locally." : "Recording is OFF.";
  } catch (_) {}
}

document.getElementById("fw-rec-toggle")?.addEventListener("change", async (e) => {
  const enabled = e.target.checked;
  const status = document.getElementById("fw-rec-status");
  try {
    await fetch("/api/firewall/recording/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (status) status.textContent = enabled ? "Recording is ON — prompts are being saved locally." : "Recording is OFF.";
  } catch (err) {
    if (status) status.textContent = `Error: ${err.message}`;
    e.target.checked = !enabled; // revert
  }
});

document.getElementById("btn-fw-refresh-recs")?.addEventListener("click", loadRecordings);

document.getElementById("btn-fw-clear-recs")?.addEventListener("click", async () => {
  if (!confirm("Delete all recorded prompts? This cannot be undone.")) return;
  await fetch("/api/firewall/recordings", { method: "DELETE" });
  loadRecordings();
});

// System proxy status is loaded in the main nav-btn click handler above
