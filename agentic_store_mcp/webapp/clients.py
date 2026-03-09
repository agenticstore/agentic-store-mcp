"""
clients.py — MCP client definitions: config paths and launch commands.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Client:
    slug: str
    name: str
    config_path: Path
    launch_cmd: list[str] = field(default_factory=list)

    def launch_supported(self) -> bool:
        if not self.launch_cmd:
            return False
        binary = self.launch_cmd[-1] if self.launch_cmd[0] in ("open", "start") else self.launch_cmd[0]
        if self.launch_cmd[0] == "open":
            return sys.platform == "darwin"
        if self.launch_cmd[0] == "start":
            return sys.platform == "win32"
        return shutil.which(binary) is not None


def _home() -> Path:
    return Path.home()


def get_all_clients() -> list[Client]:
    platform = sys.platform

    if platform == "darwin":
        claude_config = _home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        claude_launch = ["open", "-a", "Claude"]
        cursor_launch = ["open", "-a", "Cursor"]
        antigravity_launch = ["open", "-a", "Antigravity"]
    elif platform == "win32":
        claude_config = _home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
        claude_launch = ["start", "", "Claude"]
        cursor_launch = ["start", "", "Cursor"]
        antigravity_launch = []  # not supported on Windows yet
    else:
        claude_config = _home() / ".config" / "Claude" / "claude_desktop_config.json"
        claude_launch = []  # no launch on Linux for Claude Desktop
        cursor_launch = ["cursor"] if shutil.which("cursor") else []
        antigravity_launch = ["antigravity"] if shutil.which("antigravity") else []

    cursor_config = _home() / ".cursor" / "mcp.json"
    antigravity_config = _home() / ".config" / "antigravity" / "mcp.json"

    return [
        Client(
            slug="claude-desktop",
            name="Claude Desktop",
            config_path=claude_config,
            launch_cmd=claude_launch,
        ),
        Client(
            slug="cursor",
            name="Cursor",
            config_path=cursor_config,
            launch_cmd=cursor_launch,
        ),
        Client(
            slug="antigravity",
            name="Antigravity",
            config_path=antigravity_config,
            launch_cmd=antigravity_launch,
        ),
    ]


def get_client(slug: str) -> Client | None:
    for c in get_all_clients():
        if c.slug == slug:
            return c
    return None


def launch_client(slug: str) -> dict:
    """Fire-and-forget launch. Returns {ok, error}."""
    c = get_client(slug)
    if not c:
        return {"ok": False, "error": f"Unknown client: {slug}"}
    if not c.launch_cmd:
        return {"ok": False, "error": f"Launch not supported for {c.name} on this platform"}
    if not c.launch_supported():
        return {"ok": False, "error": f"Launch binary not found for {c.name}"}
    try:
        subprocess.Popen(c.launch_cmd)  # noqa: S603
        return {"ok": True, "error": None}
    except OSError as e:
        return {"ok": False, "error": str(e)}
