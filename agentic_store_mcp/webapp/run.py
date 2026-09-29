"""
Entry point for the `agentic-store-webapp` console script.

Identical to running `uv run webapp.py` from the repo root.
"""

from __future__ import annotations

import argparse
import threading
import time
import webbrowser


def _free_port(port: int) -> None:
    """Fail visibly instead of killing an unrelated server on this port."""
    import socket

    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise SystemExit(f"Port {port} is occupied; stop its owner first") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="AgenticStore onboarding webapp")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument(
        "--no-open", action="store_true", help="Don't open browser automatically"
    )
    args = parser.parse_args()

    _free_port(args.port)

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
