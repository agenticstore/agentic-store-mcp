"""Local prompt sanitizer proxy — intercepts AI API calls, sanitizes, then forwards."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .audit import log_event
from .rules import load_config
from .sanitizers.deterministic import sanitize as det_sanitize
from .sanitizers.llm_reviewer import is_ollama_running
from .sanitizers.llm_reviewer import review as llm_review

# Route by path prefix / content-type hints
_UPSTREAM_BY_PATH: list[tuple[str, str]] = [
    ("/v1/messages", "https://api.anthropic.com"),
    ("/v1/chat/completions", "https://api.openai.com"),
    ("/v1beta", "https://generativelanguage.googleapis.com"),
    ("/openai", "https://api.openai.com"),
    ("/anthropic", "https://api.anthropic.com"),
    ("/google", "https://generativelanguage.googleapis.com"),
]
_DEFAULT_UPSTREAM = "https://api.anthropic.com"

_server_instance: uvicorn.Server | None = None
_server_task: asyncio.Task | None = None  # type: ignore[type-arg]


def _resolve_upstream(path: str) -> tuple[str, str]:
    """Return (upstream_base, clean_path)."""
    for prefix, upstream in _UPSTREAM_BY_PATH:
        if path.startswith(prefix):
            # Strip synthetic prefix segments like /openai, /anthropic, /google
            if prefix in ("/openai", "/anthropic", "/google"):
                clean = path[len(prefix):]
                return upstream, clean or "/"
            return upstream, path
    return _DEFAULT_UPSTREAM, path


def _extract_prompt_text(body: dict) -> str:
    parts: list[str] = []
    if isinstance(body.get("system"), str):
        parts.append(body["system"])
    elif isinstance(body.get("system"), list):
        for block in body["system"]:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return "\n".join(parts)


def _apply_redactions(body: dict, original: str, redacted: str) -> dict:
    if original == redacted:
        return body
    raw = json.dumps(body)
    raw = raw.replace(json.dumps(original)[1:-1], json.dumps(redacted)[1:-1])
    return json.loads(raw)


async def _sanitize(body: dict, config: dict) -> tuple[dict, list[dict], bool]:
    findings: list[dict] = []
    safe = True

    original_text = _extract_prompt_text(body)
    current_text = original_text

    # Layer 1 — deterministic
    current_text, det_findings = det_sanitize(current_text, config)
    findings.extend(
        {"type": f.type, "original": f.original, "replacement": f.replacement}
        for f in det_findings
    )

    # Layer 2 — LLM reviewer (optional)
    llm_cfg = config.get("llm", {})
    if llm_cfg.get("enabled") and llm_cfg.get("model") and await is_ollama_running():
        try:
            result = await llm_review(current_text, llm_cfg["model"], llm_cfg.get("custom_rules", []))
            if not result.get("safe", True):
                safe = False
            findings.extend(result.get("findings", []))
            llm_redacted = result.get("redacted_prompt", current_text)
            if llm_redacted != current_text:
                current_text = llm_redacted
        except Exception as exc:
            log_event("llm_error", str(exc))

    if current_text != original_text:
        body = _apply_redactions(body, original_text, current_text)

    return body, findings, safe


async def _proxy_handler(request: Request) -> Response:
    config = load_config()
    path = request.url.path
    upstream_base, clean_path = _resolve_upstream(path)

    raw_body = await request.body()
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    body: dict[str, Any] = {}
    if raw_body:
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            pass

    sanitized_body, findings, safe = await _sanitize(body, config)

    mode = config.get("mode", "redact")
    if not safe and mode == "block":
        log_event("blocked", f"Prompt blocked — {len(findings)} finding(s)", findings, safe=False)
        return JSONResponse(
            {"error": "Prompt blocked by AgenticStore firewall", "findings": findings},
            status_code=400,
        )

    if findings:
        log_event("redacted", f"{len(findings)} finding(s) sanitized", findings, safe=safe)
    else:
        log_event("clean", "Prompt forwarded clean")

    if config.get("recording"):
        from .recorder import record_prompt
        record_prompt(
            provider=upstream_base,
            model=body.get("model", "unknown"),
            prompt_text=_extract_prompt_text(body),
            redacted=bool(findings),
            findings_count=len(findings),
        )

    upstream_url = upstream_base + clean_path
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        upstream_resp = await client.request(
            method=request.method,
            url=upstream_url,
            headers=fwd_headers,
            content=json.dumps(sanitized_body).encode() if sanitized_body else raw_body,
        )

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers={
            k: v for k, v in upstream_resp.headers.items()
            if k.lower() not in ("content-encoding", "transfer-encoding")
        },
    )


_proxy_app = Starlette(
    routes=[Route("/{path:path}", _proxy_handler, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])]
)


async def start_proxy(port: int = 8766) -> None:
    global _server_instance, _server_task
    if _server_task and not _server_task.done():
        return
    cfg = uvicorn.Config(_proxy_app, host="127.0.0.1", port=port, log_level="error")
    _server_instance = uvicorn.Server(cfg)

    async def _serve_guarded() -> None:
        try:
            await _server_instance.serve()
        except OSError as exc:
            raise RuntimeError(f"Proxy failed to bind port {port}: {exc}") from exc

    _server_task = asyncio.create_task(_serve_guarded())
    # Give the server a moment to bind — surface bind errors early
    await asyncio.sleep(0.3)
    if _server_task.done() and _server_task.exception():
        raise _server_task.exception()  # type: ignore[misc]

    os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{port}"
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/openai"


async def stop_proxy() -> None:
    global _server_instance, _server_task
    instance = _server_instance
    task = _server_task
    _server_instance = None
    _server_task = None

    if instance:
        instance.should_exit = True  # signal uvicorn's event loop to shut down cleanly

    if task and not task.done():
        try:
            # Wait for uvicorn to close the socket naturally (respects should_exit)
            await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        except (asyncio.CancelledError, Exception):
            pass

    # Brief pause to let the OS finish releasing the port
    await asyncio.sleep(0.3)

    os.environ.pop("ANTHROPIC_BASE_URL", None)
    os.environ.pop("OPENAI_BASE_URL", None)


def is_proxy_running() -> bool:
    return _server_task is not None and not _server_task.done()
