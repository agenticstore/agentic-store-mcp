"""
app.py — FastAPI application for the AgenticStore onboarding webapp.

Routes:
  GET  /                           → index.html (3 sections: Connectors, Tools, Clients)
  GET  /api/tools                  → tool catalog with connector badges + toggle state
  GET  /api/connectors             → all connectors with per-field token status
  POST /api/connectors/{slug}/test → {ok, detail}
  POST /api/token                  → {service, token} → set_token()
  GET  /api/token/{service}        → {service, has_token: bool}
  DELETE /api/token/{service}      → remove_token()
  GET  /api/clients                → list with config paths and launch_supported
  POST /api/apply                  → {client, enabled_tools} → write config
  POST /api/launch                 → {client} → subprocess launch
  GET  /api/memory/status          → {last_checkpoint, fact_count, log_size_kb}
"""
from __future__ import annotations

import asyncio as _asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator


def _is_docker() -> bool:
    """Detect if we're running inside a Docker container."""
    return Path("/.dockerenv").exists() or os.environ.get("container") == "docker"


# Holds the running event loop so the sleep-wake thread can schedule coroutines.
_event_loop: _asyncio.AbstractEventLoop | None = None


async def _auto_restore_proxy() -> None:
    """Restart the proxy and re-apply system proxy settings if they should be active.

    Called on app startup (handles reboot) and on wake (handles sleep/wake cycle).
    """
    if _is_docker():
        return
    try:
        from agentic_store_mcp.firewall.rules import load_config
        config = load_config()
        if not config.get("enabled"):
            return

        port = config.get("port", 8766)

        from agentic_store_mcp.firewall.ca_manager import is_ca_installed
        from agentic_store_mcp.firewall.system_proxy import is_system_proxy_set, set_system_proxy

        if is_ca_installed():
            from agentic_store_mcp.firewall.tls_proxy import is_tls_proxy_running, start_tls_proxy
            if not is_tls_proxy_running():
                start_tls_proxy(port)
                await _asyncio.sleep(1.0)  # let mitmproxy bind
        else:
            from agentic_store_mcp.firewall.proxy import is_proxy_running, start_proxy
            if not is_proxy_running() and _is_port_free(port):
                await start_proxy(port)

        if not is_system_proxy_set(port):
            set_system_proxy(port)
    except Exception:
        pass  # best-effort — never break app startup


def _setup_sleep_wake() -> None:
    """Register macOS IOKit sleep/wake callbacks (no-op on non-macOS / Docker)."""
    if _is_docker():
        return
    try:
        from agentic_store_mcp.firewall.system_proxy import watch_sleep_wake, remove_system_proxy

        def _on_sleep() -> None:
            try:
                remove_system_proxy()
            except Exception:
                pass

        def _on_wake() -> None:
            loop = _event_loop
            if loop is None or loop.is_closed():
                return
            _asyncio.run_coroutine_threadsafe(_auto_restore_proxy(), loop)

        watch_sleep_wake(_on_sleep, _on_wake)
    except Exception:
        pass  # best-effort — never break app startup


@asynccontextmanager
async def _lifespan(app: "FastAPI") -> AsyncIterator[None]:  # noqa: F821
    global _event_loop
    _event_loop = _asyncio.get_running_loop()
    await _auto_restore_proxy()
    _setup_sleep_wake()
    yield


from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

HERE = Path(__file__).parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"

app = FastAPI(title="AgenticStore Setup", docs_url=None, redoc_url=None, lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ─── Index ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/env")
async def api_env():
    """Runtime environment info for the frontend."""
    return {"is_docker": _is_docker()}


# ─── Tools ────────────────────────────────────────────────────────────────────

@app.get("/api/tools")
async def api_tools():
    from agentic_store_mcp.webapp.discovery import build_catalog
    tools = build_catalog()
    return {"tools": tools, "total": len(tools)}


# ─── Connectors ───────────────────────────────────────────────────────────────

@app.get("/api/connectors")
async def api_connectors():
    from agentic_store_mcp.connectors import all_connectors
    from agentic_store_mcp.secrets import get_token

    result = []
    for c in all_connectors():
        fields = []
        for f in c.fields:
            service_key = f"{c.slug}_{f.name}"
            fields.append({
                "name": f.name,
                "label": f.label,
                "description": f.description,
                "secret": f.secret,
                "required": f.required,
                "placeholder": f.placeholder,
                "env_var": f.env_var,
                "has_token": get_token(service_key) is not None,
            })
        result.append({
            "slug": c.slug,
            "name": c.name,
            "description": c.description,
            "docs_url": c.docs_url,
            "test_supported": c.test_supported,
            "fields": fields,
            "configured": all(
                get_token(f"{c.slug}_{fld.name}") is not None
                for fld in c.fields if fld.required
            ),
        })
    return {"connectors": result}


class TestConnectorRequest(BaseModel):
    pass  # no body needed — slug is in path


@app.post("/api/connectors/{slug}/test")
async def api_test_connector(slug: str):
    from agentic_store_mcp.connectors import REGISTRY
    from agentic_store_mcp.secrets import get_token

    c = REGISTRY.get(slug)
    if not c:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {slug}")
    if not c.test_supported:
        return {"ok": False, "detail": "Test not supported for this connector"}

    if slug == "github":
        return await _test_github(c)
    elif slug in ("openai", "anthropic", "linear"):
        service_key = f"{slug}_{c.fields[0].name}"
        has_token = get_token(service_key) is not None
        if not has_token:
            return {"ok": False, "detail": "No token configured"}
        return {"ok": True, "detail": "Token present (live API test not available in setup)"}
    return {"ok": False, "detail": "Test not implemented"}


def _github_token_source(service_key: str) -> tuple[str | None, str]:
    """Return (token, source_label) so tests can report where the token came from."""
    import os
    upper = service_key.upper()
    for env_var in (upper, f"{upper}_TOKEN", f"{upper}_KEY"):
        val = os.environ.get(env_var)
        if val:
            return val, f"env var {env_var}"

    try:
        import keyring
        val = keyring.get_password("agentic-store-mcp", service_key)
        if val:
            return val, "OS keyring"
    except Exception:
        pass

    from pathlib import Path
    import json
    tokens_file = Path.home() / ".config" / "agentic-store" / "tokens.json"
    try:
        data = json.loads(tokens_file.read_text(encoding="utf-8"))
        val = data.get(service_key)
        if val:
            return val, "config file (~/.config/agentic-store/tokens.json)"
    except (OSError, json.JSONDecodeError):
        pass

    return None, "not found"


async def _test_github(connector) -> dict:
    service_key = f"github_{connector.fields[0].name}"
    token, source = _github_token_source(service_key)

    if not token:
        return {"ok": False, "detail": "No token configured — enter one in the field above and click Save."}

    try:
        from github import Github, Auth
        g = Github(auth=Auth.Token(token))
        user = g.get_user()
        login = user.login
        return {"ok": True, "detail": f"Authenticated as {login}  (token source: {source})"}
    except ImportError:
        return {"ok": False, "detail": "PyGithub not installed. Run: uv sync"}
    except Exception as e:
        hint = ""
        if "401" in str(e):
            hint = f" — token source is '{source}'. If you have a GITHUB_TOKEN env var set, it overrides the webapp. Unset it or update it to your new token."
        return {"ok": False, "detail": str(e) + hint}


# ─── Token CRUD ───────────────────────────────────────────────────────────────

class SetTokenRequest(BaseModel):
    service: str
    token: str


@app.post("/api/token")
async def api_set_token(body: SetTokenRequest):
    from agentic_store_mcp.secrets import set_token
    if not body.service or not body.token:
        raise HTTPException(status_code=400, detail="service and token are required")
    set_token(body.service, body.token)
    return {"ok": True, "service": body.service}


@app.get("/api/token/{service}")
async def api_get_token(service: str):
    from agentic_store_mcp.secrets import get_token
    has = get_token(service) is not None
    return {"service": service, "has_token": has}


@app.delete("/api/token/{service}")
async def api_delete_token(service: str):
    from agentic_store_mcp.secrets import remove_token
    remove_token(service)
    return {"ok": True, "service": service}


# ─── Clients ──────────────────────────────────────────────────────────────────

@app.get("/api/clients")
async def api_clients():
    from agentic_store_mcp.webapp.clients import get_all_clients
    result = []
    for c in get_all_clients():
        result.append({
            "slug": c.slug,
            "name": c.name,
            "config_path": str(c.config_path),
            "launch_supported": c.launch_supported(),
            "config_exists": c.config_path.exists(),
        })
    return {"clients": result}


class ApplyRequest(BaseModel):
    client: str
    enabled_tools: list[str] | None = None


@app.post("/api/apply")
async def api_apply(body: ApplyRequest):
    from agentic_store_mcp.webapp.config_writer import write_config
    result = write_config(body.client, body.enabled_tools)
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


class LaunchRequest(BaseModel):
    client: str


@app.post("/api/launch")
async def api_launch(body: LaunchRequest):
    from agentic_store_mcp.webapp.clients import launch_client
    result = launch_client(body.client)
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


class RestartRequest(BaseModel):
    client: str
    sync_first: bool = False


@app.post("/api/restart")
async def api_restart(body: RestartRequest):
    from agentic_store_mcp.webapp.clients import restart_client
    result = restart_client(body.client, sync_first=body.sync_first)
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ─── Memory ───────────────────────────────────────────────────────────────────

@app.get("/api/memory/status")
async def api_memory_status():
    try:
        from agentic_store_mcp.memory_store import get_status
        return get_status()
    except ImportError:
        return {"available": False}


@app.get("/api/memory/facts")
async def api_memory_facts():
    from agentic_store_mcp.memory_store import list_facts
    facts = list_facts()
    return {"facts": facts, "total": len(facts)}


@app.get("/api/memory/strategy")
async def api_memory_strategy():
    from agentic_store_mcp.memory_store import read_strategy
    return {"content": read_strategy()}


class StrategyRequest(BaseModel):
    content: str


@app.post("/api/memory/strategy")
async def api_memory_strategy_write(body: StrategyRequest):
    from agentic_store_mcp.memory_store import write_strategy
    write_strategy(body.content)
    return {"ok": True}


@app.get("/api/memory/checkpoints")
async def api_memory_checkpoints():
    from agentic_store_mcp.memory_store import list_checkpoints
    checkpoints = list_checkpoints()
    return {"checkpoints": checkpoints, "total": len(checkpoints)}


class CheckpointRequest(BaseModel):
    task: str
    name: str | None = None
    decisions: list[str] = []
    next_steps: list[str] = []
    client: str = ""
    notes: str = ""


@app.post("/api/memory/checkpoint")
async def api_memory_checkpoint(body: CheckpointRequest):
    from agentic_store_mcp.memory_store import save_checkpoint
    try:
        name = save_checkpoint(body.name or None, {
            "task": body.task,
            "decisions": body.decisions,
            "next_steps": body.next_steps,
            "client": body.client,
            "context": {"notes": body.notes},
        })
        return {"ok": True, "name": name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class RestoreRequest(BaseModel):
    name: str


@app.post("/api/memory/restore")
async def api_memory_restore(body: RestoreRequest):
    from agentic_store_mcp.memory_store import load_checkpoint
    data = load_checkpoint(body.name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Checkpoint not found: {body.name!r}")
    return {"ok": True, "checkpoint": data}


@app.delete("/api/memory/checkpoint/{name}")
async def api_memory_delete_checkpoint(name: str):
    from agentic_store_mcp.memory_store import delete_checkpoint
    deleted = delete_checkpoint(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Checkpoint not found: {name!r}")
    return {"ok": True, "name": name}


@app.get("/api/memory/logs")
async def api_memory_logs(limit: int = 50):
    from agentic_store_mcp.memory_store import read_logs
    entries = read_logs(limit)
    return {"entries": entries, "total": len(entries)}


# ─── Firewall ─────────────────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse as _StreamingResponse  # noqa: E402
import json as _json  # noqa: E402


def _is_any_proxy_running() -> bool:
    from agentic_store_mcp.firewall.proxy import is_proxy_running
    from agentic_store_mcp.firewall.tls_proxy import is_tls_proxy_running
    return is_proxy_running() or is_tls_proxy_running()


def _is_port_free(port: int) -> bool:
    """Try to bind the port — the only accurate test of whether a server can use it."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _force_free_port(port: int) -> None:
    """SIGTERM any process still holding the port (best-effort, macOS/Linux)."""
    import subprocess
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True, text=True, timeout=3,
        )
        for pid_str in result.stdout.strip().splitlines():
            if pid_str.strip().isdigit():
                subprocess.run(["kill", "-TERM", pid_str.strip()], capture_output=True)
    except Exception:
        pass


@app.get("/api/firewall/status")
async def api_firewall_status():
    from agentic_store_mcp.firewall.rules import load_config
    from agentic_store_mcp.firewall.audit import read_logs
    from agentic_store_mcp.firewall.sanitizers.llm_reviewer import is_ollama_running
    from agentic_store_mcp.firewall.ca_manager import is_ca_installed

    config = load_config()
    logs = read_logs(limit=500)
    redacted_count = sum(1 for e in logs if e.get("event") == "redacted")
    blocked_count = sum(1 for e in logs if e.get("event") == "blocked")
    ollama_ok = await is_ollama_running()
    system_mode = is_ca_installed()

    return {
        "running": _is_any_proxy_running(),
        "system_mode": system_mode,
        "port": config.get("port", 8766),
        "requests_total": len(logs),
        "redacted_total": redacted_count,
        "blocked_total": blocked_count,
        "ollama_available": ollama_ok,
    }


@app.post("/api/firewall/start")
async def api_firewall_start():
    from agentic_store_mcp.firewall.proxy import start_proxy
    from agentic_store_mcp.firewall.tls_proxy import is_tls_proxy_running
    from agentic_store_mcp.firewall.ca_manager import is_ca_installed
    from agentic_store_mcp.firewall.rules import load_config, save_config

    config = load_config()
    port = config.get("port", 8766)

    # If our TLS proxy is already on this port, traffic is already being
    # intercepted — no need to start the simple proxy too.
    if is_tls_proxy_running():
        config["enabled"] = True
        save_config(config)
        return {"ok": True, "running": True, "system_mode": is_ca_installed()}

    if not _is_port_free(port):
        raise HTTPException(status_code=409, detail=f"Port {port} is already in use. Free it first or change the port.")

    config["enabled"] = True
    save_config(config)
    await start_proxy(port)

    from agentic_store_mcp.firewall.audit import log_event
    log_event("session_start", f"Firewall session started on port {port}")

    return {"ok": True, "running": _is_any_proxy_running(), "system_mode": is_ca_installed()}


@app.post("/api/firewall/stop")
async def api_firewall_stop():
    import asyncio as _asyncio
    from agentic_store_mcp.firewall.proxy import stop_proxy
    from agentic_store_mcp.firewall.tls_proxy import stop_tls_proxy
    from agentic_store_mcp.firewall.system_proxy import is_system_proxy_set, remove_system_proxy
    from agentic_store_mcp.firewall.rules import load_config, save_config

    config = load_config()
    port = config.get("port", 8766)
    config["enabled"] = False
    save_config(config)

    # Remove macOS system proxy settings FIRST so the OS stops routing traffic
    # to localhost:8766 before we kill the listener — prevents internet cutoff.
    if is_system_proxy_set(port):
        try:
            remove_system_proxy()
        except Exception:
            pass

    await stop_proxy()
    stop_tls_proxy()

    # Poll until the port is genuinely free (mitmproxy can be slow to release).
    # Force-kill any lingering process if it doesn't free within ~3 seconds.
    for attempt in range(6):
        if _is_port_free(port):
            break
        if attempt == 3:
            _force_free_port(port)
        await _asyncio.sleep(0.5)

    return {"ok": True, "running": False}


@app.get("/api/firewall/config")
async def api_firewall_config_get():
    from agentic_store_mcp.firewall.rules import load_config
    from agentic_store_mcp.firewall.sanitizers.llm_reviewer import PREDEFINED_SYSTEM_PROMPT
    config = load_config()
    return {**config, "predefined_prompt": PREDEFINED_SYSTEM_PROMPT}


class FirewallConfigRequest(BaseModel):
    deterministic: dict | None = None
    llm: dict | None = None
    mode: str | None = None
    port: int | None = None


@app.post("/api/firewall/config")
async def api_firewall_config_save(body: FirewallConfigRequest):
    from agentic_store_mcp.firewall.rules import load_config, save_config

    config = load_config()
    if body.deterministic is not None:
        config["deterministic"] = {**config["deterministic"], **body.deterministic}
    if body.llm is not None:
        config["llm"] = {**config["llm"], **body.llm}
    if body.mode is not None:
        config["mode"] = body.mode
    if body.port is not None:
        config["port"] = body.port
    save_config(config)
    return {"ok": True}


@app.get("/api/firewall/models")
async def api_firewall_models():
    from agentic_store_mcp.firewall.sanitizers.llm_reviewer import list_models, is_ollama_running
    if not await is_ollama_running():
        return {"available": False, "models": []}
    models = await list_models()
    return {"available": True, "models": models}


class PullModelRequest(BaseModel):
    model: str


@app.post("/api/firewall/models/pull")
async def api_firewall_models_pull(body: PullModelRequest):
    from agentic_store_mcp.firewall.sanitizers.llm_reviewer import pull_model

    async def _stream():
        try:
            async for chunk in pull_model(body.model):
                yield f"data: {_json.dumps(chunk)}\n\n"
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return _StreamingResponse(_stream(), media_type="text/event-stream")


@app.delete("/api/firewall/models/{model_name:path}")
async def api_firewall_models_delete(model_name: str):
    from agentic_store_mcp.firewall.sanitizers.llm_reviewer import delete_model
    await delete_model(model_name)
    return {"ok": True}


@app.get("/api/firewall/logs")
async def api_firewall_logs(limit: int = 100):
    from agentic_store_mcp.firewall.audit import read_logs
    entries = read_logs(limit)
    return {"entries": entries, "total": len(entries)}


@app.delete("/api/firewall/logs")
async def api_firewall_logs_clear():
    from agentic_store_mcp.firewall.audit import clear_logs
    clear_logs()
    return {"ok": True}


# ─── System Proxy (TLS MITM) ──────────────────────────────────────────────────

@app.get("/api/firewall/system/status")
async def api_system_proxy_status():
    from agentic_store_mcp.firewall.ca_manager import is_ca_installed
    from agentic_store_mcp.firewall.system_proxy import is_system_proxy_set
    from agentic_store_mcp.firewall.tls_proxy import is_tls_proxy_running
    from agentic_store_mcp.firewall.rules import load_config
    config = load_config()
    port = config.get("port", 8766)
    return {
        "ca_installed": is_ca_installed(),
        "proxy_configured": is_system_proxy_set(port),
        "tls_proxy_running": is_tls_proxy_running(),
        "fully_active": is_ca_installed() and is_system_proxy_set(port) and is_tls_proxy_running(),
        "port": port,
    }


@app.post("/api/firewall/system/install")
async def api_system_proxy_install():
    """SSE stream — runs full install sequence and emits step events."""
    from agentic_store_mcp.firewall.ca_manager import ensure_ca_generated, install_ca_to_keychain, is_ca_installed
    from agentic_store_mcp.firewall.system_proxy import set_system_proxy
    from agentic_store_mcp.firewall.tls_proxy import start_tls_proxy
    from agentic_store_mcp.firewall.rules import load_config

    async def _stream():
        def step(id: str, status: str, message: str, error: str = ""):
            import json
            return f"data: {json.dumps({'step': id, 'status': status, 'message': message, 'error': error})}\n\n"

        config = load_config()
        port = config.get("port", 8766)

        # Step 1 — Generate CA cert
        yield step("ca_generate", "running", "Generating local CA certificate…")
        try:
            ensure_ca_generated()
            yield step("ca_generate", "done", "CA certificate generated")
        except Exception as e:
            yield step("ca_generate", "error", "Failed to generate CA", str(e))
            return

        # Step 2 — Install to user login keychain (no admin required)
        if is_ca_installed():
            yield step("ca_install", "done", "CA already trusted in login keychain")
        else:
            yield step("ca_install", "running", "Trusting CA certificate in login keychain…")
            try:
                install_ca_to_keychain()
                yield step("ca_install", "done", "Certificate trusted in login keychain")
            except Exception as e:
                yield step("ca_install", "error", "Keychain install failed", str(e))
                return

        # Step 3 — Configure system proxy
        yield step("net_proxy", "running", "Configuring macOS network proxy settings…")
        try:
            services = set_system_proxy(port)
            yield step("net_proxy", "done", f"Proxy set on: {', '.join(services)}")
        except Exception as e:
            yield step("net_proxy", "error", "Network proxy config failed", str(e))
            return

        # Step 4 — Start TLS proxy
        yield step("tls_start", "running", "Starting TLS proxy…")
        try:
            start_tls_proxy(port)
            import asyncio
            await asyncio.sleep(1.5)  # allow mitmproxy to bind
            from agentic_store_mcp.firewall.audit import log_event as _log_evt
            _log_evt("session_start", f"System proxy session started on port {port}")
            yield step("tls_start", "done", f"TLS proxy running on localhost:{port}")
        except Exception as e:
            yield step("tls_start", "error", "TLS proxy failed to start", str(e))
            return

        yield step("complete", "done", "System proxy is active — all AI traffic is now sanitized")

    return _StreamingResponse(_stream(), media_type="text/event-stream")


@app.post("/api/firewall/system/uninstall")
async def api_system_proxy_uninstall():
    """SSE stream — removes system proxy cleanly."""
    from agentic_store_mcp.firewall.ca_manager import remove_ca_from_keychain
    from agentic_store_mcp.firewall.system_proxy import remove_system_proxy
    from agentic_store_mcp.firewall.tls_proxy import stop_tls_proxy

    async def _stream():
        import json

        def step(id: str, status: str, message: str, error: str = ""):
            return f"data: {json.dumps({'step': id, 'status': status, 'message': message, 'error': error})}\n\n"

        yield step("tls_stop", "running", "Stopping TLS proxy…")
        try:
            stop_tls_proxy()
            yield step("tls_stop", "done", "TLS proxy stopped")
        except Exception as e:
            yield step("tls_stop", "error", "Could not stop proxy", str(e))

        yield step("net_proxy", "running", "Removing system proxy settings…")
        try:
            remove_system_proxy()
            yield step("net_proxy", "done", "System proxy settings removed")
        except Exception as e:
            yield step("net_proxy", "error", "Could not remove proxy settings", str(e))

        yield step("ca_remove", "running", "Removing CA from System Keychain — password dialog may appear…")
        try:
            remove_ca_from_keychain()
            yield step("ca_remove", "done", "CA certificate removed from System Keychain")
        except Exception as e:
            yield step("ca_remove", "error", "Could not remove CA cert", str(e))

        yield step("complete", "done", "System proxy fully uninstalled")

    return _StreamingResponse(_stream(), media_type="text/event-stream")


class SanitizeTestRequest(BaseModel):
    text: str


@app.post("/api/firewall/test/sanitize")
async def api_firewall_test_sanitize(body: SanitizeTestRequest):  # noqa: E402
    """Run text through the full sanitization pipeline and return findings."""
    from agentic_store_mcp.firewall.rules import load_config
    from agentic_store_mcp.firewall.sanitizers.deterministic import sanitize as det_sanitize
    from agentic_store_mcp.firewall.sanitizers.llm_reviewer import is_ollama_running, review as llm_review

    config = load_config()
    text = body.text
    findings: list[dict] = []

    redacted, det_findings = det_sanitize(text, config)
    findings.extend(
        {"layer": "deterministic", "type": f.type, "original": f.original, "replacement": f.replacement}
        for f in det_findings
    )

    llm_cfg = config.get("llm", {})
    llm_result = None
    if llm_cfg.get("enabled") and llm_cfg.get("model") and await is_ollama_running():
        try:
            llm_result = await llm_review(redacted, llm_cfg["model"], llm_cfg.get("custom_rules", []))
            for f in llm_result.get("findings", []):
                findings.append({"layer": "llm", **f})
        except Exception as e:
            llm_result = {"error": str(e)}

    return {
        "original": body.text,
        "redacted": llm_result.get("redacted_prompt", redacted) if llm_result and "redacted_prompt" in llm_result else redacted,
        "findings": findings,
        "safe": llm_result.get("safe", True) if llm_result else True,
        "llm_used": llm_result is not None and "error" not in llm_result,
    }


@app.get("/api/firewall/test")
async def api_firewall_test():
    """Make a live HTTPS request through the proxy — result appears in audit log."""
    import httpx
    from agentic_store_mcp.firewall.ca_manager import CA_CERT_PEM
    from agentic_store_mcp.firewall.tls_proxy import is_tls_proxy_running
    from agentic_store_mcp.firewall.rules import load_config

    config = load_config()
    port = config.get("port", 8766)

    if not is_tls_proxy_running():
        return {"ok": False, "error": "TLS proxy is not running. Install & start the system proxy first."}

    if not CA_CERT_PEM.exists():
        return {"ok": False, "error": "CA certificate not found."}

    try:
        async with httpx.AsyncClient(
            proxy=f"http://127.0.0.1:{port}",
            verify=str(CA_CERT_PEM),
            timeout=10.0,
        ) as client:
            resp = await client.get("https://httpbin.org/get")
            return {
                "ok": True,
                "status": resp.status_code,
                "message": "Request intercepted — check the Audit Log tab for the entry.",
                "proxied_via": f"127.0.0.1:{port}",
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Client connect / disconnect ──────────────────────────────────────────────

class ClientConnectRequest(BaseModel):
    client: str  # "claude_code" | "cursor" | "openai_sdk"


def _shell_profile_write(vars: list[tuple[str, str]]) -> None:
    """Write ANTHROPIC_BASE_URL / OPENAI_BASE_URL to ~/.zshrc and ~/.bash_profile
    so every new terminal session automatically routes traffic through the firewall."""
    import re
    from pathlib import Path

    home = Path.home()
    profiles = [home / ".zshrc", home / ".bash_profile"]
    marker_start = "# >>> AgenticStore Firewall >>>"
    marker_end = "# <<< AgenticStore Firewall <<<"

    lines = [marker_start]
    for key, value in vars:
        lines.append(f'export {key}="{value}"')
    lines.append(marker_end)
    block = "\n".join(lines) + "\n"

    for profile in profiles:
        try:
            content = profile.read_text(encoding="utf-8") if profile.exists() else ""
            # Remove any existing block
            content = re.sub(
                rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}\n?",
                "",
                content,
                flags=re.DOTALL,
            )
            profile.write_text(content.rstrip("\n") + "\n" + block, encoding="utf-8")
        except Exception:
            pass  # best-effort


def _shell_profile_remove(keys: list[str]) -> None:
    """Remove the AgenticStore Firewall block from shell profiles."""
    import re
    from pathlib import Path

    home = Path.home()
    profiles = [home / ".zshrc", home / ".bash_profile"]
    marker_start = "# >>> AgenticStore Firewall >>>"
    marker_end = "# <<< AgenticStore Firewall <<<"

    for profile in profiles:
        try:
            if not profile.exists():
                continue
            content = profile.read_text(encoding="utf-8")
            content = re.sub(
                rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}\n?",
                "",
                content,
                flags=re.DOTALL,
            )
            profile.write_text(content, encoding="utf-8")
        except Exception:
            pass  # best-effort


@app.post("/api/firewall/client/connect")
async def api_client_connect(body: ClientConnectRequest):  # noqa: E402
    """Inject proxy URL at three levels:
    1. macOS launchctl — GUI apps launched from Dock/Finder (current session).
    2. ~/.zshrc + ~/.bash_profile — every new terminal session automatically.
    No manual `export` command needed after this.
    """
    import subprocess
    from agentic_store_mcp.firewall.rules import load_config
    config = load_config()
    port = config.get("port", 8766)
    base = f"http://127.0.0.1:{port}"

    cmds: list[tuple[str, str]] = []
    if body.client in ("claude_code", "openai_sdk"):
        cmds.append(("ANTHROPIC_BASE_URL", base))
    if body.client in ("cursor", "openai_sdk"):
        cmds.append(("OPENAI_BASE_URL", f"{base}/openai"))

    # 1. launchctl — GUI apps (Dock/Finder)
    errors = []
    for key, value in cmds:
        r = subprocess.run(
            ["launchctl", "setenv", key, value],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            errors.append(f"{key}: {r.stderr.strip()}")

    # 2. Shell profiles — new terminal sessions
    _shell_profile_write(cmds)

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))
    return {"ok": True, "vars": {k: v for k, v in cmds}}


@app.post("/api/firewall/client/disconnect")
async def api_client_disconnect(body: ClientConnectRequest):  # noqa: E402
    """Remove injected env vars from launchctl and shell profiles."""
    import subprocess
    keys: list[str] = []
    if body.client in ("claude_code", "openai_sdk"):
        keys.append("ANTHROPIC_BASE_URL")
    if body.client in ("cursor", "openai_sdk"):
        keys.append("OPENAI_BASE_URL")

    # 1. launchctl — GUI apps
    errors = []
    for key in keys:
        r = subprocess.run(
            ["launchctl", "unsetenv", key],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            errors.append(f"{key}: {r.stderr.strip()}")

    # 2. Shell profiles — remove block
    _shell_profile_remove(keys)

    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))
    return {"ok": True, "removed": keys}


@app.get("/api/firewall/client/status")
async def api_client_status():  # noqa: E402
    """Return which clients currently have the env vars injected."""
    import subprocess
    def _get(key: str) -> str | None:
        r = subprocess.run(
            ["launchctl", "getenv", key],
            capture_output=True, text=True,
        )
        v = r.stdout.strip()
        return v if v else None

    return {
        "ANTHROPIC_BASE_URL": _get("ANTHROPIC_BASE_URL"),
        "OPENAI_BASE_URL": _get("OPENAI_BASE_URL"),
    }


# ─── Recordings ───────────────────────────────────────────────────────────────

class RecordingToggleRequest(BaseModel):
    enabled: bool


@app.post("/api/firewall/recording/toggle")
async def api_recording_toggle(body: RecordingToggleRequest):
    from agentic_store_mcp.firewall.rules import load_config, save_config
    config = load_config()
    config["recording"] = body.enabled
    save_config(config)
    return {"ok": True, "recording": body.enabled}


@app.get("/api/firewall/recordings")
async def api_recordings(limit: int = 50):
    from agentic_store_mcp.firewall.recorder import read_recordings, recordings_size_kb
    entries = read_recordings(limit)
    return {"entries": entries, "total": len(entries), "size_kb": recordings_size_kb()}


@app.delete("/api/firewall/recordings")
async def api_recordings_clear():
    from agentic_store_mcp.firewall.recorder import clear_recordings
    clear_recordings()
    return {"ok": True}


@app.get("/api/firewall/recordings/{index}")
async def api_recording_detail(index: int, limit: int = 50):
    from agentic_store_mcp.firewall.recorder import read_recordings
    entries = read_recordings(limit)
    if index < 0 or index >= len(entries):
        raise HTTPException(status_code=404, detail="Recording not found")
    return entries[index]
