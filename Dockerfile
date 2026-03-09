# agentic-store-mcp — Docker image
#
# Runs the MCP server over stdio (the MCP protocol standard).
# MCP clients connect via:  docker run -i --rm agentic-store-mcp
#
# Build:
#   docker build -t agentic-store-mcp .
#
# Run (all tools):
#   docker run -i --rm agentic-store-mcp
#
# Run (specific modules):
#   docker run -i --rm agentic-store-mcp --modules code,data
#
# Run (with API keys):
#   docker run -i --rm -e BRAVE_SEARCH_API_KEY=your_key agentic-store-mcp

FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (no project itself yet, just deps)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source
COPY agentic_store_mcp/ ./agentic_store_mcp/
COPY server.py webapp.py ./

# Install the project itself
RUN uv sync --frozen --no-dev

# MCP stdio — no port needed
# Override with: docker run ... agentic-store-mcp webapp.py --host 0.0.0.0
ENTRYPOINT ["uv", "run", "server.py"]
