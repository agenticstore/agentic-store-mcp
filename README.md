# agentic-store-mcp

Give your AI agents superpowers — free, open-source MCP tools, self-hosted, no account required.

Works with **Claude Desktop**, **Cursor**, **Windsurf**, **VS Code**, and any MCP-compatible client.

---

## What's Included

| Module | Tool | Description | Requires |
|--------|------|-------------|----------|
| **AgenticCode** | `python_lint_checker` | Static analysis for Python — bugs, style, complexity | Nothing |
| **AgenticCode** | `repo_scanner` | Scan for leaked secrets, PII, and .gitignore gaps | Nothing |
| **AgenticCode** | `dependency_audit` | Check for outdated and vulnerable dependencies | Nothing |
| **AgenticData** | `agentic_web_crawl` | Fetch any URL — extract page text, SEO metadata, headings, links, images | Nothing |
| **AgenticData** | `agentic_web_search` | Search the web via self-hosted SearXNG; returns ranked results with title, URL, snippet | SearXNG running |

---

## Setup

Choose your preferred setup method. Both expose the same tools over the same MCP stdio protocol.

- **[Python](#python-setup)** — requires `uv` (recommended for developers)
- **[Docker](#docker-setup)** — requires Docker, no Python needed on the host

---

## Python Setup

### 1. Install `uv`

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Windows (winget)**
```powershell
winget install --id=astral-sh.uv -e
```

Verify:
```bash
uv --version
```

### 2. Run the server

**Option A — Run directly via `uvx` (no install, always latest)**

```bash
uvx --refresh agentic-store-mcp
```

> `--refresh` ensures `uvx` always pulls the latest published version on each run. Omit it if you want to reuse the cached version.

**Option B — Install globally**

```bash
pip install agentic-store-mcp
agentic-store-mcp
```

**Option C — Clone and run from source**

```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
uv sync
uv run server.py
```

### 3. Enable web search (optional)

`agentic_web_search` requires a running [SearXNG](https://github.com/searxng/searxng) instance — a free, self-hosted metasearch engine.

```bash
# Start SearXNG (Docker required)
docker compose up -d

# Run the MCP server with the SearXNG URL
SEARXNG_URL=http://localhost:8080 uvx --refresh agentic-store-mcp
```

### 4. Available flags

```bash
uvx --refresh agentic-store-mcp                              # all tools
uvx --refresh agentic-store-mcp --modules code               # AgenticCode only
uvx --refresh agentic-store-mcp --modules data               # AgenticData only
uvx --refresh agentic-store-mcp --modules code,data          # multiple modules
uvx --refresh agentic-store-mcp --tools agentic_web_search   # single tool
uvx --refresh agentic-store-mcp --list                       # list tools and exit
```

---

## Docker Setup

### 1. Pull the image *(recommended)*

```bash
docker pull agenticstore/agentic-store-mcp:latest
```

### 2. Verify

```bash
docker run --rm agenticstore/agentic-store-mcp:latest --list
```

### 3. Enable web search *(optional)*

Requires a running SearXNG instance. Clone the repo just for the `docker-compose.yml`, then start SearXNG:

```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
docker compose up -d
```

Run the MCP server connected to SearXNG:

```bash
docker run -i --rm \
  --network agentic-store-mcp_default \
  -e SEARXNG_URL=http://searxng:8080 \
  agenticstore/agentic-store-mcp:latest
```

### Update to latest *(optional)*

```bash
docker pull agenticstore/agentic-store-mcp:latest
```

### Build from source *(optional — for contributors or custom builds)*

```bash
git clone https://github.com/agenticstore/agentic-store-mcp
cd agentic-store-mcp
docker build -t agentic-store-mcp .
docker run --rm agentic-store-mcp --list
```

> Replace `agenticstore/agentic-store-mcp:latest` with `agentic-store-mcp` in any config below if using a local build.

---

## Connect to Your AI Client

Add AgenticStore to your MCP client's config file, then restart the client.

Each section shows **Python** and **Docker** variants. Docker configs use the remote image — if you built locally, replace `agenticstore/agentic-store-mcp:latest` with `agentic-store-mcp`.

---

### Claude Desktop

**Config location**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Python — all tools**
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

**Python — with web search** *(optional — `docker compose up -d` required)*
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

**Docker — web crawl only**
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

**Docker — with web search** *(optional — `docker compose up -d` required)*
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "agentic-store-mcp_default",
        "-e", "SEARXNG_URL=http://searxng:8080",
        "agenticstore/agentic-store-mcp:latest"
      ]
    }
  }
}
```

---

### Cursor

**Config location:** `~/.cursor/mcp.json`

**Python — all tools**
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

**Python — with web search** *(optional — `docker compose up -d` required)*
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

**Docker — with web search** *(optional — `docker compose up -d` required)*
```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network", "agentic-store-mcp_default",
        "-e", "SEARXNG_URL=http://searxng:8080",
        "agenticstore/agentic-store-mcp:latest"
      ]
    }
  }
}
```

---

### Windsurf

**Config location:** `~/.codeium/windsurf/mcp_config.json`

Same pattern as Cursor above.

---

### VS Code (MCP extension)

Same pattern as Cursor above.

---

## Programmatic Usage (Python)

```python
from agentic_store_mcp import start_server

start_server()                              # all tools
start_server(modules=["code"])              # AgenticCode only
start_server(modules=["code", "data"])      # multiple modules
start_server(tools=["agentic_web_search"])  # single tool
```

---

## Tool Reference

### `agentic_web_crawl`
Fetches a URL and returns structured page content and SEO signals: title, meta description, canonical URL, robots directives, Open Graph tags, Twitter Card tags, heading structure (h1–h6), word count, and internal/external link breakdown. Handles redirects and encoding detection automatically.

**No external dependencies or setup required.**

### `agentic_web_search`
Searches the web via a self-hosted [SearXNG](https://github.com/searxng/searxng) instance. Returns ranked results with title, URL, snippet, and source engine. Supports categories (general, news, images, science, it, etc.) and language filtering.

**Requires SearXNG:** `docker compose up -d`

### `python_lint_checker`
Static analysis for Python files. Checks imports, bugs, style, and complexity — zero external dependencies.

### `repo_scanner`
Scans a directory for leaked secrets (AWS keys, API tokens, private keys), PII (emails, SSNs), and missing `.gitignore` entries.

### `dependency_audit`
Audits `requirements.txt`, `pyproject.toml`, `package.json`, `go.mod`, `pom.xml`, and more. Checks for outdated versions and known CVEs via OSV.

---

## Contributing

- Tools must be **pure Python** — no managed services, no AgenticStore infrastructure
- Each tool lives in `agentic_store_mcp/modules/<category>/<tool_name>/` with `handler.py`, `schema.json`, `README.md`, and `test_handler.py`
- Run tests: `uv run pytest`

---

## License

MIT — free to use, fork, and modify.
