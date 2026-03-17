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
    """SIGTERM any process holding the port so uvicorn can bind cleanly."""
    import subprocess
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True, text=True, timeout=3,
        )
        pids = [p.strip() for p in result.stdout.strip().splitlines() if p.strip().isdigit()]
        if pids:
            for pid in pids:
                subprocess.run(["kill", "-TERM", pid], capture_output=True)
            print(f"  Freed port {port} (killed PID(s): {', '.join(pids)})")
            time.sleep(0.6)  # let the OS release the socket
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="AgenticStore onboarding webapp")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser automatically")
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
