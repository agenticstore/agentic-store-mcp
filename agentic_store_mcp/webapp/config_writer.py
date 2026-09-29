"""
config_writer.py — atomic write of MCP client configs.

Merges only the "agentic-store-mcp" key into existing config,
preserving all other mcpServers entries.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil
import subprocess
import tomllib
import re
from pathlib import Path


def _server_command() -> list[str]:
    """Return the command array for running the MCP server."""
    import shutil
    import sys

    # 1. Determine if we are in a development clone
    # webapp/config_writer.py -> webapp/ -> agentic_store_mcp/ -> root
    project_root = Path(__file__).parent.parent.parent
    is_clone = (project_root / "pyproject.toml").exists()
    server_py = project_root / "server.py"

    # 2. If in a clone, prefer uv run to ensure the right venv is used
    if is_clone and server_py.exists():
        uv = shutil.which("uv")
        if uv:
            return [uv, "run", "--directory", str(project_root), str(server_py)]
        return [sys.executable, str(server_py)]

    # 3. If installed as a package (pip install), use python -m
    # This is the most reliable way to ensure we use the same environment
    # that the webapp is currently running in.
    return [sys.executable, "-m", "agentic_store_mcp.server"]


def _build_mcp_entry(enabled_tools: list[str] | None) -> dict:
    """Build the mcpServers entry for agentic-store-mcp."""
    cmd = _server_command()
    args: list[str] = cmd[1:]  # everything after the executable

    if enabled_tools is not None and len(enabled_tools) > 0:
        # Check if all tools are enabled (no --tools filter needed)
        from agentic_store_mcp.webapp.discovery import _discover_raw

        all_names = {
            r["schema"].get("name") for r in _discover_raw() if r["schema"].get("name")
        }
        if set(enabled_tools) != all_names:
            args += ["--tools", ",".join(sorted(enabled_tools))]

    return {
        "command": cmd[0],
        "args": args,
    }


def _codex_sections(text: str) -> list[tuple[bool, str]]:
    """Split TOML into sections; final semantic checks guard unusual layouts."""
    sections: list[tuple[bool, str]] = []
    start = 0
    own = False
    for match in re.finditer(r"(?m)^\s*(\[[^\n]+\])[^\n]*$", text):
        try:
            table = tomllib.loads(match.group(1) + "\n")
        except ValueError:
            continue
        servers = table.get("mcp_servers", {})
        is_own = isinstance(servers, dict) and "agentic-store-mcp" in servers
        sections.append((own, text[start : match.start()]))
        start = match.start()
        own = is_own
    sections.append((own, text[start:]))
    return sections


def _codex_payload(config_path: Path, enabled_tools: list[str] | None) -> str:
    """Use Codex's TOML editor in a temporary home before atomic installation."""
    executable = shutil.which("codex")
    if executable is None:
        raise ValueError(
            "Install the Codex CLI to apply GPT / OpenAI Codex configuration."
        )
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    before = tomllib.loads(original)
    entry = _build_mcp_entry(enabled_tools)
    with tempfile.TemporaryDirectory(prefix="agentic-codex-") as scratch:
        target = Path(scratch) / "config.toml"
        target.write_text(original, encoding="utf-8")
        target.chmod(0o600)
        result = subprocess.run(
            [
                executable,
                "mcp",
                "add",
                "agentic-store-mcp",
                "--",
                entry["command"],
                *entry["args"],
            ],
            env={**os.environ, "CODEX_HOME": scratch},
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode:
            raise ValueError(
                "Codex could not update MCP configuration; check existing TOML settings."
            )
        payload = target.read_text(encoding="utf-8")
    generated = "".join(section for own, section in _codex_sections(payload) if own)
    retained = "".join(section for own, section in _codex_sections(original) if not own)
    payload = retained.rstrip("\n") + "\n\n" + generated
    after = tomllib.loads(payload)
    # Verify the CLI changed only our server entry.
    for data in (before, after):
        servers = data.get("mcp_servers", {})
        servers.pop("agentic-store-mcp", None)
        if not servers:
            data.pop("mcp_servers", None)
    if before != after:
        raise ValueError(
            "Codex changed unrelated settings; configuration was not written."
        )
    installed = (
        tomllib.loads(payload).get("mcp_servers", {}).get("agentic-store-mcp", {})
    )
    if (
        installed.get("command") != entry["command"]
        or installed.get("args", []) != entry["args"]
    ):
        raise ValueError(
            "Codex generated an unexpected server entry; configuration was not written."
        )
    return payload


def write_config(client_slug: str, enabled_tools: list[str] | None) -> dict:
    """
    Atomically write/update the MCP config for a client.

    Returns {ok: bool, path: str, error: str|None}
    """
    from agentic_store_mcp.webapp.clients import get_client

    client = get_client(client_slug)
    if not client:
        return {"ok": False, "path": None, "error": f"Unknown client: {client_slug}"}

    config_path = client.config_path

    if client_slug == "codex":
        try:
            payload = _codex_payload(config_path, enabled_tools)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "path": None, "error": str(exc)}
    else:
        # Read existing config (if any)
        existing: dict = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}

        # Merge: only touch our key
        mcp_servers = existing.get("mcpServers", {})
        mcp_servers["agentic-store-mcp"] = _build_mcp_entry(enabled_tools)
        existing["mcpServers"] = mcp_servers

        # Validate JSON before writing
        try:
            payload = json.dumps(existing, indent=2)
            json.loads(payload)  # sanity check
        except (TypeError, ValueError) as e:
            return {
                "ok": False,
                "path": None,
                "error": f"JSON serialization error: {e}",
            }

    # Atomic write: tmp → os.replace()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=config_path.parent,
            prefix=".mcp_tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path, config_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        return {"ok": False, "path": None, "error": str(e)}

    return {"ok": True, "path": str(config_path), "error": None}
