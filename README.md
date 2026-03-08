# ⚡ Agentic Store MCP: Free, Open-Source Tools for AI Agents

<!-- SEO Metadata -->
<!-- Keywords: Model Context Protocol, MCP server, AI agents, Claude Desktop MCP, Cursor MCP, open-source MCP tools, Python MCP, self-hosted AI tools, web search MCP, Python lint checker MCP -->

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker Pulls](https://img.shields.io/docker/pulls/agenticstore/agentic-store-mcp.svg)](https://hub.docker.com/r/agenticstore/agentic-store-mcp)

Give your AI agents superpowers with **Agentic Store MCP**—a collection of free, open-source, and self-hosted tools built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

No accounts, no API limits, no subscriptions. Just pure, self-hosted capabilities for your favorite AI assistants.

**Fully compatible with:** [Claude Desktop](#-claude-desktop), [Cursor](#-cursor), [Windsurf](#-windsurf), [VS Code](#-vs-code-mcp-extension), and any other MCP-compatible client.

---

## 🚀 Quick Start: Installation

Get started in less than a minute. Choose your preferred environment:

### Method 1: Python (Recommended for Developers)

Using `uv` (the fast Python package installer):

```bash
uvx --refresh agentic-store-mcp
```

_Note: The `--refresh` flag ensures you always run the latest published version._

**Need to install `uv`?**

- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Method 2: Docker (No Python Required)

```bash
docker run --rm agenticstore/agentic-store-mcp:latest --list
```

---

## 🛠️ MCP Tool Directory

Our tools are organized into powerful modules designed to solve specific workflow challenges for AI agents.

### 🌐 AgenticData Module

Empower your AI to gather real-time information from the web.

- **`agentic_web_crawl` — Advanced Web Scraper & Crawler**
  - **What it does:** Fetches any URL and extracts clean page text, SEO metadata, heading structures, links, and images. Handles redirects and encoding automatically.
  - **Use Case:** Let Claude or Cursor read external documentation, scrape competitor sites, or summarize web articles.
  - **Requirements:** None! Works out of the box.

- **`agentic_web_search` — Private Metasearch Engine**
  - **What it does:** Searches the web via a self-hosted SearXNG instance. Returns ranked results with titles, URLs, and text snippets.
  - **Use Case:** Give your AI live internet access without paying for search APIs.
  - **Requirements:** Requires a local [SearXNG](https://github.com/searxng/searxng) instance (`docker compose up -d`).

### 💻 AgenticCode Module

Give your AI the ability to analyze, lint, and secure codebases autonomously.

- **`python_lint_checker` — Python Static Analysis**
  - **What it does:** Checks Python files for imports, bugs, styling issues, and code complexity.
  - **Use Case:** Ask your AI to review your Python code for PEP-8 compliance and logical bugs.
  - **Requirements:** None! Zero external dependencies.

- **`repo_scanner` — Security & Secret Scanner**
  - **What it does:** Scans directories for leaked secrets (AWS keys, API tokens), PII (emails, SSNs), and `.gitignore` gaps.
  - **Use Case:** Run a security audit on your project before committing code to public repositories.
  - **Requirements:** None!

- **`dependency_audit` — Vulnerability Checker**
  - **What it does:** Audits package files (`requirements.txt`, `package.json`, `go.mod`, etc.) for outdated versions and known CVEs using the OSV database.
  - **Use Case:** Ask your AI to check if your project's dependencies are secure and up-to-date.
  - **Requirements:** None!

---

## 🔌 Connecting to Your AI Client

Add AgenticStore to your MCP client's configuration file to enable the tools, then restart the client.

<details>
<summary><h3>🧠 Claude Desktop</h3></summary>

**Config locations:**

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Python (All Tools)**

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

**Docker (All Tools)**

```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "agenticstore/agentic-store-mcp:latest"]
    }
  }
}
```

_(Check the bottom of this section for SearXNG setup instructions if you want web search enabled!)_

</details>

<details>
<summary><h3>💻 Cursor</h3></summary>

**Config location:** `~/.cursor/mcp.json`

**Python (All Tools)**

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

</details>

<details>
<summary><h3>🏄 Windsurf</h3></summary>

**Config location:** `~/.codeium/windsurf/mcp_config.json`

_(Configuration is identical to the Cursor setup above.)_

</details>

<details>
<summary><h3>📝 VS Code (MCP Extension)</h3></summary>

_(Configuration is identical to the Cursor setup above.)_

</details>

---

## 🔎 Enabling Web Search (`agentic_web_search`)

To use the web search tool, you need a running [SearXNG](https://github.com/searxng/searxng) instance.

1. **Start SearXNG via Docker:**
   ```bash
   git clone https://github.com/agenticstore/agentic-store-mcp
   cd agentic-store-mcp
   docker compose up -d
   ```
2. **Update your MCP config with the `SEARXNG_URL` environment variable:**

**Python users:**

```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "uvx",
      "args": ["--refresh", "agentic-store-mcp"],
      "env": { "SEARXNG_URL": "http://localhost:8080" }
    }
  }
}
```

**Docker users:**

```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--network",
        "agentic-store-mcp_default",
        "-e",
        "SEARXNG_URL=http://searxng:8080",
        "agenticstore/agentic-store-mcp:latest"
      ]
    }
  }
}
```

---

## 🎛️ Advanced Usage & CLI Flags

Filter which tools or modules your AI has access to using the CLI:

```bash
uvx --refresh agentic-store-mcp                              # Run all tools
uvx --refresh agentic-store-mcp --modules code               # Only load AgenticCode
uvx --refresh agentic-store-mcp --modules data               # Only load AgenticData
uvx --refresh agentic-store-mcp --tools agentic_web_search   # Only load a specific tool
uvx --refresh agentic-store-mcp --list                       # List all available tools and exit
```

## 🏗️ Programmatic Usage (Python)

Integrate these MCP tools directly into your own LangChain, LlamaIndex, or custom AI python scripts:

```python
from agentic_store_mcp import start_server

start_server()                              # Load all tools
start_server(modules=["code", "data"])      # Load multiple categories
start_server(tools=["agentic_web_search"])  # Load a single tool
```

---

## 🤝 Contributing & Community

We welcome contributions! To add a new tool:

1. Ensure the tool is **pure Python** (no external managed services, completely self-hosted).
2. Create your tool under `agentic_store_mcp/modules/<category>/<tool_name>/` containing:
   - `handler.py`
   - `schema.json`
   - `README.md`
   - `test_handler.py`
3. Run tests locally using `uv run pytest`.

## 📜 License & Support

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

**⭐ Enjoying Agentic Store MCP?**
If you find these tools useful, please [star this repository on GitHub](https://github.com/agenticstore/agentic-store-mcp) to help other developers discover free, open-source MCP tools for their AI workflows!
