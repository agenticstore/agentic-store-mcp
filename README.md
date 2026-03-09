<div align="center">

# ⚡ AgenticStore MCP: The Ultimate Open-Source AI Agent Toolkit
**Supercharge your AI Assistant with 27 Powerful Model Context Protocol (MCP) Tools**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg?style=for-the-badge)](https://modelcontextprotocol.io)
[![GitHub Stars](https://img.shields.io/github/stars/agenticstore/agentic-store-mcp?style=for-the-badge&color=gold)](https://github.com/agenticstore/agentic-store-mcp)

[🚀 Quick Start](#-quick-start-guide-3-ways-to-install) • [📋 Full Tool Directory](#-tool-directory--all-27-tools) • [🌐 Web Search](#-enabling-web-search) • [🔌 Client Setup](#-connect-to-your-ai-client) • [⭐ Star Repo](https://github.com/agenticstore/agentic-store-mcp)

</div>

---

<!-- SEO: Model Context Protocol tools, MCP server, Claude Desktop MCP, Cursor MCP, open-source AI tools, self-hosted MCP, Python MCP server, AI agent toolkit, web search MCP, code review MCP, GitHub MCP tools, agent memory MCP, AI productivity tools, LLM tools open source, Windsurf MCP, VS Code AI >> -->

<br/>

> **AgenticStore MCP** turns **Claude Desktop, Cursor, and Windsurf** into unstoppable autonomous agents. Get instant access to web search, codebase analysis, GitHub integration, and persistent memory—all locally hosted, with no subscriptions or vendor lock-in.

## 🔥 Why Choose AgenticStore MCP?

- **🔒 100% Privacy-First:** Everything runs locally. Your code and data never leave your machine.
- **💸 Truly Free:** No accounts, no paywalls, no subscriptions.
- **🧠 Persistent Agent Memory:** Let your AI remember facts and contexts across sessions.
- **⚡ Plug & Play:** Installs in seconds via `uvx` or Docker.

---

## 📋 Table of Contents

- [🧰 What's Inside the Toolkit](#-whats-inside-the-toolkit)
- [🚀 Quick Start Guide (3 Ways to Install)](#-quick-start-guide-3-ways-to-install)
  - [V0: Python/uvx (Fastest)](#v0--python--uvx-fastest-start-no-docker-needed)
  - [V1: Docker (Isolated)](#v1--docker-no-python-required-isolated-environment)
  - [V2: MCP Hub Webapp (UI)](#v2--mcp-hub-webapp-gui-to-manage-everything)
- [🔌 Connect to Your AI Client](#-connect-to-your-ai-client)
- [🗂 Tool Directory — All 27 Tools](#-tool-directory--all-27-tools)
- [🔎 Enabling Web Search](#-enabling-web-search)
- [🎛 Advanced Usage & CLI Flags](#-advanced-usage--cli-flags)
- [🤝 Contributing](#-contributing)

---

## 🧰 What's Inside the Toolkit

Equip your AI client with these 4 powerhouse modules containing **27 specific tools**:

| Module | Purpose | Key Capabilities | Tools |
| :--- | :--- | :--- | :---: |
| 💻 **Code & Security** | Codebase mastery & safety | Static analysis, CVE scans, Git commit summaries | **11** |
| 🌐 **Data & Search** | Web access | Private web search (SearXNG) and deep web crawling | **2** |
| 🧠 **Memory** | Agent context persistence | Save/read facts, session checkpoints, changelogs | **12** |
| 🔧 **Meta-Tools** | Configuration & discovery | Tool discovery, runtime config management | **2** |

---

## 🚀 Quick Start Guide (3 Ways to Install)

Pick the setup that best fits your workflow. *Don't know which to pick? Start with V0.*

<details open>
<summary><strong><kbd>V0</kbd> — Python / uvx (Fastest start, no Docker needed)</strong></summary>
<br/>

**1️⃣ Install `uv` (one-time setup)**
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2️⃣ Run the MCP server**
```bash
uvx --refresh agentic-store-mcp
```
*(The `--refresh` flag ensures you always pull the latest published stable version).*

**3️⃣ Configure your AI Client**  
See the [Connect to Your AI Client](#-connect-to-your-ai-client) section to link it!

> 💡 **Pro-Tip (Web Search):** Want web search? Add `"env": { "SEARXNG_URL": "http://localhost:8080" }` to your config and run `docker compose up -d searxng` from this repo. See [Web Search Setup](#-enabling-web-search).

</details>

<details>
<summary><strong><kbd>V1</kbd> — Docker (No Python required, fully isolated)</strong></summary>
<br/>

**1️⃣ Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is running**

**2️⃣ Clone and start services**
```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
docker compose up -d
```
*This starts a private web search engine (SearXNG) at `http://localhost:8080` and the AgenticStore Webapp at `http://localhost:8765`.*

**3️⃣ Client configuration**  
Open `http://localhost:8765` → **Clients tab** to get your exact copy-paste config snippet. Example for Claude:

```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "agentic-store-mcp_agentic-store-memory:/root/.config/agentic-store",
        "--network", "agentic-store-mcp_default",
        "-e", "SEARXNG_URL=http://searxng:8080",
        "agentic-store-mcp"
      ]
    }
  }
}
```

</details>

<details>
<summary><strong><kbd>V2</kbd> — MCP Hub UI (Manage everything visually)</strong></summary>
<br/>

Forget manual JSON editing! Use our local web UI to:
- 🔑 **Connectors:** Enter GitHub/OpenAI API keys securely (stored in OS keyring).
- 🛠️ **Tools:** Toggle which of the 27 tools to expose to the AI.
- 💻 **Clients:** Auto-generate configuration for Claude, Cursor, and Windsurf.
- 🧠 **Memory:** Manage persistent agent states, checkpoints, and logs.

**Start the Hub via Python:**
```bash
# Option A — from a cloned repo
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
uv sync
uv run webapp.py

# Option B — if installed via uvx / pip
uvx agentic-store-mcp  # installs the package
agentic-store-webapp   # launches the webapp
```
*(Or via Docker: `docker compose up -d`)*

**Access it at:** [http://localhost:8765](http://localhost:8765)

</details>

---

## 🔌 Connect to Your AI Client

Add the configuration snippet to your respective client's config file. **Remember to restart the client after saving!**

| Client | Config File Path |
| :--- | :--- |
| **Claude Desktop (Mac)** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Desktop (Win)** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Cursor** | `~/.cursor/mcp.json` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` |
| **VS Code** | Appends to your VS Code `settings.json` under MCP extension config |

**The Config Snippet (for V0 `uvx` setup):**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "uvx",
      "args": ["--refresh", "agentic-store-mcp"]
    }
  }
}
```

<div align="center">
  <br/>
  <a href="#-agenticstore-mcp-the-ultimate-open-source-ai-agent-toolkit">⬆️ Back to Top</a>
</div>

---

## 🗂 Tool Directory — All 27 Tools

<details>
<summary><strong>💻 Code Tools & Integrations (11 tools)</strong></summary>
<br/>

### Codebase Analysis
*Analyze, search, and navigate your codebase flawlessly.*

| Tool | Capability |
|------|-------------|
| `python_lint_checker` | Runs static analysis on Python files (finds bugs, unused imports, complexity). No external deps. |
| `search_code` | Blazing-fast full-text search across local codebases with regex & file-type filtering. |
| `get_file` | Read files from defined paths, including specific line-range slicing. |
| `analyze_commits` | Contextualize agents with recent repo history (diff stats, authors, messages). |

### GitHub Integration 
*(Requires a GitHub Personal Access Token. Set via `GITHUB_TOKEN` or MCP Hub).*

| Tool | Capability |
|------|-------------|
| `get_repo_info` | Fetch metadata: stars, forks, primary language, open issues. |
| `manage_issue` | Create, comment on, close, or list issues in accessible repositories. |
| `create_pr` | Automatically open new internal Pull Requests with title & body definitions. |

### Security & Auditing
*Agent-driven DevSecOps.*

| Tool | Capability |
|------|-------------|
| `repo_scanner` | Detects leaked secrets (API keys), PII, and validates `.gitignore`. |
| `dependency_audit` | Scans `requirements.txt`, `package.json`, etc. against the OSV CVE database. |
| `code_scanning_alerts` | Fetches active CodeQL/Security alerts from GitHub. |
| `dependabot_alerts` | Fetches Dependabot vulnerability alerts from GitHub. |

</details>

<details>
<summary><strong>🌐 Data & Search (2 tools)</strong></summary>
<br/>

| Tool | Capability |
|------|-------------|
| `agentic_web_crawl` | Extract clean markdown text, headings, and metadata from any URL. Handles redirects beautifully. |
| `agentic_web_search` | Conduct live web searches via self-hosted SearXNG. Returns structured snippets. |

</details>

<details>
<summary><strong>🧠 Memory & Agent Orchestration (12 tools)</strong></summary>
<br/>

*Persistent memory lets AI agents hand off work across sessions and restarts. 100% locally stored.*

### Storage Primitives
| Tool | Capability |
|------|-------------|
| `memory_write` | Store a key-value fact in local JSON. Survives restarts. |
| `memory_read` | Retrieve specific (or all) stored facts. |
| `memory_search` | Fuzzy full-text search across all stored facts. |
| `memory_log` | Append timestamped entries to an immutable session JSONL log (decision trails). |
| `memory_checkpoint` | Save a complete snapshot: state, decisions, next steps, and client context. |
| `memory_restore` | Load a named checkpoint back into the active agent context. |

### Productivity Layer
| Tool | Capability |
|------|-------------|
| `spinup_memory` | Initialize a new project context (stub files for plans, milestones, learnings). |
| `restore_session` | One-call holistic session restore (loads latest checkpoint, plans, logs, and facts). |
| `update_plan` | Create or update the active `plan.md` for task tracking. |
| `update_milestones` | Append or patch individual milestone progress via regex. |
| `update_learnings` | Log technical discoveries into a growing context directory. |
| `update_change_log` | Append semantic release notes to `CHANGELOG.md` automatically. |

</details>

<details>
<summary><strong>🔧 Toolkit Meta-Tools (2 tools)</strong></summary>
<br/>

| Tool | Capability |
|------|-------------|
| `tool_search` | List all available toolkit tools, requirements, and descriptions. |
| `configure` | Dynamically override runtime configurations and module states. |

</details>

---

## 🔎 Enabling Web Search

To give your agent internet access, `agentic_web_search` uses a private [SearXNG](https://github.com/searxng/searxng) instance.

**1. Start the SearXNG Docker container:**
```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
docker compose up -d searxng
```

**2. Pass the environment variable to your AI Client:**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "uvx",
      "args": ["--refresh", "agentic-store-mcp"],
      "env": {
        "SEARXNG_URL": "http://localhost:8080"
      }
    }
  }
}
```

---

## 🎛 Advanced Usage & CLI Flags

Need granular control? Filter exactly what gets loaded.

```bash
# Load everything
uvx --refresh agentic-store-mcp

# Load only specific feature modules
uvx --refresh agentic-store-mcp --modules code
uvx --refresh agentic-store-mcp --modules data memory

# Load only specific isolated tools
uvx --refresh agentic-store-mcp --tools agentic_web_search repo_scanner

# Debug: List what would be loaded and exit
uvx --refresh agentic-store-mcp --list
```

---

## 🤝 Contributing

We want to build the ultimate open-source tool directory for Agents!

**Tool Guidelines:**
- 🐍 **Pure Python** — No weird managed services, no mandatory accounts.
- 📦 **Self-contained** — Placed inside `agentic_store_mcp/modules/<module>/<submodule>/<tool_name>/`.
- 🧪 **Tested** — Must have a `test_handler.py` smoke test.
- 📚 **Documented** — Include a `README.md` for tool usage.

**Local Dev Setup:**
```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
uv sync

# Run tests
uv run pytest

# Start the MCP server
uv run server.py

# Start the webapp (MCP Hub UI)
uv run webapp.py
```

---

## 📜 License & Support

This project is licensed under the **MIT License** — free to use, modify, and distribute. See [LICENSE](LICENSE) for details.

---

<div align="center">

⭐ **If AgenticStore MCP makes your workflow faster, please [star the repository](https://github.com/agenticstore/agentic-store-mcp) to help others discover it!** ⭐

*Built with ❤️ by [AgenticStore.dev](https://agenticstore.dev) — Open-source AI tooling for everyone.*

</div>
