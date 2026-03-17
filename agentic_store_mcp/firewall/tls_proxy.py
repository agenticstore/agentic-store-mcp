"""mitmproxy-based TLS-intercepting proxy with prompt sanitization addon."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from mitmproxy import http, options
from mitmproxy.tools.dump import DumpMaster

from .audit import log_event
from .ca_manager import CONFDIR
from .rules import load_config
from .sanitizers.deterministic import sanitize as det_sanitize

_master: DumpMaster | None = None
_thread: threading.Thread | None = None


_ROUTE_BY_PATH: list[tuple[str, str, int]] = [
    ("/v1/messages",       "api.anthropic.com",                    443),
    ("/v1/chat/completions", "api.openai.com",                     443),
    ("/v1beta",            "generativelanguage.googleapis.com",     443),
    ("/openai/",           "api.openai.com",                       443),
    ("/google/",           "generativelanguage.googleapis.com",    443),
]


class _PromptFirewallAddon:
    """mitmproxy addon — sanitizes AI API request bodies before forwarding.

    Handles two modes on the same port:
    - HTTPS CONNECT tunnels (system proxy mode, browsers)
    - Direct HTTP requests (ANTHROPIC_BASE_URL / OPENAI_BASE_URL mode, SDK clients)
    """

    _TARGET_HOSTS = ("api.anthropic.com", "api.openai.com", "generativelanguage.googleapis.com")

    def request(self, flow: http.HTTPFlow) -> None:
        # Direct HTTP mode: request arrived as plain HTTP to 127.0.0.1.
        # Rewrite host/port/scheme to the correct AI API upstream so mitmproxy
        # forwards it correctly, then fall through to sanitization.
        if flow.request.pretty_host in ("127.0.0.1", "localhost"):
            path = flow.request.path
            for prefix, host, port in _ROUTE_BY_PATH:
                if path.startswith(prefix):
                    # Strip synthetic prefix (/openai/, /google/) from path
                    if prefix in ("/openai/", "/google/"):
                        flow.request.path = path[len(prefix) - 1:]
                    flow.request.host = host
                    flow.request.port = port
                    flow.request.scheme = "https"
                    break
            else:
                # Unknown path — let mitmproxy handle it as-is
                return

        if flow.request.pretty_host not in self._TARGET_HOSTS:
            return
        if not flow.request.content:
            return

        try:
            body: dict[str, Any] = json.loads(flow.request.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        config = load_config()
        original_text = self._extract_text(body)
        redacted_text, findings = det_sanitize(original_text, config)

        if findings:
            body = self._apply_redactions(body, original_text, redacted_text)
            flow.request.content = json.dumps(body).encode()
            log_event(
                "redacted",
                f"{len(findings)} finding(s) sanitized via system proxy",
                [{"type": f.type, "original": f.original, "replacement": f.replacement} for f in findings],
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

        mode = config.get("mode", "redact")
        if mode == "block" and findings:
            flow.response = http.Response.make(
                400,
                json.dumps({"error": "Prompt blocked by AgenticStore firewall", "findings": len(findings)}),
                {"Content-Type": "application/json"},
            )

    @staticmethod
    def _extract_text(body: dict) -> str:
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

    @staticmethod
    def _apply_redactions(body: dict, original: str, redacted: str) -> dict:
        if original == redacted:
            return body
        raw = json.dumps(body)
        raw = raw.replace(json.dumps(original)[1:-1], json.dumps(redacted)[1:-1])
        return json.loads(raw)


def _run_master(master: DumpMaster) -> None:
    """Run mitmproxy event loop in a dedicated thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(master.run())
    except Exception:
        pass
    finally:
        # Cancel all pending tasks before closing the loop to avoid
        # "Task was destroyed but it is pending!" warnings from mitmproxy internals.
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()


def start_tls_proxy(port: int = 8766) -> None:
    global _master, _thread
    if _thread and _thread.is_alive():
        return

    CONFDIR.mkdir(parents=True, exist_ok=True)

    opts = options.Options(
        listen_host="127.0.0.1",
        listen_port=port,
        confdir=str(CONFDIR),
        ssl_insecure=False,
    )
    _master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    _master.addons.add(_PromptFirewallAddon())

    _thread = threading.Thread(target=_run_master, args=(_master,), daemon=True, name="mitmproxy")
    _thread.start()


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
