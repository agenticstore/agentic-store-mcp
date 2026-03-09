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

import os
from pathlib import Path


def _is_docker() -> bool:
    """Detect if we're running inside a Docker container."""
    return Path("/.dockerenv").exists() or os.environ.get("container") == "docker"

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

HERE = Path(__file__).parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"

app = FastAPI(title="AgenticStore Setup", docs_url=None, redoc_url=None)
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
async def api_memory_logs(limit: int = 30):
    from agentic_store_mcp.memory_store import read_logs
    entries = read_logs(limit)
    return {"entries": entries, "total": len(entries)}
