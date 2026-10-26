"""
Entry point for the `agentic-store-webapp` console script.

Identical to running `uv run webapp.py` from the repo root.
"""

import argparse
import json
import socket
import threading
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen


def _port_available(host: str, port: int) -> bool:
    """Return whether this process can safely bind the requested dashboard port."""
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _find_available_port(host: str) -> int:
    """Ask the OS for a loopback port for an explicitly separate UI instance."""
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _relay_session_url(host: str, port: int) -> str | None:
    """Identify an existing Relay instance without assuming every listener is Relay."""
    url = f"http://{host}:{port}"
    try:
        with urlopen(f"{url}/api/control/board", timeout=0.4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None
    return url if isinstance(payload, dict) and "summary" in payload else None


def _select_port(host: str, port: int, auto_port: bool) -> int:
    """Choose a safe dashboard port or explain how to reuse an existing Relay."""
    if _port_available(host, port):
        return port
    if auto_port:
        return _find_available_port(host)
    existing = _relay_session_url(host, port)
    if existing:
        raise SystemExit(
            f"Relay is already running at {existing}. Reuse that shared UI, or use "
            "--auto-port to start a separate UI instance."
        )
    raise SystemExit(
        f"Port {port} is occupied by another process; no process was stopped. "
        "Use --auto-port for a separate UI instance."
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="AgenticStore onboarding webapp")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help="Use an OS-selected free port when --port is occupied",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't open browser automatically"
    )
    args = parser.parse_args()

    args.port = _select_port(args.host, args.port, args.auto_port)

    url = f"http://{args.host}:{args.port}"
    print(f"\n  AgenticStore Setup  →  {url}\n")

    if not args.no_open:

        def _open():
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    import uvicorn

    from agentic_store_mcp.webapp.app import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
