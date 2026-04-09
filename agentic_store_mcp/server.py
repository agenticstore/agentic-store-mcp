#!/usr/bin/env python3
"""
AgenticStore MCP Server

Auto-discovers tools from modules/ and serves them over MCP stdio.

Usage (clone mode):
    uv run server.py                          # serve all tools
    uv run server.py --modules code,data      # specific modules only
    uv run server.py --tools repo_scanner     # specific tools only
    uv run server.py --list                   # print available tools and exit

Usage (PyPI / uvx mode):
    uvx agentic-store-mcp
    uvx agentic-store-mcp --modules code
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Both clone mode and PyPI install: modules/ lives next to this file.
ROOT = Path(__file__).parent
MODULES_DIR = ROOT / "modules"
APP_NAME = "AgenticStore Tools"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AgenticStore MCP Server — serves tools from modules/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic-store-mcp                      serve all modules
  agentic-store-mcp --modules code       AgenticCode tools only
  agentic-store-mcp --modules code,data  AgenticCode + AgenticData
  agentic-store-mcp --tools agentic_web_search  single tool
  agentic-store-mcp --list               print tools and exit
        """,
    )
    p.add_argument(
        "--modules", "-m",
        metavar="SLUGS",
        help="Comma-separated module slugs to load. Example: code,data",
        default=None,
    )
    p.add_argument(
        "--tools", "-t",
        metavar="NAMES",
        help="Comma-separated tool names to load. Example: repo_scanner,agentic_web_search",
        default=None,
    )
    p.add_argument(
        "--list", "-l",
        action="store_true",
        help="Print available tools and exit (no server started)",
    )
    p.add_argument(
        "--install-claude",
        action="store_true",
        help=(
            "Register this MCP server in Claude Code (~/.claude/settings.json) "
            "and clear any stale proxy env vars so Claude connects directly to Anthropic."
        ),
    )
    p.add_argument(
        "--firewall-mode",
        action="store_true",
        help=(
            "Used together with --install-claude: instead of clearing the proxy URL, "
            "verify the AgenticStore firewall proxy is running and point Claude Code at it. "
            "The proxy must already be started via the webapp before using this flag."
        ),
    )
    p.add_argument(
        "--install-cursor",
        action="store_true",
        help="Install this MCP server into Cursor (configures ~/.cursor/mcp.json)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------

def _load_tools(
    modules_filter: set[str] | None = None,
    tools_filter: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Walk modules/ and load matching tools.

    Supports two directory depths (both backward-compatible):
      2-level: modules/{module}/{tool}/handler.py          (e.g. data/agentic_web_search)
      3-level: modules/{module}/{submodule}/{tool}/handler.py  (e.g. code/security/repo_scanner)

    Returns:
        { tool_name: { description, input_schema, run, module, submodule, connectors } }
    """
    tools: dict[str, dict[str, Any]] = {}

    if not MODULES_DIR.exists():
        _warn(f"modules/ directory not found at {MODULES_DIR}")
        return tools

    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("."):
            continue

        slug = module_dir.name
        if modules_filter and slug not in modules_filter:
            continue

        for child_dir in sorted(module_dir.iterdir()):
            if not child_dir.is_dir() or child_dir.name.startswith("."):
                continue

            if (child_dir / "handler.py").exists():
                # 2-level tool: modules/{module}/{tool}/
                _register_tool(tools, child_dir, slug, submodule=None, tools_filter=tools_filter)
            else:
                # 3-level: treat child_dir as a submodule, walk one level deeper
                for tool_dir in sorted(child_dir.iterdir()):
                    if not tool_dir.is_dir() or tool_dir.name.startswith("."):
                        continue
                    if (tool_dir / "handler.py").exists():
                        _register_tool(tools, tool_dir, slug, submodule=child_dir.name, tools_filter=tools_filter)

    return tools


def _register_tool(
    tools: dict[str, dict[str, Any]],
    tool_dir: Path,
    slug: str,
    submodule: str | None,
    tools_filter: set[str] | None,
) -> None:
    """Load and register a single tool from tool_dir into the tools dict."""
    schema_path = tool_dir / "schema.json"
    handler_path = tool_dir / "handler.py"

    if not schema_path.exists() or not handler_path.exists():
        return

    try:
        schema = json.loads(schema_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _warn(f"Skipping {tool_dir.name}: bad schema.json — {exc}")
        return

    tool_name: str = schema.get("name") or tool_dir.name
    if tools_filter and tool_name not in tools_filter:
        return

    mod_id = (
        f"agentic-store.{slug}.{submodule}.{tool_name}"
        if submodule
        else f"agentic-store.{slug}.{tool_name}"
    )
    spec = importlib.util.spec_from_file_location(mod_id, handler_path)
    if spec is None or spec.loader is None:
        _warn(f"Skipping {tool_name}: cannot create module spec")
        return

    handler_module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(handler_module)  # type: ignore[union-attr]
    except Exception as exc:
        _warn(f"Skipping {tool_name}: handler import failed — {exc}")
        return

    if not hasattr(handler_module, "run"):
        _warn(f"Skipping {tool_name}: handler.py has no run() function")
        return

    tools[tool_name] = {
        "description": schema.get("description", ""),
        "input_schema": schema.get(
            "inputSchema",
            {"type": "object", "properties": {}},
        ),
        "run": handler_module.run,
        "module": slug,
        "submodule": submodule,
        "connectors": schema.get("connectors", []),
    }


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

async def _serve(tools: dict[str, dict[str, Any]]) -> None:
    server = Server(APP_NAME)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=name,
                description=info["description"],
                inputSchema=info["input_schema"],
            )
            for name, info in tools.items()
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        if name not in tools:
            raise ValueError(f"Unknown tool: '{name}'")

        try:
            result = tools[name]["run"](arguments or {})
        except Exception as exc:
            result = {"result": None, "error": f"Tool raised an exception: {exc}"}

        return [
            types.TextContent(type="text", text=json.dumps(result, indent=2))
        ]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warn(msg: str) -> None:
    print(f"[warn]  {msg}", file=sys.stderr)


def _print_tools_table(tools: dict[str, dict[str, Any]]) -> None:
    if not tools:
        print("No tools found.")
        return

    # Group by module → submodule
    grouped: dict[str, dict[str, list[str]]] = {}
    for name, info in sorted(tools.items()):
        slug = info["module"]
        sub = info.get("submodule") or ""
        grouped.setdefault(slug, {}).setdefault(sub, []).append(name)

    print(f"\nAgenticStore Tools — {len(tools)} tool(s) available\n")
    for slug in sorted(grouped):
        print(f"  [{slug}]")
        for sub in sorted(grouped[slug]):
            if sub:
                print(f"    ({sub})")
                indent = "      "
            else:
                indent = "    "
            for name in sorted(grouped[slug][sub]):
                desc = tools[name]["description"].split("\n")[0]
                short = desc[:68] + "…" if len(desc) > 68 else desc
                connectors = tools[name].get("connectors", [])
                badge = f" [{','.join(connectors)}]" if connectors else ""
                print(f"{indent}{name:<28}{badge:<16} {short}")
    print()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_server(
    modules: list[str] | None = None,
    tools: list[str] | None = None,
) -> None:
    """
    Start the AgenticStore MCP server over stdio.

    This is the programmatic entry point — use it when embedding the server
    inside a Python script or when you want to avoid CLI argument parsing.

    Args:
        modules: Optional list of module slugs to load, e.g. ["code", "data"].
                 Loads all modules when omitted.
        tools:   Optional list of tool names to load, e.g. ["repo_scanner"].
                 Loads all tools within the selected modules when omitted.

    Example::

        from agentic_store_mcp import start_server

        # Serve every tool
        start_server()

        # Serve AgenticCode tools only
        start_server(modules=["code"])

        # Serve a single tool
        start_server(tools=["agentic_web_search"])

    The server runs until the MCP client disconnects (blocking call).
    """
    modules_filter: set[str] | None = {m.strip() for m in modules if m.strip()} if modules else None
    tools_filter: set[str] | None = {t.strip() for t in tools if t.strip()} if tools else None

    loaded = _load_tools(modules_filter, tools_filter)

    if not loaded:
        print(
            "[error] No tools loaded. "
            "Check the modules/tools arguments or verify the modules/ directory exists.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"[start] {len(loaded)} tool(s): {', '.join(sorted(loaded))}",
        file=sys.stderr,
    )
    asyncio.run(_serve(loaded))


# ---------------------------------------------------------------------------
# Installation Helpers
# ---------------------------------------------------------------------------

def _is_proxy_listening(port: int) -> bool:
    """Return True if something is accepting connections on 127.0.0.1:<port>."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _launchctl_unsetenv(key: str) -> None:
    import subprocess
    try:
        subprocess.run(["launchctl", "unsetenv", key], capture_output=True)
    except Exception:
        pass


def _launchctl_setenv(key: str, value: str) -> None:
    import subprocess
    try:
        subprocess.run(["launchctl", "setenv", key, value], capture_output=True)
    except Exception:
        pass


def _shell_profile_remove_firewall() -> None:
    """Strip the AgenticStore Firewall block from ~/.zshrc and ~/.bash_profile."""
    import re
    marker_start = "# >>> AgenticStore Firewall >>>"
    marker_end   = "# <<< AgenticStore Firewall <<<"
    for profile in [Path.home() / ".zshrc", Path.home() / ".bash_profile"]:
        try:
            if not profile.exists():
                continue
            text = profile.read_text(encoding="utf-8")
            if marker_start not in text:
                continue
            text = re.sub(
                rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}\n?",
                "",
                text,
                flags=re.DOTALL,
            )
            profile.write_text(text, encoding="utf-8")
        except Exception:
            pass


def _shell_profile_write_firewall(port: int, anthropic_url: str) -> None:
    """Write a health-checked proxy activation block to ~/.zshrc and ~/.bash_profile."""
    import re
    marker_start = "# >>> AgenticStore Firewall >>>"
    marker_end   = "# <<< AgenticStore Firewall <<<"
    block = (
        f"{marker_start}\n"
        f"# AgenticStore Firewall — only route through proxy when it's actually running\n"
        f"if nc -z 127.0.0.1 {port} 2>/dev/null; then\n"
        f'  export ANTHROPIC_BASE_URL="{anthropic_url}"\n'
        f"else\n"
        f"  unset ANTHROPIC_BASE_URL 2>/dev/null; true\n"
        f"fi\n"
        f"{marker_end}\n"
    )
    for profile in [Path.home() / ".zshrc", Path.home() / ".bash_profile"]:
        try:
            content = profile.read_text(encoding="utf-8") if profile.exists() else ""
            content = re.sub(
                rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}\n?",
                "",
                content,
                flags=re.DOTALL,
            )
            profile.write_text(content.rstrip("\n") + "\n" + block, encoding="utf-8")
        except Exception:
            pass


def _write_claude_settings(command: str, args: list[str]) -> Path:
    """Atomically write the MCP server entry into ~/.claude/settings.json."""
    import json
    import os
    import tempfile

    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    settings.setdefault("mcpServers", {})["agentic-store-mcp"] = {
        "command": command,
        "args": args,
    }

    payload = json.dumps(settings, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=settings_path.parent, suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, settings_path)
    return settings_path


def _install_to_claude(firewall_mode: bool = False) -> None:
    """Register this MCP server in Claude Code and configure the connection mode.

    Default (no --firewall-mode):
        • Writes MCP entry to ~/.claude/settings.json
        • Removes ANTHROPIC_BASE_URL from launchctl and shell profiles
          so Claude Code connects directly to api.anthropic.com

    --firewall-mode:
        • Same MCP registration
        • Verifies the AgenticStore proxy is running on its configured port
        • Sets ANTHROPIC_BASE_URL via launchctl (GUI apps) and shell profiles
          so Claude Code routes through the firewall
    """
    import shutil
    from agentic_store_mcp.firewall.ca_manager import CA_CERT_PEM

    # ── Resolve the server command ────────────────────────────────────────────
    is_clone = (ROOT.parent / "pyproject.toml").exists()
    uv = shutil.which("uv")
    binary = shutil.which("agentic-store-mcp")

    if is_clone and uv:
        command = uv
        args: list[str] = [
            "run", "--directory", str(ROOT.parent.absolute()),
            str(ROOT.parent / "server.py"),
        ]
    elif binary:
        command = binary
        args = []
    else:
        print(
            "[error] Could not find either the repo clone (pyproject.toml) or the "
            "agentic-store-mcp binary on PATH. Run 'pip install .' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Firewall pre-flight: check proxy BEFORE writing anything ──────────────
    proxy_port: int = 8766
    proxy_url: str = ""
    if firewall_mode:
        from agentic_store_mcp.firewall.rules import load_config
        proxy_port = load_config().get("port", 8766)
        proxy_url  = f"http://127.0.0.1:{proxy_port}"
        if not _is_proxy_listening(proxy_port):
            print(
                f"[error] Firewall proxy is NOT running on port {proxy_port}.\n"
                f"\n"
                f"  Start it first:\n"
                f"    agentic-store-webapp          # open the webapp\n"
                f"    → Firewall tab → Start Proxy\n"
                f"\n"
                f"  Then re-run:\n"
                f"    agentic-store-mcp --install-claude --firewall-mode\n",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── Write MCP config ──────────────────────────────────────────────────────
    try:
        settings_path = _write_claude_settings(command, args)
    except Exception as e:
        print(f"[error] Failed to write Claude Code settings: {e}", file=sys.stderr)
        sys.exit(1)

    print("[ok] agentic-store-mcp registered in Claude Code.")
    print(f"     Config:  {settings_path}")
    print(f"     Command: {command} {' '.join(args)}\n")

    # ── Connection mode ───────────────────────────────────────────────────────
    if not firewall_mode:
        # Direct mode: clear any stale proxy URL so Claude hits Anthropic directly.
        _launchctl_unsetenv("ANTHROPIC_BASE_URL")
        _launchctl_unsetenv("OPENAI_BASE_URL")
        _shell_profile_remove_firewall()
        print("[ok] Cleared proxy env vars — Claude Code will connect directly to api.anthropic.com.")
        print("     (launchctl unsetenv + shell profile block removed)\n")

        # Check if ANTHROPIC_BASE_URL is still live in the current process environment.
        # This happens when the firewall block was sourced in the current terminal session —
        # shell profile changes only take effect in NEW shells.
        import os as _os
        still_set = _os.environ.get("ANTHROPIC_BASE_URL", "")
        if still_set:
            print(f"[warn] ANTHROPIC_BASE_URL='{still_set}' is still active in this terminal.")
            print("       Run this to clear it for the current session:\n")
            print("         unset ANTHROPIC_BASE_URL\n")
            print("       Then restart Claude Code, or open a new terminal before running 'claude'.\n")
        else:
            print("  Restart Claude Code (or open a new terminal and run 'claude') to apply.\n")
    else:
        # Firewall mode: proxy is confirmed running (checked above before any writes).
        _launchctl_setenv("ANTHROPIC_BASE_URL", proxy_url)
        _shell_profile_write_firewall(proxy_port, proxy_url)

        print(f"[ok] Firewall proxy confirmed running on port {proxy_port}.")
        print(f"[ok] ANTHROPIC_BASE_URL={proxy_url} set via launchctl + shell profiles.")
        print("\n  NODE_EXTRA_CA_CERTS (for TLS interception, if CA is installed):")
        print(f"  export NODE_EXTRA_CA_CERTS=\"{CA_CERT_PEM}\"")
        print("  (Add to ~/.zshrc / ~/.bash_profile to make it permanent)\n")
        print("  Restart Claude Code (or open a new terminal and run 'claude') to apply.\n")


def _install_to_cursor() -> None:
    """Install this server into Cursor by editing ~/.cursor/mcp.json directly."""
    import shutil
    config_path = Path.home() / ".cursor" / "mcp.json"

    is_clone = (ROOT.parent / "pyproject.toml").exists()
    uv = shutil.which("uv")
    binary = shutil.which("agentic-store-mcp")

    if is_clone and uv:
        command = uv
        args: list[str] = [
            "run", "--directory", str(ROOT.parent.absolute()),
            str(ROOT.parent / "server.py"),
        ]
    elif binary:
        command = binary
        args = []
    else:
        command = "agentic-store-mcp"
        args = []

    if not config_path.parent.exists():
        print(f"[error] Cursor config directory not found: {config_path.parent}", file=sys.stderr)
        sys.exit(1)

    data: dict[str, Any] = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    data.setdefault("mcpServers", {})["agentic-store-mcp"] = {
        "command": command,
        "args": args,
    }

    try:
        config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("[ok] agentic-store-mcp registered in Cursor.")
        print(f"     Config:  {config_path}")
        print(f"     Command: {command} {' '.join(args)}")
        print("\n  Restart Cursor (Cmd+Shift+P → Reload Window) to pick up the server.\n")
    except Exception as e:
        print(f"[error] Failed to update Cursor config: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and delegate to start_server() (or --list)."""
    args = _parse_args()

    modules = [s.strip() for s in args.modules.split(",") if s.strip()] if args.modules else None
    tools   = [s.strip() for s in args.tools.split(",")   if s.strip()] if args.tools   else None

    if args.list:
        modules_filter = set(modules) if modules else None
        tools_filter   = set(tools)   if tools   else None
        _print_tools_table(_load_tools(modules_filter, tools_filter))
        return

    if getattr(args, "install_claude", False):
        _install_to_claude(firewall_mode=getattr(args, "firewall_mode", False))
        return

    if getattr(args, "firewall_mode", False):
        print("[error] --firewall-mode requires --install-claude.", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "install_cursor", False):
        _install_to_cursor()
        return

    start_server(modules=modules, tools=tools)


if __name__ == "__main__":
    main()
