"""Independent fail-safe for the macOS system proxy when the dashboard dies."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

from .system_proxy import SNAPSHOT_FILE, remove_system_proxy


def start_watchdog(port: int) -> None:
    """Launch a process which survives SIGKILL of the dashboard."""
    subprocess.Popen(
        [sys.executable, "-m", __name__, str(os.getpid()), str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _parent_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _listener_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def main() -> None:
    parent_pid, port = int(sys.argv[1]), int(sys.argv[2])
    failures = 0
    while True:
        if not SNAPSHOT_FILE.exists():
            return
        try:
            owner = json.loads(SNAPSHOT_FILE.read_text()).get("_owner_pid")
            if owner != parent_pid:
                return  # a new dashboard instance took ownership
        except (OSError, ValueError):
            failures += 1
        if not _parent_alive(parent_pid):
            break
        failures = 0 if _listener_alive(port) else failures + 1
        if failures >= 3:
            break
        time.sleep(1)
    # Retry on transient networksetup failures; never silently leave a dead route.
    while SNAPSHOT_FILE.exists():
        try:
            remove_system_proxy(port)
            return
        except (OSError, RuntimeError, ValueError):
            time.sleep(2)


if __name__ == "__main__":
    main()
