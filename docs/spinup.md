# Agentic Store development spinup

Prepared 2026-09-27 in `/Users/pavan/Documents/agentic-store-mcp`.

## Readiness

- Existing `.venv` loads the MCP, FastAPI, HTTPX, and mitmproxy runtime.
- The existing preparation task verified the stdio MCP handshake, discovery of 31 tools, and a read-only tool call.
- Dashboard routes and static assets passed in-process checks.
- The preparation task reports 375 tests passing with token storage redirected to a temporary directory and Keychain access disabled. Without isolation, one configuration test attempts to write to real token storage because its mock patches the wrong reference.
- Pytest is absent from `.venv`; the baseline used a cached runner without changing dependencies.
- No dashboard listener is running: local-port permission was not granted in the preparation task.
- Preserve existing edits to UI CSS, base template, lockfile, logo, and demo assets.

## Architecture and next work

Python MCP server discovers tools from module directories. FastAPI provides the local dashboard. `webapp/clients.py` declares client paths; `webapp/config_writer.py` writes JSON `mcpServers` entries. These are separate from provider credentials in `connectors.py` and firewall routing.

### GPT integration — pending

Determine the intended OpenAI client surface (Codex, ChatGPT, or an API application) before selecting its configuration and transport. Existing Claude-style JSON cannot be assumed to fit every client. Inspect client registry, config writer, dashboard client controls, and connector registry. Preserve unrelated client settings; verify tool discovery through the selected client.

### Prompt firewall architecture review — pending

Compare `firewall/proxy.py` and `firewall/tls_proxy.py`. Both extract text from `system` and `messages`; their sanitizer and block behavior differ. Review request schemas, routing, streaming, tool payloads, multimodal inputs, and error behavior against the chosen client.

The preparation task reports synthetic reproductions of two issues: multi-message redaction may report findings without changing the outgoing payload, and request bodies using `input` are not scanned. Treat these as unresolved until fixes have regression evidence.

## Development entry points

MCP: `.venv/bin/python server.py`.

Dashboard: `.venv/bin/python -m uvicorn agentic_store_mcp.webapp.app:app --host 127.0.0.1 --port 8875` after local-port permission. Inspect app startup behavior before launching. The convenience launcher frees its requested port by terminating existing listeners, so use direct uvicorn for shared development.

For subsequent substantive work, update the matching pending work item and its verification evidence. Run Python lint for each modified Python file, repository scanning after source changes, and dependency auditing after dependency changes, as required by the supplied project instructions.
