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
    if (sec === "relay") {
      loadControlPlane();
      _stopLogAutoRefresh();
    } else if (sec === "firewall") {
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
  let hash = location.hash.replace("#", "");
  if (hash === "control-plane") {
    history.replaceState(null, "", "#relay");
    hash = "relay";
  }
  // Top-level sections
  if (hash === "firewall" || hash === "mcp-hub" || hash === "relay") {
    activateSection(hash);
    if (hash === "relay") window.setTimeout(loadControlPlane, 0);
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
    if (requestId !== firewallLogRequest) return;
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
    await loadClientStatus();

    // Update endpoints with actual port
    ["fw-endpoint-anthropic", "fw-endpoint-openai", "fw-endpoint-google"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        const suffix = id === "fw-endpoint-openai" ? "/openai/v1" : id === "fw-endpoint-google" ? "/google" : "";
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

    document.getElementById("fw-redaction-text").value = data.redaction_text || "";

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
      redaction_text: document.getElementById("fw-redaction-text").value || null,
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
let firewallLogRequest = 0;
async function loadFirewallLogs() {
  const requestId = ++firewallLogRequest;
  const el = document.getElementById("fw-logs-list");
  try {
    const reveal = document.getElementById("fw-log-originals")?.checked === true;
    const filter = document.getElementById("fw-log-filter")?.value || "all";
    const data = await api("GET", `/api/firewall/logs?limit=100&show_originals=${reveal}&event_filter=${encodeURIComponent(filter)}`);
    if (!data.entries.length) {
      el.innerHTML = `<div class="no-items">No matching audit entries.</div>`;
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
              <span class="fw-finding-type">${escapeHtml(String(f.type || f.layer || ""))}</span>
              <span class="fw-finding-original">${escapeHtml(String(reveal ? (f.original ?? "Unavailable for this entry") : "Hidden"))}</span>
              <span class="fw-finding-arrow">→</span>
              <span class="fw-finding-replacement">${escapeHtml(String(f.replacement || f.reason || ""))}</span>
            </div>`).join("")}
        </div>` : "";
      return `
        <div class="fw-log-row ${hasFindings ? "fw-log-row-expandable" : ""}" data-idx="${i}">
          <span class="fw-log-ts">${ts}</span>
          <span class="fw-log-event ${eventCls}">${escapeHtml(String(e.event))}</span>
          ${safeBadge}
          <span class="fw-log-detail">${escapeHtml(String(e.detail))}</span>
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

document.getElementById("fw-log-filter")?.addEventListener("change", loadFirewallLogs);
document.getElementById("fw-log-originals")?.addEventListener("change", () => {
  document.querySelectorAll("#fw-logs-list .fw-finding-original").forEach(el => { el.textContent = "Hidden"; });
  loadFirewallLogs();
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
  { id: "tls_start",   label: "Start TLS proxy",                 hint: "" },
  { id: "net_proxy",   label: "Configure macOS network proxy",   hint: "" },
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
    const data = await (await fetch("/api/firewall/client/status", { cache: "no-store" })).json();
    _setClientBadge("claude", !!data.ANTHROPIC_BASE_URL);
    _setClientBadge("openai", !!data.OPENAI_BASE_URL);
    _setClientBadge("codex", /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(data.HTTPS_PROXY || ""));
  } catch (_) {}
}

function _setClientBadge(id, connected) {
  const badge = document.getElementById(`fw-client-${id}-badge`);
  const btn = document.querySelector(`#fw-client-${id} .fw-client-connect-btn`);
  if (badge) {
    badge.textContent = connected ? "configured · restart client" : "disconnected";
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
    let result = btn.closest(".fw-client-row").querySelector(".fw-client-result");
    if (!result) {
      result = document.createElement("span");
      result.className = "fw-client-result";
      result.setAttribute("role", "status");
      btn.closest(".fw-client-row").appendChild(result);
    }
    result.textContent = "Applying…";
    try {
      const resp = await fetch(`/api/firewall/client/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        result.textContent = `Failed: ${typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail)}`;
      } else {
        await loadClientStatus();
        result.textContent = action === "connect" ? "Configured. Fully quit and restart your client." : "Disconnected.";
        const clientId = client === "claude_code" ? "claude" : client === "openai_sdk" ? "openai" : client === "codex" ? "codex" : "cursor";
        const notice = document.getElementById(`fw-restart-${clientId}`);
        if (notice) notice.style.display = action === "connect" ? "block" : "none";
        // Show env var banner on connect (Claude only)
        const banner = document.getElementById(`fw-env-banner-${clientId}`);
        if (banner) banner.classList.toggle("visible", action === "connect");
      }
    } catch (e) {
      result.textContent = `Error: ${e.message}`;
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
          <span class="fw-rec-mode">${r.recording_content === "pre_sanitized" ? "original" : "sanitized"}</span>
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
    const content = document.getElementById("fw-rec-content");
    if (content) content.value = cfg.recording_content || "sanitized";
    const status = document.getElementById("fw-rec-status");
    if (status) status.textContent = cfg.recording ? `Recording is ON — ${cfg.recording_content === "pre_sanitized" ? "original prompts are stored locally" : "the sanitized prompt forwarded upstream is stored locally"}.` : "Recording is OFF.";
  } catch (_) {}
}

document.getElementById("fw-rec-toggle")?.addEventListener("change", async (e) => {
  const enabled = e.target.checked;
  const content = document.getElementById("fw-rec-content")?.value || "sanitized";
  const status = document.getElementById("fw-rec-status");
  try {
    await fetch("/api/firewall/recording/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled, recording_content: content }),
    });
    if (status) status.textContent = enabled ? `Recording is ON — ${content === "pre_sanitized" ? "original prompts are stored locally" : "the sanitized prompt forwarded upstream is stored locally"}.` : "Recording is OFF.";
  } catch (err) {
    if (status) status.textContent = `Error: ${err.message}`;
    e.target.checked = !enabled; // revert
  }
});

document.getElementById("fw-rec-content")?.addEventListener("change", async (e) => {
  const checkbox = document.getElementById("fw-rec-toggle");
  const enabled = checkbox?.checked === true;
  const content = e.target.value;
  const status = document.getElementById("fw-rec-status");
  try {
    await fetch("/api/firewall/recording/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled, recording_content: content }),
    });
    if (status) status.textContent = enabled ? `Recording is ON — ${content === "pre_sanitized" ? "original prompts are stored locally" : "the sanitized prompt forwarded upstream is stored locally"}.` : "Recording is OFF.";
  } catch (err) {
    if (status) status.textContent = `Error: ${err.message}`;
  }
});

document.getElementById("btn-fw-refresh-recs")?.addEventListener("click", loadRecordings);

document.getElementById("btn-fw-clear-recs")?.addEventListener("click", async () => {
  if (!confirm("Delete all recorded prompts? This cannot be undone.")) return;
  await fetch("/api/firewall/recordings", { method: "DELETE" });
  loadRecordings();
});

// System proxy status is loaded in the main nav-btn click handler above

// ── Relay project delivery system ────────────────────────────────────────────────
const controlPlane = { data: null, selectedId: null, filter: "all", editingWorkspaceId: null, editingBoardId: null, workspaceRules: [], perspective: "admin", boardId: null, view: "delivery" };
const CP_COLUMNS = [
  ["backlog", "Backlog"], ["todo", "Ready"], ["in_progress", "In progress"],
  ["blocked", "Blocked"], ["in_review", "Review"], ["done", "Done"],
];

function escapeControl(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
}

function controlError(error) {
  const el = document.getElementById("cp-error");
  if (!el) return;
  el.textContent = error.message || String(error);
  el.style.display = "block";
}
function controlNotice(message) {
  const el = document.getElementById("cp-notice");
  if (!el) return;
  el.textContent = message;
  el.style.display = "block";
}

async function loadControlPlane() {
  try {
    const query = controlPlane.boardId ? `?board_id=${encodeURIComponent(controlPlane.boardId)}` : "";
    const data = await api("GET", `/api/control/board${query}`);
    controlPlane.data = data;
    controlPlane.boardId = data.active_board?.id || controlPlane.boardId;
    if (!data.tasks.some((task) => task.id === controlPlane.selectedId)) controlPlane.selectedId = null;
    document.getElementById("cp-error").style.display = "none";
    renderControlPlane();
  } catch (error) { controlError(error); }
}

function taskAgent(task) {
  return String(task.claimed_by || task.assignee || "").toLowerCase();
}

function filteredControlTasks() {
  const tasks = controlPlane.data?.tasks || [];
  if (controlPlane.filter === "ready") return tasks.filter((task) => task.ready);
  if (controlPlane.filter === "blocked") return tasks.filter((task) => task.status === "blocked" || task.blockers?.length);
  if (controlPlane.filter === "mine") return tasks.filter((task) => !taskAgent(task) || taskAgent(task).includes("local") || taskAgent(task).includes("me"));
  if (controlPlane.filter === "codex" || controlPlane.filter === "claude") return tasks.filter((task) => taskAgent(task).includes(controlPlane.filter));
  return tasks;
}

function renderAgentConsole() {
  const panel = document.getElementById("cp-agent-console");
  const tasks = controlPlane.data?.tasks || [];
  const clients = controlPlane.data?.agent_clients || {};
  const triage = tasks.filter((task) => ["backlog", "todo"].includes(task.status) && !task.claimed_by);
  const planningSessions = controlPlane.data?.summary?.recent_planning_sessions || [];
  const latestPlan = planningSessions.at(-1);
  const agentCard = (client) => {
    const assigned = tasks.filter((task) => taskAgent(task).includes(client));
    const active = assigned.filter((task) => !["done", "cancelled"].includes(task.status));
    const available = clients[client]?.available;
    return `<article class="cp-agent-card"><div class="cp-agent-card-top"><span class="cp-agent-avatar cp-agent-${client}">${client === "codex" ? "⌘" : "C"}</span><div><strong>${client === "codex" ? "Codex" : "Claude"}</strong><small>${available ? "CLI ready" : "CLI unavailable"}</small></div><span class="cp-agent-count">${active.length}</span></div><p>${active.length ? `${active.length} active ticket${active.length === 1 ? "" : "s"} assigned` : "No active tickets assigned"}</p><button class="btn btn-ghost" data-cp-launch-triage="${client}" ${available && triage.length ? "" : "disabled"}>Launch triage</button></article>`;
  };
  const planningRecord = latestPlan ? `<div class="cp-planning-record"><span>✦</span><div><small>Latest planning session · ${escapeControl(latestPlan.agent_client || "agent")}</small><strong>${escapeControl(latestPlan.brief?.split("\n")[0]?.replace(/^Goal:\s*/, "") || "Planning brief recorded")}</strong></div><code>${escapeControl(latestPlan.id)}</code></div>` : "";
  panel.innerHTML = `<div class="cp-agent-console-head"><div><p class="cp-eyebrow">RELAY TRIAGE</p><h3>Plan work before you fan it out</h3><p>Give an AI planner the outcome, constraints, and quality bar. It proposes an Epic and testable tickets in Terminal, then waits for your approval before it writes to this board.</p></div><div class="cp-triage-summary"><strong>✦</strong><span>new initiative</span><button class="btn btn-primary" data-cp-open-planner="true">Plan with AI</button></div></div><div class="cp-agent-grid">${agentCard("codex")}${agentCard("claude")}</div>${planningRecord}`;
  panel.style.display = controlPlane.perspective === "agent" ? "block" : "none";
}

function renderControlTicketParents() {
  const select = document.getElementById("cp-ticket-parent");
  if (!select) return;
  const epics = (controlPlane.data?.tasks || []).filter((task) => task.type === "epic");
  select.innerHTML = '<option value="">No epic</option>' + epics.map((epic) => `<option value="${escapeControl(epic.id)}">${escapeControl(epic.title)}</option>`).join("");
}

function updateControlTicketType() {
  const type = document.getElementById("cp-ticket-type")?.value;
  const parentField = document.getElementById("cp-ticket-parent-field");
  const submit = document.getElementById("cp-ticket-submit");
  const heading = document.getElementById("cp-ticket-modal-heading");
  const isEpic = type === "epic";
  if (parentField) parentField.style.display = isEpic ? "none" : "grid";
  if (isEpic) document.getElementById("cp-ticket-parent").value = "";
  if (submit) submit.textContent = isEpic ? "Create epic" : "Create ticket";
  if (heading) heading.textContent = isEpic ? "Create epic" : "Add work";
}

function renderControlEpics(tasks) {
  const epics = tasks.filter((task) => task.type === "epic");
  if (!epics.length) {
    return `<section class="cp-epic-empty"><span class="cp-eyebrow">EPIC PORTFOLIO</span><h3>Shape a meaningful outcome before splitting the work.</h3><p>Create an Epic to group related tickets, see delivery progress, and keep the intent next to the execution.</p><button class="btn btn-primary" data-cp-create-epic="true">Create first Epic</button></section>`;
  }
  return `<section class="cp-epic-grid">${epics.map((epic) => {
    const children = tasks.filter((task) => task.parent_id === epic.id);
    const done = children.filter((task) => task.status === "done").length;
    const active = children.filter((task) => ["in_progress", "in_review"].includes(task.status)).length;
    const blocked = children.filter((task) => task.status === "blocked" || task.blockers?.length).length;
    const progress = children.length ? Math.round((done / children.length) * 100) : (epic.status === "done" ? 100 : 0);
    const preview = children.slice(0, 3).map((task) => `<li><span class="cp-epic-task-state cp-state-${escapeControl(task.status)}"></span>${escapeControl(task.title)}</li>`).join("") || "<li class=\"cp-epic-no-tasks\">No tickets connected yet</li>";
    return `<button type="button" class="cp-epic-card${epic.id === controlPlane.selectedId ? " selected" : ""}" data-cp-ticket="${escapeControl(epic.id)}"><div class="cp-epic-card-head"><span class="cp-epic-label">EPIC</span><span class="cp-priority cp-priority-${escapeControl(epic.priority)}">${escapeControl(epic.priority)}</span></div><div class="cp-epic-card-title"><div><h3>${escapeControl(epic.title)}</h3><p>${escapeControl(epic.description || "A delivery outcome with no description yet.")}</p></div><div class="cp-epic-progress" style="--cp-progress:${progress}%"><span>${progress}<small>%</small></span></div></div><div class="cp-epic-metrics"><span><b>${children.length}</b> tickets</span><span><b>${active}</b> active</span><span class="${blocked ? "is-blocked" : ""}"><b>${blocked}</b> blocked</span></div><ul class="cp-epic-preview">${preview}</ul><div class="cp-epic-footer"><span>${done} of ${children.length} complete</span><span>Open Epic <b>→</b></span></div></button>`;
  }).join("")}</section>`;
}

function renderControlPlane() {
  const data = controlPlane.data;
  if (!data) return;
  const summary = data.summary;
  const isAgentView = controlPlane.perspective === "agent";
  document.getElementById("cp-board-path").textContent = data.path;
  document.getElementById("cp-perspective-label").textContent = isAgentView ? "Agent" : "Admin";
  document.getElementById("cp-perspective-note").textContent = isAgentView ? "Operate a focused queue, capture evidence, and hand off work cleanly." : "Configure workspaces, direct capacity, and manage delivery.";
  document.querySelectorAll(".cp-perspective-button").forEach((button) => button.classList.toggle("active", button.dataset.cpPerspective === controlPlane.perspective));
  document.querySelectorAll(".cp-view-button").forEach((button) => {
    const active = button.dataset.cpView === controlPlane.view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelector(".cp-project-bar").style.display = isAgentView ? "none" : "flex";
  document.getElementById("cp-create").style.display = isAgentView ? "none" : "inline-flex";
  renderAgentConsole();

  const boards = data.boards || [];
  const boardSelect = document.getElementById("cp-board-select");
  boardSelect.innerHTML = boards.map((item) => `<option value="${escapeControl(item.id)}">${escapeControl(item.name)}</option>`).join("");
  boardSelect.value = controlPlane.boardId || "";
  document.querySelector(".cp-board-select-label").textContent = data.active_board?.description || "Delivery board";
  renderControlTicketParents();

  const workspaces = data.workspaces || [];
  const workspaceLabel = workspaces.length ? `${workspaces.length} workspace${workspaces.length === 1 ? "" : "s"} ready` : "No workspaces configured";
  document.getElementById("cp-project-name").textContent = workspaceLabel;
  document.getElementById("cp-project-summary").textContent = workspaces.length ? workspaces.map((item) => item.name).join(" · ") : "Add a workspace before assigning work to agents.";
  document.getElementById("cp-ticket-workspace").innerHTML = '<option value="">Choose workspace</option>' + workspaces.map((item) => `<option value="${escapeControl(item.id)}">${escapeControl(item.name)} · ${escapeControl(item.source)}</option>`).join("");
  document.getElementById("cp-planner-workspace").innerHTML = '<option value="">Plan before choosing a workspace</option>' + workspaces.map((item) => `<option value="${escapeControl(item.id)}">${escapeControl(item.name)} · ${escapeControl(item.source)}</option>`).join("");
  document.getElementById("cp-workspace-list").innerHTML = workspaces.map((item) => {
    const sourceLabel = item.local_directory ? "Local checkout" : "Remote clone";
    const location = item.local_directory || item.repository_url || "No repository location saved";
    const ruleCount = splitControlWorkspaceRules(item.branch_rules).length;
    return `<article class="cp-workspace-row"><div class="cp-workspace-row-icon">${item.local_directory ? "⌘" : "↗"}</div><div class="cp-workspace-row-copy"><b>${escapeControl(item.name)}</b><small>${escapeControl(sourceLabel)} · ${escapeControl(location)}</small><em>${ruleCount} delivery rule${ruleCount === 1 ? "" : "s"}</em></div><button class="cp-workspace-settings" type="button" data-cp-edit-workspace="${escapeControl(item.id)}" aria-label="Configure ${escapeControl(item.name)}" title="Workspace settings">⚙</button></article>`;
  }).join("") || '<div class="cp-workspace-empty"><span>⌘</span><strong>No workspaces yet</strong><p>Add a local checkout or a remote repository for agents to use.</p></div>';
  document.getElementById("cp-metrics").innerHTML = [
    [summary.total, "work items"], [summary.active, "active"], [summary.ready.length, "ready"],
    [summary.blocked.length, "blocked"], [`${summary.completion_percent}%`, "complete"], [summary.claimed, "claimed"],
  ].map(([value, label]) => `<div class="cp-metric"><strong>${escapeControl(value)}</strong><span>${label}</span></div>`).join("");
  const tasks = filteredControlTasks();
  if (controlPlane.view === "epics") {
    document.getElementById("cp-board").classList.add("cp-board-epics");
    document.getElementById("cp-board").innerHTML = renderControlEpics(tasks);
  } else {
    document.getElementById("cp-board").classList.remove("cp-board-epics");
    const deliveryTasks = tasks.filter((task) => task.type !== "epic");
    document.getElementById("cp-board").innerHTML = CP_COLUMNS.map(([status, title]) => {
      const cards = deliveryTasks.filter((task) => task.status === status).map(renderControlCard).join("") || '<p class="cp-column-empty">No tickets</p>';
      return `<section class="cp-column cp-${status}" data-cp-drop-status="${status}"><h3>${title}<span>${deliveryTasks.filter((task) => task.status === status).length}</span></h3>${cards}</section>`;
    }).join("");
  }
  renderControlDetail();
}

function renderControlCard(task) {
  const selected = task.id === controlPlane.selectedId ? " selected" : "";
  const priority = `<span class="cp-priority cp-priority-${escapeControl(task.priority)}">${escapeControl(task.priority)}</span>`;
  const signal = task.blockers?.length ? " ⛔" : task.ready ? " ✓" : "";
  return `<button class="cp-ticket${selected}" draggable="true" data-cp-ticket="${escapeControl(task.id)}"><span class="cp-ticket-top">${priority}<code>${escapeControl(task.id)}</code></span><strong>${escapeControl(task.title)}</strong><span class="cp-ticket-meta">${escapeControl(task.type)} · ${escapeControl(task.claimed_by || task.assignee || "unassigned")}${signal}</span></button>`;
}

function controlDetailStatus(status) {
  return String(status || "todo").replaceAll("_", " ");
}

function renderControlDetail() {
  const el = document.getElementById("cp-detail");
  const task = controlPlane.data?.tasks.find((item) => item.id === controlPlane.selectedId);
  if (!task) {
    el.className = "cp-detail cp-detail-empty";
    el.innerHTML = '<p class="cp-empty">Select a ticket to inspect its brief, delivery evidence, decisions, and activity.</p>';
    return;
  }
  el.className = "cp-detail cp-ticket-dialog";
  const tasks = controlPlane.data?.tasks || [];
  const workspace = controlPlane.data?.workspaces?.find((item) => item.id === task.workspace_id);
  const parentEpic = task.parent_id ? tasks.find((item) => item.id === task.parent_id) : null;
  const children = task.type === "epic" ? tasks.filter((item) => item.parent_id === task.id) : [];
  const completeChildren = children.filter((item) => item.status === "done").length;
  const activity = [
    ...(task.comments || []).map((item) => ({ kind: "update", at: item.at, title: "Progress update", body: item.body })),
    ...(task.validations || []).map((item) => ({ kind: item.status || "validation", at: item.at, title: `${item.kind || "Validation"} · ${item.status || "recorded"}`, body: item.summary, output: item.output })),
    ...(task.git_evidence || []).map((item) => ({ kind: "evidence", at: item.at || item.recorded_at, title: `Git snapshot · ${item.branch || "detached"}`, body: item.commit_subject || item.commit || "Repository evidence attached" })),
    ...(task.handoffs || []).map((item) => ({ kind: "handoff", at: item.at, title: `Handed to ${item.to || "agent"}`, body: item.note })),
  ].filter((item) => item.at).sort((a, b) => String(b.at).localeCompare(String(a.at)));
  const activityMarkup = activity.length ? activity.map((item) => `<article class="cp-activity-item cp-activity-${escapeControl(item.kind)}"><span class="cp-activity-dot"></span><div><div class="cp-activity-title"><strong>${escapeControl(item.title)}</strong><time>${escapeControl(item.at)}</time></div><p>${escapeControl(item.body || "No summary recorded.")}</p>${item.output ? `<pre>${escapeControl(item.output)}</pre>` : ""}</div></article>`).join("") : '<div class="cp-activity-empty"><strong>No activity yet</strong><p>Capture the first decision, validation result, or agent handoff here.</p></div>';
  const criteria = (task.acceptance_criteria || []).length ? task.acceptance_criteria.map((item) => `<li><span class="cp-check"></span>${escapeControl(item)}</li>`).join("") : '<li class="cp-muted-row">No acceptance criteria recorded.</li>';
  const childMarkup = task.type === "epic" ? `<section class="cp-epic-delivery"><div class="cp-section-title"><div><span class="cp-section-kicker">EPIC DELIVERY</span><h4>${completeChildren}/${children.length} child tickets complete</h4></div><button class="cp-text-button" data-cp-action="edit">Edit Epic</button></div><div class="cp-epic-child-list">${children.length ? children.map((item) => `<button type="button" data-cp-ticket="${escapeControl(item.id)}"><span class="cp-state-dot cp-state-${escapeControl(item.status)}"></span><span>${escapeControl(item.title)}</span><small>${escapeControl(controlDetailStatus(item.status))}</small></button>`).join("") : '<p class="cp-muted-row">No child tickets yet. Create work and assign it to this Epic.</p>'}</div></section>` : "";
  const owner = task.claimed_by || task.assignee || "Unassigned";
  el.innerHTML = `<div class="cp-workdrawer-head"><div class="cp-workdrawer-ident"><code>${escapeControl(task.id)}</code><span class="cp-status-pill cp-status-${escapeControl(task.status)}">${escapeControl(controlDetailStatus(task.status))}</span></div><button class="cp-close" id="cp-close-detail" aria-label="Close ticket">×</button></div>
    <div class="cp-workdrawer-title"><div><h3>${escapeControl(task.title)}</h3><p>${escapeControl(task.description || "Add context so an agent or reviewer can pick this up without a separate briefing.")}</p></div><button class="btn btn-ghost cp-edit-ticket" data-cp-action="edit">Edit details</button></div>
    <div class="cp-workdrawer-actions"><button class="btn btn-primary" data-cp-action="start_ticket">Start work</button><button class="btn btn-ghost" data-cp-action="review_ticket">Request review</button><button class="btn btn-ghost" data-cp-action="complete_ticket">Mark complete</button><span></span><button class="cp-quick-action" data-cp-action="comment">+ Update</button><button class="cp-quick-action" data-cp-action="record_validation">+ Evidence</button><button class="cp-quick-action" data-cp-action="attach_git_evidence">+ Git</button><button class="cp-quick-action" data-cp-action="handoff_ticket">Handoff</button></div>
    <div class="cp-workdrawer-grid"><main class="cp-workdrawer-main"><section class="cp-detail-card cp-criteria-card"><div class="cp-section-title"><div><span class="cp-section-kicker">DEFINITION OF DONE</span><h4>Acceptance criteria</h4></div><button class="cp-text-button" data-cp-action="edit">Edit</button></div><ul class="cp-criteria-list">${criteria}</ul></section>${childMarkup}<section class="cp-detail-card cp-activity-card"><div class="cp-section-title"><div><span class="cp-section-kicker">PROJECT RECORD</span><h4>Activity &amp; evidence</h4></div><button class="cp-text-button" data-cp-action="comment">Add update</button></div><div class="cp-activity-feed">${activityMarkup}</div></section></main>
    <aside class="cp-workdrawer-sidebar"><section class="cp-detail-card cp-details-card"><div class="cp-section-title"><div><span class="cp-section-kicker">AT A GLANCE</span><h4>Details</h4></div><button class="cp-icon-text" data-cp-action="edit" aria-label="Edit details">Edit</button></div><dl class="cp-detail-list"><div><dt>Owner</dt><dd>${escapeControl(owner)}</dd></div><div><dt>Priority</dt><dd><span class="cp-detail-priority cp-priority-${escapeControl(task.priority)}">${escapeControl(task.priority)}</span></dd></div><div><dt>Risk</dt><dd>${escapeControl(task.risk_level || "medium")}</dd></div><div><dt>Complexity</dt><dd>${escapeControl(task.complexity || "medium")}</dd></div><div><dt>Type</dt><dd>${escapeControl(task.type)}</dd></div><div><dt>Workspace</dt><dd>${escapeControl(workspace?.name || "Not assigned")}</dd></div>${parentEpic ? `<div><dt>Epic</dt><dd><button type="button" data-cp-ticket="${escapeControl(parentEpic.id)}">${escapeControl(parentEpic.title)}</button></dd></div>` : ""}</dl></section>
    <section class="cp-detail-card cp-proof-card"><div class="cp-section-title"><div><span class="cp-section-kicker">ADD TO THE RECORD</span><h4>Proof of work</h4></div></div><button class="cp-proof-action" data-cp-action="record_validation"><span>✓</span><div><strong>Validation</strong><small>Test, lint, review, or build result</small></div><b>+</b></button><button class="cp-proof-action" data-cp-action="attach_git_evidence"><span>⌘</span><div><strong>Git snapshot</strong><small>Branch, commit, and changed files</small></div><b>+</b></button><button class="cp-proof-action" data-cp-action="handoff_ticket"><span>↗</span><div><strong>Agent handoff</strong><small>Launch Codex or Claude with context</small></div><b>+</b></button></section></aside></div>`;
}

async function controlWrite(action, payload = {}) {
  try {
    const result = await api("POST", "/api/control/board", { action, board_id: controlPlane.boardId, payload: { ...payload, confirm_write: true } });
    await loadControlPlane();
    return result;
  } catch (error) { controlError(error); return null; }
}

function selectedControlTask() { return controlPlane.data?.tasks.find((task) => task.id === controlPlane.selectedId); }

const controlDrag = { taskId: null, sourceStatus: null, didMove: false };

function openControlTransitionModal(task, status) {
  if (task.status === status) return;
  controlDrag.taskId = task.id;
  controlDrag.sourceStatus = task.status;
  document.getElementById("cp-transition-ticket").textContent = `${task.id} · ${task.title}`;
  document.getElementById("cp-transition-from").textContent = task.status.replaceAll("_", " ");
  document.getElementById("cp-transition-to").textContent = status.replaceAll("_", " ");
  document.getElementById("cp-transition-comment").value = "";
  const defaultMode = document.querySelector('input[name="cp-transition-next"][value="move"]');
  if (defaultMode) defaultMode.checked = true;
  document.querySelectorAll(".cp-transition-option").forEach((option) => option.classList.toggle("active", option.querySelector("input")?.value === "move"));
  document.getElementById("cp-transition-submit-label").textContent = "Move ticket";
  document.getElementById("cp-transition-modal").style.display = "flex";
  document.getElementById("cp-transition-comment").focus();
}

function closeControlTransitionModal() {
  document.getElementById("cp-transition-modal").style.display = "none";
  controlDrag.taskId = null;
  controlDrag.sourceStatus = null;
}

function closeControlTicketEditor() { document.getElementById("cp-ticket-edit-modal").style.display = "none"; }
function closeControlValidationModal() { document.getElementById("cp-validation-modal").style.display = "none"; }
function closeControlEvidenceModal() { document.getElementById("cp-evidence-modal").style.display = "none"; }

function openControlTicketEditor(task) {
  const workspaces = controlPlane.data?.workspaces || [];
  document.getElementById("cp-ticket-edit-context").textContent = `${task.id} · Changes are saved to the selected Relay board.`;
  document.getElementById("cp-ticket-edit-title").value = task.title || "";
  document.getElementById("cp-ticket-edit-description").value = task.description || "";
  document.getElementById("cp-ticket-edit-type").value = task.type || "task";
  document.getElementById("cp-ticket-edit-priority").value = task.priority || "medium";
  document.getElementById("cp-ticket-edit-risk").value = task.risk_level || "medium";
  document.getElementById("cp-ticket-edit-complexity").value = task.complexity || "medium";
  document.getElementById("cp-ticket-edit-assignee").value = task.assignee || task.claimed_by || "";
  document.getElementById("cp-ticket-edit-workspace").innerHTML = '<option value="">No workspace</option>' + workspaces.map((item) => `<option value="${escapeControl(item.id)}">${escapeControl(item.name)} · ${escapeControl(item.source)}</option>`).join("");
  document.getElementById("cp-ticket-edit-workspace").value = task.workspace_id || "";
  document.getElementById("cp-ticket-edit-criteria").value = (task.acceptance_criteria || []).join("\n");
  document.getElementById("cp-ticket-edit-modal").style.display = "flex";
  window.setTimeout(() => document.getElementById("cp-ticket-edit-title").focus(), 0);
}

function openControlValidationModal(task) {
  document.getElementById("cp-validation-ticket").textContent = `${task.id} · ${task.title}`;
  document.getElementById("cp-validation-form").reset();
  document.getElementById("cp-validation-modal").style.display = "flex";
  window.setTimeout(() => document.getElementById("cp-validation-summary").focus(), 0);
}

function openControlEvidenceModal(task) {
  const workspace = controlPlane.data?.workspaces?.find((item) => item.id === task.workspace_id);
  document.getElementById("cp-evidence-ticket").textContent = `${task.id} · ${task.title}`;
  document.getElementById("cp-evidence-form").reset();
  document.getElementById("cp-evidence-repo-path").value = workspace?.local_directory || "";
  document.getElementById("cp-evidence-modal").style.display = "flex";
  window.setTimeout(() => document.getElementById("cp-evidence-repo-path").focus(), 0);
}

async function handleControlAction(action) {
  const task = selectedControlTask();
  if (!task) return;
  if (action === "edit") { openControlTicketEditor(task); return; }
  if (action === "review_ticket") {
    try {
      const result = await api("POST", "/api/control/board", { action, board_id: controlPlane.boardId, payload: { id: task.id, confirm_write: true } });
      await loadControlPlane();
      controlNotice(result.review.ready_for_review ? "Review readiness recorded. This ticket is ready for review." : `Review needs: ${result.review.missing.join(", ")}.`);
    } catch (error) { controlError(error); }
    return;
  }
  if (action === "start_ticket") {
    const agent = task.claimed_by || task.assignee || "local-agent";
    const started = await controlWrite("start_ticket", { id: task.id, agent });
    if (started) controlNotice(`Work started with ${agent}.`);
    return;
  }
  if (action === "complete_ticket") {
    const completed = await controlWrite("complete_ticket", { id: task.id });
    if (completed) controlNotice("Ticket marked complete.");
    return;
  }
  if (action === "comment") {
    document.getElementById("cp-comment-ticket").textContent = `${task.id} · ${task.title}`;
    document.getElementById("cp-comment-body").value = "";
    document.getElementById("cp-comment-modal").style.display = "flex";
    document.getElementById("cp-comment-body").focus();
    return;
  }
  if (action === "handoff_ticket") {
    document.getElementById("cp-handoff-ticket").textContent = `${task.id} · ${task.title}`;
    document.getElementById("cp-handoff-recipient").value = task.claimed_by || task.assignee || "codex-agent";
    document.getElementById("cp-handoff-note").value = "";
    document.getElementById("cp-handoff-modal").style.display = "flex";
    return;
  }
  if (action === "record_validation") { openControlValidationModal(task); return; }
  if (action === "attach_git_evidence") { openControlEvidenceModal(task); }
}

function closeControlCommentModal() { document.getElementById("cp-comment-modal").style.display = "none"; }
document.getElementById("cp-comment-close")?.addEventListener("click", closeControlCommentModal);
document.getElementById("cp-comment-cancel")?.addEventListener("click", closeControlCommentModal);
document.getElementById("cp-comment-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = selectedControlTask();
  const comment = document.getElementById("cp-comment-body").value.trim();
  if (!task || !comment) return;
  const saved = await controlWrite("comment", { id: task.id, comment });
  if (saved) closeControlCommentModal();
});

document.getElementById("cp-ticket-edit-close")?.addEventListener("click", closeControlTicketEditor);
document.getElementById("cp-ticket-edit-cancel")?.addEventListener("click", closeControlTicketEditor);
document.getElementById("cp-ticket-edit-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = selectedControlTask();
  if (!task) return;
  const changes = {
    title: document.getElementById("cp-ticket-edit-title").value.trim(),
    description: document.getElementById("cp-ticket-edit-description").value.trim(),
    type: document.getElementById("cp-ticket-edit-type").value,
    priority: document.getElementById("cp-ticket-edit-priority").value,
    risk_level: document.getElementById("cp-ticket-edit-risk").value,
    complexity: document.getElementById("cp-ticket-edit-complexity").value,
    assignee: document.getElementById("cp-ticket-edit-assignee").value.trim() || null,
    workspace_id: document.getElementById("cp-ticket-edit-workspace").value || null,
    acceptance_criteria: document.getElementById("cp-ticket-edit-criteria").value.split("\n").map((item) => item.trim()).filter(Boolean),
  };
  const saved = await controlWrite("update", { id: task.id, changes });
  if (saved) { closeControlTicketEditor(); controlNotice("Ticket details updated."); }
});
document.getElementById("cp-validation-close")?.addEventListener("click", closeControlValidationModal);
document.getElementById("cp-validation-cancel")?.addEventListener("click", closeControlValidationModal);
document.getElementById("cp-validation-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = selectedControlTask();
  if (!task) return;
  const saved = await controlWrite("record_validation", {
    id: task.id,
    validation_kind: document.getElementById("cp-validation-kind").value,
    validation_status: document.getElementById("cp-validation-status").value,
    validation_summary: document.getElementById("cp-validation-summary").value.trim(),
    validation_output: document.getElementById("cp-validation-output").value.trim(),
  });
  if (saved) { closeControlValidationModal(); controlNotice("Validation evidence saved to the project record."); }
});
document.getElementById("cp-evidence-close")?.addEventListener("click", closeControlEvidenceModal);
document.getElementById("cp-evidence-cancel")?.addEventListener("click", closeControlEvidenceModal);
document.getElementById("cp-evidence-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = selectedControlTask();
  const repoPath = document.getElementById("cp-evidence-repo-path").value.trim();
  if (!task || !repoPath) return;
  const saved = await controlWrite("attach_git_evidence", { id: task.id, repo_path: repoPath, base_ref: document.getElementById("cp-evidence-base-ref").value.trim() || null });
  if (saved) { closeControlEvidenceModal(); controlNotice("Git snapshot attached to the ticket."); }
});

document.getElementById("cp-transition-close")?.addEventListener("click", closeControlTransitionModal);
document.getElementById("cp-transition-cancel")?.addEventListener("click", closeControlTransitionModal);
document.querySelectorAll('input[name="cp-transition-next"]').forEach((input) => input.addEventListener("change", () => {
  document.querySelectorAll(".cp-transition-option").forEach((option) => option.classList.toggle("active", option.querySelector("input")?.checked));
  const submitLabel = document.getElementById("cp-transition-submit-label");
  if (submitLabel) submitLabel.textContent = input.value === "handoff" ? "Move & hand off" : "Move ticket";
}));
document.getElementById("cp-transition-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = controlPlane.data?.tasks.find((item) => item.id === controlDrag.taskId);
  const status = document.getElementById("cp-transition-to").textContent.replaceAll(" ", "_");
  const comment = document.getElementById("cp-transition-comment").value.trim();
  const nextStep = document.querySelector('input[name="cp-transition-next"]:checked')?.value || "move";
  if (!task || !status) return;
  const moved = await controlWrite("transition", { id: task.id, status, reason: comment });
  if (!moved) return;
  if (comment) await controlWrite("comment", { id: task.id, comment });
  closeControlTransitionModal();
  controlNotice(`Moved ${task.id} to ${status.replaceAll("_", " ")}.`);
  if (nextStep === "handoff") {
    controlPlane.selectedId = task.id;
    await handleControlAction("handoff_ticket");
  }
});

document.getElementById("cp-refresh")?.addEventListener("click", loadControlPlane);
function closeControlTicketModal() {
  document.getElementById("cp-ticket-modal").style.display = "none";
}


const CONTROL_WORKSPACE_RULE_PRESETS = [
  "Use feature/<ticket-id>-<short-slug> branch names",
  "Run lint before every commit",
  "Run relevant tests before review",
  "Run type checks before review",
  "Run a security scan before merge",
  "Open a pull request with validation evidence",
];

function splitControlWorkspaceRules(value) {
  return String(value || "").split(/[\n;]/).map((item) => item.trim()).filter(Boolean);
}

function renderControlWorkspaceRules() {
  const rules = controlPlane.workspaceRules || [];
  const list = document.getElementById("cp-rule-list");
  if (!list) return;
  list.innerHTML = rules.length
    ? rules.map((rule, index) => `<span class="cp-rule-chip">${escapeControl(rule)}<button type="button" data-cp-rule-remove="${index}" aria-label="Remove rule">×</button></span>`).join("")
    : '<p class="cp-rule-empty">No rules selected. Add a template or write one below.</p>';
  document.querySelectorAll("[data-cp-rule-preset]").forEach((button) => {
    const selected = rules.includes(button.dataset.cpRulePreset);
    button.classList.toggle("selected", selected);
    button.querySelector("span").textContent = selected ? "✓" : "+";
  });
  document.getElementById("cp-project-rules").value = rules.join("; ");
}

function addControlWorkspaceRule(rule) {
  const normalised = String(rule || "").trim();
  if (!normalised || controlPlane.workspaceRules.includes(normalised)) return;
  controlPlane.workspaceRules.push(normalised);
  renderControlWorkspaceRules();
}

function resetControlWorkspaceForm() {
  controlPlane.editingWorkspaceId = null;
  controlPlane.workspaceRules = [];
  document.getElementById("cp-workspace-name").value = "";
  document.getElementById("cp-project-source").value = "local";
  document.getElementById("cp-local-directory").value = "";
  document.getElementById("cp-remote-repository").value = "";
  document.getElementById("cp-custom-rule").value = "";
  document.getElementById("cp-workspace-form-heading").textContent = "New workspace";
  document.getElementById("cp-save-project").textContent = "Add workspace";
  document.getElementById("cp-delete-current-workspace").style.display = "none";
  renderControlWorkspaceRules();
  updateControlProjectWarning();
}

function openControlWorkspaceEditor() {
  document.getElementById("cp-workspace-editor-modal").style.display = "flex";
  window.setTimeout(() => document.getElementById("cp-workspace-name").focus(), 0);
}

function closeControlWorkspaceEditor() {
  document.getElementById("cp-workspace-editor-modal").style.display = "none";
  resetControlWorkspaceForm();
}

function editControlWorkspace(workspaceId) {
  const workspace = controlPlane.data?.workspaces?.find((item) => item.id === workspaceId);
  if (!workspace) return;
  controlPlane.editingWorkspaceId = workspace.id;
  controlPlane.workspaceRules = splitControlWorkspaceRules(workspace.branch_rules);
  document.getElementById("cp-workspace-name").value = workspace.name || "";
  document.getElementById("cp-project-source").value = workspace.source || "local";
  document.getElementById("cp-local-directory").value = workspace.local_directory || "";
  document.getElementById("cp-remote-repository").value = workspace.repository_url || "";
  document.getElementById("cp-custom-rule").value = "";
  document.getElementById("cp-workspace-form-heading").textContent = `Workspace settings · ${workspace.name}`;
  document.getElementById("cp-save-project").textContent = "Save changes";
  document.getElementById("cp-delete-current-workspace").style.display = "inline-flex";
  renderControlWorkspaceRules();
  updateControlProjectWarning();
  openControlWorkspaceEditor();
}

function updateControlProjectWarning() {
  const source = document.getElementById("cp-project-source")?.value;
  const localDirectory = document.getElementById("cp-local-directory")?.value.trim();
  const warning = document.getElementById("cp-project-warning");
  if (!warning) return;
  warning.style.display = source === "remote" || !localDirectory ? "block" : "none";
}
function closeControlHandoffModal() { document.getElementById("cp-handoff-modal").style.display = "none"; }
function closeControlPlannerModal() { document.getElementById("cp-planner-modal").style.display = "none"; }
function openControlPlannerModal() {
  const form = document.getElementById("cp-planner-form");
  form.reset();
  document.querySelectorAll(".cp-planner-choice").forEach((item) => item.classList.toggle("selected", item.querySelector("input").checked));
  document.getElementById("cp-planner-modal").style.display = "flex";
  document.getElementById("cp-planner-goal").focus();
}
function closeControlProjectModal() { document.getElementById("cp-project-modal").style.display = "none"; }
document.getElementById("cp-open-project")?.addEventListener("click", () => { document.getElementById("cp-project-modal").style.display = "flex"; });
document.getElementById("cp-project-cancel")?.addEventListener("click", closeControlProjectModal);
document.getElementById("cp-project-cancel-secondary")?.addEventListener("click", closeControlProjectModal);
document.getElementById("cp-new-workspace")?.addEventListener("click", () => { resetControlWorkspaceForm(); openControlWorkspaceEditor(); });
document.getElementById("cp-workspace-editor-close")?.addEventListener("click", closeControlWorkspaceEditor);
document.getElementById("cp-workspace-editor-cancel")?.addEventListener("click", closeControlWorkspaceEditor);
document.getElementById("cp-project-source")?.addEventListener("change", updateControlProjectWarning);
document.getElementById("cp-local-directory")?.addEventListener("input", updateControlProjectWarning);
document.getElementById("cp-add-custom-rule")?.addEventListener("click", () => {
  const input = document.getElementById("cp-custom-rule");
  addControlWorkspaceRule(input.value);
  input.value = "";
  input.focus();
});
document.getElementById("cp-custom-rule")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  document.getElementById("cp-add-custom-rule").click();
});
document.getElementById("cp-delete-current-workspace")?.addEventListener("click", async () => {
  const workspaceId = controlPlane.editingWorkspaceId;
  if (!workspaceId) return;
  if (!confirm("Delete this workspace? Any open ticket assigned to it will prevent deletion.")) return;
  const deleted = await controlWrite("delete_workspace", { workspace_id: workspaceId });
  if (deleted) { closeControlWorkspaceEditor(); closeControlProjectModal(); }
});
document.getElementById("cp-handoff-cancel")?.addEventListener("click", closeControlHandoffModal);
document.getElementById("cp-handoff-cancel-secondary")?.addEventListener("click", closeControlHandoffModal);
document.getElementById("cp-open-planner")?.addEventListener("click", openControlPlannerModal);
document.getElementById("cp-planner-close")?.addEventListener("click", closeControlPlannerModal);
document.getElementById("cp-planner-cancel")?.addEventListener("click", closeControlPlannerModal);
document.querySelectorAll('input[name="cp-planner-stage"]').forEach((input) => input.addEventListener("change", () => {
  document.querySelectorAll(".cp-planner-choice").forEach((item) => item.classList.toggle("selected", item.querySelector("input").checked));
}));
document.getElementById("cp-planner-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const goal = document.getElementById("cp-planner-goal").value.trim();
  if (goal.length < 8) return controlError(new Error("Describe the outcome in at least eight characters."));
  try {
    const valuesFor = (name) => [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((item) => item.value);
    const stage = document.querySelector('input[name="cp-planner-stage"]:checked')?.value || "feature";
    const result = await api("POST", "/api/control/board/launch-planner", {
      board_id: controlPlane.boardId,
      goal,
      success_criteria: document.getElementById("cp-planner-success").value.trim(),
      context: document.getElementById("cp-planner-context").value.trim(),
      stage,
      product_surfaces: valuesFor("cp-planner-surface"),
      quality_gates: valuesFor("cp-planner-quality"),
      workspace_id: document.getElementById("cp-planner-workspace").value || null,
      client: document.getElementById("cp-planner-client").value,
    });
    closeControlPlannerModal();
    await loadControlPlane();
    controlNotice(`${result.client === "codex" ? "Codex" : "Claude"} planner launched · session ${result.session_id}. Review the plan in Terminal before approving ticket creation.`);
  } catch (error) { controlError(error); }
});
document.getElementById("cp-handoff-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = selectedControlTask();
  if (!task) return;
  try {
    const result = await api("POST", "/api/control/board/launch-handoff", { board_id: controlPlane.boardId,
      ticket_id: task.id,
      recipient: document.getElementById("cp-handoff-recipient").value.trim(),
      note: document.getElementById("cp-handoff-note").value.trim(),
      client: document.getElementById("cp-handoff-client").value,
    });
    closeControlHandoffModal();
    await loadControlPlane();
    controlNotice(`${result.client === "codex" ? "Codex" : "Claude"} launched · session ${result.session_id}`);
  } catch (error) { controlError(error); }
});

document.getElementById("cp-create")?.addEventListener("click", () => {
  document.getElementById("cp-ticket-form").reset();
  renderControlTicketParents();
  updateControlTicketType();
  document.getElementById("cp-ticket-modal").style.display = "flex";
  document.getElementById("cp-ticket-title").focus();
});
document.getElementById("cp-ticket-type")?.addEventListener("change", updateControlTicketType);

function resetControlBoardForm() {
  controlPlane.editingBoardId = null;
  document.getElementById("cp-board-name").value = "";
  document.getElementById("cp-board-description").value = "";
  document.getElementById("cp-board-color").value = "violet";
  document.getElementById("cp-board-modal-heading").textContent = "New board";
  document.getElementById("cp-board-submit").textContent = "Create board";
  document.getElementById("cp-delete-board").style.display = "none";
}
function openControlBoardModal(board = null) {
  resetControlBoardForm();
  if (board) {
    controlPlane.editingBoardId = board.id;
    document.getElementById("cp-board-name").value = board.name || "";
    document.getElementById("cp-board-description").value = board.description || "";
    document.getElementById("cp-board-color").value = board.color || "violet";
    document.getElementById("cp-board-modal-heading").textContent = "Board settings";
    document.getElementById("cp-board-submit").textContent = "Save board";
    document.getElementById("cp-delete-board").style.display = "inline-flex";
  }
  document.getElementById("cp-board-modal").style.display = "flex";
  window.setTimeout(() => document.getElementById("cp-board-name").focus(), 0);
}
function closeControlBoardModal() {
  document.getElementById("cp-board-modal").style.display = "none";
  resetControlBoardForm();
}
document.getElementById("cp-new-board")?.addEventListener("click", () => openControlBoardModal());
document.getElementById("cp-board-settings")?.addEventListener("click", () => openControlBoardModal(controlPlane.data?.active_board));
document.getElementById("cp-board-cancel")?.addEventListener("click", closeControlBoardModal);
document.getElementById("cp-board-cancel-secondary")?.addEventListener("click", closeControlBoardModal);
document.getElementById("cp-board-select")?.addEventListener("change", async (event) => {
  controlPlane.boardId = event.target.value;
  controlPlane.selectedId = null;
  await loadControlPlane();
});
document.querySelectorAll(".cp-view-button").forEach((button) => button.addEventListener("click", () => {
  controlPlane.view = button.dataset.cpView;
  controlPlane.selectedId = null;
  renderControlPlane();
}));
document.getElementById("cp-board-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("cp-board-name").value.trim();
  if (!name) return controlError(new Error("Give the board a name."));
  const board = { name, description: document.getElementById("cp-board-description").value.trim(), color: document.getElementById("cp-board-color").value };
  const action = controlPlane.editingBoardId ? "update_board" : "add_board";
  const boardId = controlPlane.editingBoardId || controlPlane.boardId;
  try {
    const result = await api("POST", "/api/control/board", { action, board_id: boardId, payload: { board, confirm_write: true } });
    if (action === "add_board") controlPlane.boardId = result.board.id;
    closeControlBoardModal();
    await loadControlPlane();
    controlNotice(action === "add_board" ? `Created ${result.board.name}.` : `Updated ${result.board.name}.`);
  } catch (error) { controlError(error); }
});
document.getElementById("cp-delete-board")?.addEventListener("click", async () => {
  const board = controlPlane.data?.active_board;
  if (!board || !confirm(`Delete ${board.name}? Boards with tickets or Epics cannot be deleted.`)) return;
  try {
    const result = await api("POST", "/api/control/board", { action: "delete_board", board_id: board.id, payload: { confirm_write: true } });
    controlPlane.boardId = result.boards[0]?.id || null;
    closeControlBoardModal();
    await loadControlPlane();
    controlNotice(`Deleted ${board.name}.`);
  } catch (error) { controlError(error); }
});
document.getElementById("cp-ticket-cancel")?.addEventListener("click", closeControlTicketModal);
document.getElementById("cp-ticket-cancel-secondary")?.addEventListener("click", closeControlTicketModal);
document.getElementById("cp-ticket-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = document.getElementById("cp-ticket-title").value.trim();
  if (!title) return;
  const criteria = document.getElementById("cp-ticket-criteria").value.split("\n").map((item) => item.trim()).filter(Boolean);
  const result = await controlWrite("add", { task: {
    title,
    description: document.getElementById("cp-ticket-description").value.trim(),
    type: document.getElementById("cp-ticket-type").value,
    priority: document.getElementById("cp-ticket-priority").value,
    workspace_id: document.getElementById("cp-ticket-workspace").value || null,
    parent_id: document.getElementById("cp-ticket-parent").value || null,
    acceptance_criteria: criteria,
  }});
  if (result?.task?.id) { controlPlane.selectedId = result.task.id; closeControlTicketModal(); renderControlPlane(); }
});
document.getElementById("cp-save-project")?.addEventListener("click", async () => {
  const source = document.getElementById("cp-project-source").value;
  const local_directory = document.getElementById("cp-local-directory").value.trim() || null;
  const repository_url = document.getElementById("cp-remote-repository").value.trim() || null;
  const name = document.getElementById("cp-workspace-name").value.trim();
  if (!name) return controlError(new Error("Give the workspace a name."));
  if ((source === "remote" || !local_directory) && !repository_url) return controlError(new Error("Provide a remote repository URL when no local directory is selected."));
  const workspace = { name, source, local_directory, repository_url, branch_rules: controlPlane.workspaceRules.join("; ") || null };
  const action = controlPlane.editingWorkspaceId ? "update_workspace" : "add_workspace";
  const saved = await controlWrite(action, { workspace_id: controlPlane.editingWorkspaceId, workspace });
  if (saved) { closeControlWorkspaceEditor(); closeControlProjectModal(); }
});
document.getElementById("cp-sync-git")?.addEventListener("click", async () => {
  const task = selectedControlTask(); const repo_path = document.getElementById("cp-local-directory").value.trim();
  if (!task) return controlError(new Error("Select a ticket before adding Git evidence."));
  if (!repo_path) return controlError(new Error("Git evidence requires a saved local directory."));
  await controlWrite("attach_git_evidence", { id: task.id, repo_path });
});
document.querySelectorAll(".cp-filter").forEach((button) => button.addEventListener("click", () => {
  controlPlane.filter = button.dataset.cpFilter;
  document.querySelectorAll(".cp-filter").forEach((item) => item.classList.toggle("active", item === button)); renderControlPlane();
}));
document.querySelectorAll(".cp-perspective-button").forEach((button) => button.addEventListener("click", () => {
  controlPlane.perspective = button.dataset.cpPerspective;
  renderControlPlane();
}));
document.addEventListener("dragstart", (event) => {
  const ticket = event.target.closest("[data-cp-ticket]");
  if (!ticket) return;
  const task = controlPlane.data?.tasks.find((item) => item.id === ticket.dataset.cpTicket);
  if (!task) return;
  controlDrag.taskId = task.id;
  controlDrag.sourceStatus = task.status;
  controlDrag.didMove = true;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", task.id);
  ticket.classList.add("dragging");
});
document.addEventListener("dragend", (event) => {
  event.target.closest("[data-cp-ticket]")?.classList.remove("dragging");
  document.querySelectorAll("[data-cp-drop-status]").forEach((column) => column.classList.remove("cp-drop-target"));
});
document.addEventListener("dragover", (event) => {
  const column = event.target.closest("[data-cp-drop-status]");
  if (!column || !controlDrag.taskId) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  column.classList.add("cp-drop-target");
});
document.addEventListener("dragleave", (event) => {
  const column = event.target.closest("[data-cp-drop-status]");
  if (column && !column.contains(event.relatedTarget)) column.classList.remove("cp-drop-target");
});
document.addEventListener("drop", (event) => {
  const column = event.target.closest("[data-cp-drop-status]");
  if (!column || !controlDrag.taskId) return;
  event.preventDefault();
  column.classList.remove("cp-drop-target");
  const task = controlPlane.data?.tasks.find((item) => item.id === controlDrag.taskId);
  if (task) openControlTransitionModal(task, column.dataset.cpDropStatus);
});
document.addEventListener("click", (event) => {
  const ticket = event.target.closest("[data-cp-ticket]");
  if (ticket && !controlDrag.didMove) { controlPlane.selectedId = ticket.dataset.cpTicket; renderControlPlane(); }
  controlDrag.didMove = false;
  const createEpic = event.target.closest("[data-cp-create-epic]");
  if (createEpic) {
    document.getElementById("cp-create").click();
    document.getElementById("cp-ticket-type").value = "epic";
    updateControlTicketType();
    return;
  }
  const action = event.target.closest("[data-cp-action]")?.dataset.cpAction;
  if (action) handleControlAction(action);
  if (event.target.id === "cp-close-detail") { controlPlane.selectedId = null; renderControlPlane(); }
  const triageClient = event.target.closest("[data-cp-launch-triage]")?.dataset.cpLaunchTriage;
  if (triageClient) {
    const clients = triageClient === "all" ? ["codex", "claude"] : [triageClient];
    api("POST", "/api/control/board/launch-triage", { board_id: controlPlane.boardId, clients }).then(async (result) => {
      await loadControlPlane();
      controlNotice(`Launched ${result.launches.length} parallel triage session${result.launches.length === 1 ? "" : "s"} for ${result.ticket_count} ticket${result.ticket_count === 1 ? "" : "s"}.`);
    }).catch(controlError);
    return;
  }
  if (event.target.closest("[data-cp-open-planner]")) {
    openControlPlannerModal();
    return;
  }
  const rulePreset = event.target.closest("[data-cp-rule-preset]")?.dataset.cpRulePreset;
  if (rulePreset) { addControlWorkspaceRule(rulePreset); return; }
  const ruleRemoveIndex = event.target.closest("[data-cp-rule-remove]")?.dataset.cpRuleRemove;
  if (ruleRemoveIndex !== undefined) {
    controlPlane.workspaceRules.splice(Number(ruleRemoveIndex), 1);
    renderControlWorkspaceRules();
    return;
  }
  const editWorkspaceId = event.target.closest("[data-cp-edit-workspace]")?.dataset.cpEditWorkspace;
  if (editWorkspaceId) editControlWorkspace(editWorkspaceId);
});

// ── Local workspace picker ──────────────────────────────────────────────────
const folderPicker = { path: null, parent: null };
async function loadControlDirectories(path) {
  try {
    const query = path ? `?path=${encodeURIComponent(path)}` : "";
    const data = await api("GET", `/api/control/directories${query}`);
    folderPicker.path = data.path; folderPicker.parent = data.parent;
    document.getElementById("cp-folder-current").textContent = data.path;
    document.getElementById("cp-folder-up").disabled = !data.parent;
    document.getElementById("cp-folder-list").innerHTML = data.directories.map((item) => `<button class="cp-folder-row" data-cp-folder="${escapeControl(item.path)}"><span>⌁</span>${escapeControl(item.name)}</button>`).join("") || '<p class="cp-empty">No visible subdirectories.</p>';
  } catch (error) { controlError(error); }
}
function closeControlFolderPicker() { document.getElementById("cp-folder-modal").style.display = "none"; }
document.getElementById("cp-browse-directory")?.addEventListener("click", () => { document.getElementById("cp-folder-modal").style.display = "flex"; loadControlDirectories(document.getElementById("cp-local-directory").value.trim() || undefined); });
document.getElementById("cp-folder-close")?.addEventListener("click", closeControlFolderPicker);
document.getElementById("cp-folder-up")?.addEventListener("click", () => { if (folderPicker.parent) loadControlDirectories(folderPicker.parent); });
document.getElementById("cp-folder-select")?.addEventListener("click", () => { if (folderPicker.path) document.getElementById("cp-local-directory").value = folderPicker.path; updateControlProjectWarning(); closeControlFolderPicker(); });
document.addEventListener("click", (event) => { const target = event.target.closest("[data-cp-folder]"); if (target) loadControlDirectories(target.dataset.cpFolder); });
