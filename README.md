<div align="center">

# ⚡ AgenticStore MCP Server: LLM Prompt Firewall & AI Security Toolkit 
**Open-Source Model Context Protocol (MCP) Server for Data Privacy, Prompt Recording, Audit Logs, and 27+ Agent Tools for Claude, Cursor, and Windsurf.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg?style=for-the-badge)](https://modelcontextprotocol.io)
[![PyPI](https://img.shields.io/pypi/v/agentic-store-mcp?color=blue&style=for-the-badge)](https://pypi.org/project/agentic-store-mcp/)

[🚀 Quick Start](#-quick-start-guide-fastest-way-to-install) • [🛡️ Prompt Firewall](#%EF%B8%8F-llm-prompt-firewall--sanitization) • [🗂️ Full Tool Directory](#-tool-directory--all-27-tools) • [🌐 Web Search](#-enabling-web-search) • [🔌 Client Setup](#-connect-to-your-ai-client) • [🖥️ GUI Webapp](https://agenticstore.dev/docs/gui)

</div>

---

## 🔒 Why You Need This: Enterprise-Grade AI Security Meets Autonomous Agents

You are building the future using autonomous AI coding assistants and agents like **Claude Code, Cursor, and Windsurf**. Giving them access to the web, your codebase, and persistent memory is a superpower, but passing sensitive enterprise data directly to remote LLM APIs presents a massive security risk. You need comprehensive **AI Data Loss Prevention (DLP)** and **AI security**. You demand clear **audit traces for AI usage** and strict **prompt recording** to ensure compliance and prevent critical data leaks.

**AgenticStore MCP Server** solves both halves of the equation. 

First, it acts as an **LLM Prompt Firewall**, establishing a secure local proxy to intercept, scan, and sanitize any prompts leaving your system to guard against prompt injection and data leaks. Secure your agentic workflows with structured **prompt recording** and generate clear **audit traces for AI usage**. Flag leaked secrets, PII, and API keys, and use local LLM models (like **Ollama**) to sanitize your data *before* it reaches the cloud. 

Second, it provides a robust, production-ready **Model Context Protocol (MCP) Toolkit**, arming your AI assistants with 27 specific tools ranging from self-hosted SearXNG web search to deep persistent semantic memory. 

Configure your MCP server tools manually or effortlessly through a beautiful local GUI. Zero subscriptions. Zero vendor lock-in.

<div align="center">
  <h3>🎥 Prompt Firewall Demo</h3>

  <video src="https://github.com/user-attachments/assets/4e1976e1-c4a3-4737-9a4e-7539abc4e89c" width="100%" controls title="AgenticStore Prompt Firewall Demo">
    Your browser does not support the video tag. <a href="https://github.com/user-attachments/assets/4e1976e1-c4a3-4737-9a4e-7539abc4e89c">Take a look at the Prompt Firewall Demo video here</a>.
  </video>
  <br/>
  <i>(If the video above doesn't load, <a href="https://github.com/user-attachments/assets/4e1976e1-c4a3-4737-9a4e-7539abc4e89c">click here to watch the demo</a>)</i>

  <br/><br/>

  <details>
  <summary><strong>🎥 Watch the GUI Demo in Action (MCP Tools)</strong></summary>
  <br/>

  <video src="https://github.com/user-attachments/assets/e894bd97-b535-4563-ada8-5561c8d10513" width="100%" controls title="AgenticStore MCP User Interface Demo">
    Your browser does not support the video tag. <a href="https://github.com/user-attachments/assets/e894bd97-b535-4563-ada8-5561c8d10513">Take a look at the AgenticStore MCP GUI Demo video here</a>.
  </video>
  <br/>
  <i>(If the video above doesn't load, <a href="https://github.com/user-attachments/assets/e894bd97-b535-4563-ada8-5561c8d10513">click here to watch the demo</a>)</i>

  <br/><br/>
  </details>

  <br/>

  <h3>🏗️ How It Works</h3>

<img src="docs/Agentic Store Architecture.png" alt="AgenticStore Architecture" width="100%" />

</div>

## 🔥 Why Choose AgenticStore MCP?

| Feature | AgenticStore MCP Server | Standard MCP Servers |
| :--- | :--- | :--- |
| **AI Security & Prompt Firewall** | 🛡️ Yes (Proxy & Rule-based DLP) | ❌ No |
| **Audit Traces & Logs** | 📝 Yes (Prompt recording & compliance) | ❌ No |
| **Local LLM Prompt Sanitization**| 🦙 Yes (Ollama integration) | ❌ No |
| **Persistent Agent Memory** | 🧠 Yes (survives restarts & sessions) | ❌ No |
| **Agentic Web Search** | 🌐 Self-hosted SearXNG | ❌ Usually No |
| **Capabilities** | 🛠️ 27+ specialized tools | ⛏️ 1 to 5 basic tools |
| **Configuration** | 🖥️ Web GUI Dashboard OR ⚙️ Manual | ⚙️ Manual JSON setup |
| **Privacy** | 🔒 100% Local Execution | 🔒 Varies |

- **🛡️ LLM Prompt Firewall:** Intercept, sanitize, and perform **prompt recording** for all data leaving your system, ensuring robust **AI security**.
- **🔒 100% Privacy-First:** Everything runs locally. Generate reliable **audit traces for AI usage** while your code and data never leave your machine unaudited.
- **💸 Truly Free:** No accounts, no paywalls, no subscriptions.
- **🧠 Persistent Agent Memory:** Let your AI remember facts and contexts across sessions seamlessly.
- **⚡ Plug & Play:** Installs instantly via `uvx` or `pip`. MCP configuration supports both manual JSON and GUI workflows.

---

## 📋 Table of Contents

- [🛡️ LLM Prompt Firewall & Sanitization](#%EF%B8%8F-llm-prompt-firewall--sanitization)
- [🧰 What's Inside the Toolkit](#-whats-inside-the-toolkit)
- [🚀 Quick Start Guide (Fastest Way to Install)](#-quick-start-guide-fastest-way-to-install)
  - [V0: Python/uvx (Recommended)](#v0--python--uvx-fastest-start-no-docker-needed)
  - [V1: From GitHub Source](#v1--from-github-source-latest-features)
  - [V2: MCP Hub Webapp (UI)](#v2--mcp-hub-webapp-gui-to-manage-everything)
- [🔌 Connect to Your AI Client](#-connect-to-your-ai-client)
- [🗂 Tool Directory — All 27 Tools](#-tool-directory--all-27-tools)
- [🔎 Enabling Web Search](#-enabling-web-search)
- [🎛 Overriding Configs & Advanced Usage](#-overriding-configs--advanced-usage)

---

## 🛡️ LLM Prompt Firewall & Sanitization

The **Prompt Firewall** gives you complete control over what natural language data and code leaves your computer when using cloud-based AI coding assistants, delivering enterprise-grade **AI security**.

> [!NOTE]
> The Firewall feature is currently tested and stable on **macOS**. Support for Linux and Windows is coming soon!

**Key Features:**
- **Proxy Interception**: Set up a local proxy to monitor all LLM traffic.
- **Audit Traces for AI Usage**: Automatically generate **prompt recording** logs. Get clear warnings at each prompt level showing exactly what was changed or redacted.
- **1-Click UI Setup**: Install certificate -> start proxy. The magic starts immediately. *(Note: Firewall setup is only made available on the UI to ensure smooth installation and operation).*
- **Local LLM Integration (Optional)**: Connect your local **Ollama** instance. Download open-source models to run completely local, pre-flight prompt sanitization, scanning your code to make it better and safer before sending it to a remote API.
- **Rule-Based Sanitization**: Easily define regex or grammar rules to block PII, AWS keys, database strings, or proprietary logic.

To enable the firewall and begin collecting **audit traces for AI usage**, start the [GUI Webapp](#v2--mcp-hub-webapp-gui-to-manage-everything) and navigate to the **Firewall** tab to install the certificate and start the proxy.

---

## 🧰 What's Inside the Toolkit (27 MCP Tools)

Equip your AI client with these 4 powerhouse modules containing **27 specific MCP tools**:

| Module | Purpose | Key Capabilities | Tools |
| :--- | :--- | :--- | :---: |
| 💻 **DevSecOps & Code Analysis** | Codebase mastery & safety | Static analysis, OSV CVE scans, Git commit summaries | **11** |
| 🌐 **Web Crawling & Search** | Internet access for Agents | Private web search (SearXNG) and deep web crawling | **2** |
| 🧠 **Persistent Agent Memory** | Agent context persistence | Save/read facts, session checkpoints, changelog generation | **12** |
| 🔧 **Meta-Tools & Config** | Configuration & discovery | Tool discovery, runtime config management | **2** |

---

## 🚀 Quick Start Guide (Fastest Way to Install)

Pick the setup that best fits your workflow. MCP supports both manual configuration and GUI-based management setup. *Don't know which to pick? Start with V0.*

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

**3️⃣ (Optional) Check your installation**
```bash
agentic-store-mcp --version
```

**4️⃣ Configure your AI Client**  
See the [Connect to Your AI Client](#-connect-to-your-ai-client) section to link it manually, or use the UI!

> 💡 **Pro-Tip (Web Search):** Want web search? Check out our Copy-Paste Config below. See [Web Search Setup](#-enabling-web-search).

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
- 🛡️ **Firewall:** Setup certificates and monitor all intercepted LLM prompts and audit logs for comprehensive **prompt recording**.
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

Because AgenticStore MCP supports both manual configuration and management via the GUI, you can manually add the configuration snippet to your respective client's config file if you prefer. **Remember to restart the client after saving!**

| Client | Config File Path |
| :--- | :--- |
| **Claude Desktop (Mac)** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Claude Desktop (Win)** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Cursor** | `~/.cursor/mcp.json` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` |
| **VS Code** | Appends to your VS Code `settings.json` under MCP extension config |

### Standard Copy-Paste Config

**Basic Setup:**
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

**With Web Search (SearXNG) enabled:**
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

<div align="center">
  <br/>
  <a href="#-agenticstore-mcp-llm-prompt-firewall--ai-security-toolkit">⬆️ Back to Top</a>
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

## 🎛 Overriding Configs & Advanced Usage

Overriding configs is related to your **MCP setup**. MCP supports both manual and GUI setup, so you can filter exactly what tools get loaded via environment variables if integrating deeply without the web GUI.

```bash
# Debug: List what would be loaded and exit
agentic-store-mcp --list
```
*Note: The LLM Prompt Firewall is exclusively configured via the UI. The firewall is only made available on the UI to ensure smooth setup, robust proxy interception, and seamless prompt recording out of the box.*

---

## 🛠️ Troubleshooting

**Internet Disruption After Proxy Use**
When dealing with the LLM Prompt Firewall proxy, if the server is terminated abruptly, there could be an internet disruption on your machine due to residual system proxy settings.

If you lose internet connection after a crash, run this command in your terminal to restore your proxy to default:
```bash
networksetup -setsecurewebproxystate "Wi-Fi" off
```

---

## 🤝 Contributing & Community

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**. 

If you'd like to contribute code or improvements, please fork the repository and create a Pull Request.

**⭐ If this toolkit saved you 10 hours of configuration, please give us a star to help others find it!**

---

## 📜 License & Support

This project is licensed under the **MIT License** — free to use, modify, and distribute. See [LICENSE](LICENSE) for details.

---

<div align="center">

⭐ **Manage Everything Easier via the Webapp:** `agentic-store-webapp`

---
*Built with ❤️ by [AgenticStore.dev](https://agenticstore.dev) — Open-source AI tooling for everyone.*

<br/>

### 🏷️ Core Technologies & Ecosystem
AgenticStore is built for the **Model Context Protocol (MCP Server)** ecosystem to provide robust **LLM Security**, a **Prompt Firewall**, and proactive **AI Data Privacy**. It supports comprehensive **Data Loss Prevention (DLP)** through **Prompt Sanitization**, **Prompt Recording**, and **Audit Traces for AI Usage**. Designed for **Autonomous Agents** and **AI Coding Assistants** like **Claude Code**, **Cursor IDE**, and **Windsurf**, it leverages **Persistent Agent Memory**, **AI DevSecOps**, **Web Search** via **SearXNG**, and **Local LLM** capabilities with **Ollama Integration** for reliable **AI Auditing**.

</div>
