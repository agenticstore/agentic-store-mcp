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
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from starlette.routing import Route

from .audit import log_event
from .payloads import extract_prompt, map_prompt
from .rules import load_config
from .sanitizers.deterministic import sanitize as det_sanitize
from .sanitizers.llm_reviewer import is_ollama_running
from .sanitizers.llm_reviewer import review as llm_review

# Route by path prefix / content-type hints
_UPSTREAM_BY_PATH: list[tuple[str, str]] = [
    ("/v1/messages", "https://api.anthropic.com"),
    ("/v1/responses", "https://api.openai.com"),
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
        if path == prefix or path.startswith(prefix + "/"):
            # Strip synthetic prefix segments like /openai, /anthropic, /google
            if prefix in ("/openai", "/anthropic", "/google"):
                clean = path[len(prefix) :]
                return upstream, clean or "/"
            return upstream, path
    return _DEFAULT_UPSTREAM, path


def _extract_prompt_text(body: dict) -> str:
    return extract_prompt(body)


async def _sanitize(body: dict, config: dict) -> tuple[dict, list[dict], bool]:
    findings: list[dict] = []
    safe = True
    texts: list[str] = []

    def collect(text):
        texts.append(text)
        return text

    map_prompt(body, collect)
    replacements = []
    llm_cfg = config.get("llm", {})
    use_llm = bool(llm_cfg.get("enabled") and llm_cfg.get("model"))
    available = await is_ollama_running() if use_llm else False
    for text in texts:
        current, detected = det_sanitize(text, config)
        findings.extend(
            {"type": f.type, "original": f.original, "replacement": f.replacement}
            for f in detected
        )
        if use_llm:
            if not available:
                safe = False
            else:
                try:
                    result = await llm_review(
                        current, llm_cfg["model"], llm_cfg.get("custom_rules", [])
                    )
                    safe = safe and result.get("safe", True)
                    findings.extend(
                        {
                            "type": f.get("type", "llm"),
                            "original": f.get("original"),
                            "replacement": f.get("replacement", "[REDACTED]"),
                        }
                        for f in result.get("findings", [])
                    )
                    current = result.get("redacted_prompt", current)
                except Exception:
                    safe = False
                    log_event("llm_error", "Local reviewer unavailable")
        replacements.append(current)
    values = iter(replacements)
    return map_prompt(body, lambda _: next(values)), findings, safe


async def _proxy_handler(request: Request) -> Response:
    config = load_config()
    path = request.url.path
    upstream_base, clean_path = _resolve_upstream(path)

    raw_body = await request.body()
    fwd_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    body: dict[str, Any] = {}
    if raw_body:
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                {"error": "Expected a JSON request object"}, status_code=400
            )
        if not isinstance(body, dict):
            return JSONResponse(
                {"error": "Expected a JSON request object"}, status_code=400
            )

    sanitized_body, findings, safe = await _sanitize(body, config)

    mode = config.get("mode", "redact")
    if (findings or not safe) and mode == "block":
        log_event(
            "blocked",
            f"Prompt blocked — {len(findings)} finding(s)",
            findings,
            safe=False,
        )
        return JSONResponse(
            {
                "error": "Prompt blocked by AgenticStore firewall",
                "findings": [
                    {k: v for k, v in f.items() if k != "original"} for f in findings
                ],
            },
            status_code=400,
        )

    if findings:
        log_event(
            "redacted", f"{len(findings)} finding(s) sanitized", findings, safe=safe
        )
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

    client = httpx.AsyncClient(timeout=120.0, trust_env=False)
    try:
        upstream_resp = await client.send(
            client.build_request(
                method=request.method,
                url=upstream_url,
                headers=fwd_headers,
                content=json.dumps(sanitized_body).encode()
                if sanitized_body
                else raw_body,
            ),
            stream=True,
        )
    except httpx.HTTPError:
        log_event("upstream_error", "Upstream service unavailable", safe=False)
        await client.aclose()
        return JSONResponse({"error": "Upstream service unavailable"}, status_code=502)

    async def close():
        await upstream_resp.aclose()
        await client.aclose()

    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers={
            k: v
            for k, v in upstream_resp.headers.items()
            if k.lower() not in ("transfer-encoding", "connection")
        },
        background=BackgroundTask(close),
    )


_proxy_app = Starlette(
    routes=[
        Route(
            "/{path:path}",
            _proxy_handler,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )
    ]
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
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/openai/v1"


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
