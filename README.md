<div align="center">

# ⚡ AgenticStore MCP: The Ultimate Open-Source AI Agent Toolkit
**Supercharge your AI Assistant with 27 Powerful Model Context Protocol (MCP) Tools**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg?style=for-the-badge)](https://modelcontextprotocol.io)
[![PyPI](https://img.shields.io/pypi/v/agentic-store-mcp?color=blue&style=for-the-badge)](https://pypi.org/project/agentic-store-mcp/)

[🚀 Quick Start](#-quick-start-guide-fastest-way-to-install) • [📋 Full Tool Directory](#-tool-directory--all-27-tools) • [🌐 Web Search](#-enabling-web-search) • [🔌 Client Setup](#-connect-to-your-ai-client) • [🖥️ GUI Webapp](https://agenticstore.dev/docs/gui)

</div>

---

<!-- SEO: Model Context Protocol tools, MCP server, Claude Desktop MCP, Cursor MCP, open-source AI tools, self-hosted MCP, Python MCP server, AI agent toolkit, web search MCP, code review MCP, MCP Hub GUI, agent memory MCP, AI productivity tools, LLM tools open source, Windsurf MCP, VS Code AI >> -->

<br/>

> **AgenticStore MCP** turns **Claude Desktop, Cursor, and Windsurf** into unstoppable autonomous agents. Get instant access to web search, codebase analysis, deep semantic memory, and a beautiful local GUI—all locally hosted, with absolutely zero subscriptions or vendor lock-in.

<div align="center">
  <h3>🎥 Watch the GUI Demo in Action</h3>

https://github.com/user-attachments/assets/e894bd97-b535-4563-ada8-5561c8d10513

</div>

## 🔥 Why Choose AgenticStore MCP?

- **🔒 100% Privacy-First:** Everything runs locally. Your code and data never leave your machine.
- **💸 Truly Free:** No accounts, no paywalls, no subscriptions.
- **🧠 Persistent Agent Memory:** Let your AI remember facts and contexts across sessions seamlessly.
- **⚡ Plug & Play:** Installs instantly via `uvx` or `pip`. 

---

## 📋 Table of Contents

- [🧰 What's Inside the Toolkit](#-whats-inside-the-toolkit)
- [🚀 Quick Start Guide (Fastest Way to Install)](#-quick-start-guide-fastest-way-to-install)
  - [V0: Python/uvx (Recommended)](#v0--python--uvx-fastest-start-no-docker-needed)
  - [V1: From GitHub Source](#v1--from-github-source-latest-features)
  - [V2: MCP Hub Webapp (UI)](#v2--mcp-hub-webapp-gui-to-manage-everything)
- [🔌 Connect to Your AI Client](#-connect-to-your-ai-client)
- [🗂 Tool Directory — All 27 Tools](#-tool-directory--all-27-tools)
- [🔎 Enabling Web Search](#-enabling-web-search)
- [🎛 Advanced Usage & CLI Flags](#-advanced-usage--cli-flags)

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

## 🚀 Quick Start Guide (Fastest Way to Install)

Pick the setup that best fits your workflow. *Don't know which to pick? Start with V0.*

<details open>
<summary><strong><kbd>V0</kbd> — Python / uvx (Fastest start, no Docker needed)</strong></summary>
<br/>

**1️⃣ Install via PyPI**
```bash
pip install agentic-store-mcp --upgrade
```
*(Or use `uvx agentic-store-mcp` if you have Astral's toolchain).*

**2️⃣ Run the MCP server**
```bash
agentic-store-mcp
```

**3️⃣ Configure your AI Client**  
See the [Connect to Your AI Client](#-connect-to-your-ai-client) section to link it!

> 💡 **Pro-Tip (Web Search):** Want web search? Add `"env": { "SEARXNG_URL": "http://localhost:8080" }` to your config and use our integrated search instance. See [Web Search Setup](#-enabling-web-search).

</details>

<details>
<summary><strong><kbd>V1</kbd> — From GitHub Source (Latest Features)</strong></summary>
<br/>

**1️⃣ Install directly from the repository**
```bash
pip install git+https://github.com/agenticstore/agentic-store-mcp.git
```
*(Or using uv: `uvx --from git+https://github.com/agenticstore/agentic-store-mcp.git agentic-store-mcp`)*

**2️⃣ Run the MCP server**
```bash
agentic-store-mcp
```

**3️⃣ Configure your AI Client**  
See the [Connect to Your AI Client](#-connect-to-your-ai-client) section to link it!

</details>

<details>
<summary><strong><kbd>V2</kbd> — MCP Hub UI (Manage everything visually)</strong></summary>
<br/>

Forget manual JSON editing! Use our local web UI to:
- 🔑 **Connectors:** Enter remote API keys securely (stored in OS keyring).
- 🛠️ **Tools:** Toggle which of the 27 tools to expose to the AI.
- 💻 **Clients:** Auto-generate configuration for Claude, Cursor, and Windsurf.
- 🧠 **Memory:** Manage persistent agent states, checkpoints, and logs.

**Start the Hub via Python:**
```bash
# Ensure it is installed via pip
pip install agentic-store-mcp --upgrade

# Launch the visual web controller
agentic-store-webapp 
```

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

**The Config Snippet (for standard setup):**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "agentic-store-mcp",
      "args": []
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

If you'd like to use a remote API or host your own container, simply append its URL.

**Pass the environment variable to your AI Client:**
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "agentic-store-mcp",
      "args": [],
      "env": {
        "SEARXNG_URL": "http://localhost:8080"
      }
    }
  }
}
```

---

## 🎛 Advanced Usage & CLI Flags

Need granular control? Filter exactly what gets loaded via environment variables if integrating deeply without the web GUI.

```bash
# Debug: List what would be loaded and exit
agentic-store-mcp --list
```

---

## 📜 License & Support

This project is licensed under the **MIT License** — free to use, modify, and distribute. See [LICENSE](LICENSE) for details.

---

<div align="center">

⭐ **Manage Everything Easier via the Webapp:** `agentic-store-webapp`
*Built with ❤️ by [AgenticStore.dev](https://agenticstore.dev) — Open-source AI tooling for everyone.*

</div>
