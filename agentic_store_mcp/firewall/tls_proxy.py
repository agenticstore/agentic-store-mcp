"""mitmproxy-based TLS-intercepting proxy with prompt sanitization addon."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from typing import Any

from mitmproxy import http, options
from mitmproxy.tools.dump import DumpMaster

from .audit import log_event
from .ca_manager import CONFDIR
from .rules import load_config
from .proxy import _sanitize
from .payloads import extract_prompt

_master: DumpMaster | None = None
_thread: threading.Thread | None = None


_ROUTE_BY_PATH: list[tuple[str, str, int]] = [
    ("/v1/messages", "api.anthropic.com", 443),
    ("/v1/responses", "api.openai.com", 443),
    ("/v1/chat/completions", "api.openai.com", 443),
    ("/v1beta", "generativelanguage.googleapis.com", 443),
    ("/openai/", "api.openai.com", 443),
    ("/google/", "generativelanguage.googleapis.com", 443),
]


class _PromptFirewallAddon:
    """mitmproxy addon — sanitizes AI API request bodies before forwarding.

    Handles two modes on the same port:
    - HTTPS CONNECT tunnels (system proxy mode, browsers)
    - Direct HTTP requests (ANTHROPIC_BASE_URL / OPENAI_BASE_URL mode, SDK clients)
    """

    _TARGET_HOSTS = (
        "api.anthropic.com",
        "api.openai.com",
        "generativelanguage.googleapis.com",
    )

    def _is_model_flow(self, flow: http.HTTPFlow) -> bool:
        host = flow.request.pretty_host
        return host in self._TARGET_HOSTS or (
            host == "chatgpt.com"
            and flow.request.path.split("?", 1)[0].startswith(
                "/backend-api/codex/responses"
            )
        )

    async def websocket_message(self, flow: http.HTTPFlow) -> None:
        """Inspect outgoing model frames; leave incoming responses untouched."""
        if not self._is_model_flow(flow) or not flow.websocket:
            return
        message = flow.websocket.messages[-1]
        if not message.from_client or not message.is_text:
            return
        try:
            body = json.loads(message.content)
        except (ValueError, UnicodeDecodeError):
            message.drop()
            log_event("blocked", "Invalid model WebSocket JSON", [], safe=False)
            return
        if not isinstance(body, dict):
            message.drop()
            return
        config = load_config()
        original = extract_prompt(body)
        sanitized, findings, safe = await _sanitize(body, config)
        blocked = config.get("mode", "redact") == "block" and (findings or not safe)
        if config.get("recording") and original:
            from .recorder import record_prompt

            response = body.get("response", body)
            record_prompt(
                provider=flow.request.pretty_host,
                model=response.get("model", "unknown"),
                prompt_text=original,
                redacted=bool(findings),
                findings_count=len(findings),
            )
        if blocked:
            message.drop()
            flow.kill()
            log_event("blocked", "Model WebSocket prompt blocked", findings, safe=False)
            return
        message.content = json.dumps(sanitized).encode()
        if original:
            log_event(
                "redacted" if findings else "clean",
                "Model WebSocket prompt forwarded",
                findings,
            )

    async def request(self, flow: http.HTTPFlow) -> None:
        # Direct HTTP mode: request arrived as plain HTTP to 127.0.0.1.
        # Rewrite host/port/scheme to the correct AI API upstream so mitmproxy
        # forwards it correctly, then fall through to sanitization.
        if flow.request.pretty_host in ("127.0.0.1", "localhost"):
            path = flow.request.path
            for prefix, host, port in _ROUTE_BY_PATH:
                if path.startswith(prefix):
                    # Strip synthetic prefix (/openai/, /google/) from path
                    if prefix in ("/openai/", "/google/"):
                        flow.request.path = path[len(prefix) - 1 :]
                    flow.request.host = host
                    flow.request.port = port
                    flow.request.scheme = "https"
                    break
            else:
                # Unknown path — let mitmproxy handle it as-is
                return

        if not self._is_model_flow(flow):
            return
        if not flow.request.content:
            return

        try:
            body: dict[str, Any] = json.loads(flow.request.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            flow.response = http.Response.make(400, b"Expected a JSON request object")
            return

        if not isinstance(body, dict):
            flow.response = http.Response.make(400, b"Expected a JSON request object")
            return

        config = load_config()
        original_text = extract_prompt(body)
        body, findings, safe = await _sanitize(body, config)

        mode = config.get("mode", "redact")
        if mode == "block" and (findings or not safe):
            flow.response = http.Response.make(
                400,
                json.dumps(
                    {
                        "error": "Prompt blocked by AgenticStore firewall",
                        "findings": len(findings),
                    }
                ),
                {"Content-Type": "application/json"},
            )
            log_event("blocked", "Prompt blocked by firewall", findings, safe=False)
            return

        flow.request.content = json.dumps(body).encode()
        if findings:
            log_event(
                "redacted",
                f"{len(findings)} finding(s) sanitized via system proxy",
                findings,
            )
        else:
            log_event("clean", f"Clean request forwarded to {flow.request.pretty_host}")

        if config.get("recording"):
            from .recorder import record_prompt

            record_prompt(
                provider=flow.request.pretty_host,
                model=body.get("model", "unknown"),
                prompt_text=original_text,
                redacted=bool(findings),
                findings_count=len(findings),
            )


def _run_master(
    opts: options.Options, ready: threading.Event, errors: list[Exception]
) -> None:
    """Run mitmproxy event loop in a dedicated thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        master = DumpMaster(
            opts, event_loop=loop, with_termlog=False, with_dumper=False
        )
        master.addons.add(_PromptFirewallAddon())
        global _master
        _master = master
        ready.set()
        loop.run_until_complete(master.run())
    except Exception as exc:
        errors.append(exc)
        ready.set()
    finally:
        # A dead listener must never leave macOS pointing at a closed port.
        try:
            from .system_proxy import remove_system_proxy

            remove_system_proxy(opts.listen_port)
        except Exception:
            pass
        # Cancel all pending tasks before closing the loop to avoid
        # "Task was destroyed but it is pending!" warnings from mitmproxy internals.
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass
        loop.close()


def start_tls_proxy(port: int = 8766) -> None:
    global _master, _thread
    if _thread and _thread.is_alive():
        return

    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"TLS proxy port {port} is occupied") from exc

    CONFDIR.mkdir(parents=True, exist_ok=True)

    opts = options.Options(
        listen_host="127.0.0.1",
        listen_port=port,
        confdir=str(CONFDIR),
        ssl_insecure=False,
    )
    ready = threading.Event()
    errors: list[Exception] = []
    _thread = threading.Thread(
        target=_run_master, args=(opts, ready, errors), daemon=True, name="mitmproxy"
    )
    _thread.start()
    if not ready.wait(timeout=5):
        raise RuntimeError("TLS proxy did not initialize")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if errors or not _thread.is_alive():
            raise RuntimeError(
                f"TLS proxy failed: {errors[0] if errors else 'listener stopped'}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    stop_tls_proxy()
    raise RuntimeError(f"TLS proxy did not bind to localhost:{port}")


def stop_tls_proxy() -> None:
    global _master, _thread
    master = _master
    thread = _thread
    _master = None
    _thread = None
    if master:
        try:
            master.shutdown()
        except Exception:
            pass
    if thread and thread.is_alive():
        thread.join(timeout=5)  # wait longer to ensure the socket is released


def is_tls_proxy_running() -> bool:
    return _thread is not None and _thread.is_alive()
