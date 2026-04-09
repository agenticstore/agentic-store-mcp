#!/usr/bin/env python3
"""
setup_local.py — one-time local setup for agentic-store-mcp.

Registers the MCP server and injects auto quality-gate rules into whichever
AI coding clients you have installed. Supports:

  • Claude Desktop  — MCP config + ~/.claude/CLAUDE.md
  • Cursor          — MCP config + ~/.cursor/rules/agentic-store.mdc
  • Windsurf        — MCP config + ~/.codeium/windsurf/memories/agentic-store.md
  • VS Code Copilot — .vscode/mcp.json + .github/copilot-instructions.md

Usage:
    uv run setup_local.py                   # auto-detect and install all found clients
    uv run setup_local.py --client cursor   # specific client only
    uv run setup_local.py --client claude,cursor,windsurf
    uv run setup_local.py --status          # show what's installed
    uv run setup_local.py --uninstall       # remove all patches
    uv run setup_local.py --uninstall --client cursor
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).parent.resolve()

# Idempotency markers (same for all clients — easy to grep for)
_BEGIN = "<!-- agentic-store-mcp:begin -->"
_END   = "<!-- agentic-store-mcp:end -->"
_MCP_KEY = "agentic-store-local"

# ─── Shared MCP server entry ──────────────────────────────────────────────────

def _mcp_entry() -> dict:
    import sys
    uv = shutil.which("uv")
    is_clone = (REPO_ROOT / "pyproject.toml").exists()
    server_py = REPO_ROOT / "server.py"

    if is_clone and server_py.exists() and uv:
        return {
            "command": uv,
            "args": ["run", "--directory", str(REPO_ROOT), "server.py"],
        }
    
    return {
        "command": sys.executable,
        "args": ["-m", "agentic_store_mcp.server"],
    }

# ─── Shared rules text ────────────────────────────────────────────────────────

def _rules_block() -> str:
    uv = shutil.which("uv") or "uv"
    return f"""\
{_BEGIN}
## AgenticStore Local Tools — Auto Quality Gates

MCP server: `{uv} run --directory {REPO_ROOT} server.py`

Run these tools automatically after code changes — do not ask for permission.

### After writing or modifying any Python file:
1. Call `python_lint_checker` on the changed file.
   - Fix all ERROR severity findings before the task is complete.
   - Surface WARNING findings to the user.

### After any code changes touch source files:
2. Call `repo_scanner` on the project root.
   - Fix leaked secrets immediately.
   - Report missing .gitignore entries.

### After adding or changing dependencies:
3. Call `dependency_audit` on the project root.
   - Block on vulnerable packages. Report outdated ones as a summary.

If `python_lint_checker` returns ERRORs, fix them before marking the task done.
{_END}"""

# ─── Generic helpers ──────────────────────────────────────────────────────────

def _patch_json_mcp(config_path: Path) -> str:
    """Add _MCP_KEY to an mcpServers JSON file. Creates if absent."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    cfg: dict = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "parse_error"
    if _MCP_KEY in cfg.get("mcpServers", {}):
        return "already_installed"
    cfg.setdefault("mcpServers", {})[_MCP_KEY] = _mcp_entry()
    config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return "installed"


def _unpatch_json_mcp(config_path: Path) -> str:
    if not config_path.exists():
        return "not_found"
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "not_found"
    if _MCP_KEY not in cfg.get("mcpServers", {}):
        return "not_found"
    del cfg["mcpServers"][_MCP_KEY]
    config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return "removed"


def _is_json_mcp_patched(config_path: Path) -> bool:
    if not config_path.exists():
        return False
    try:
        return _MCP_KEY in json.loads(config_path.read_text()).get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return False


def _patch_rules_file(rules_path: Path) -> str:
    """Append rules block to a markdown rules file. Creates if absent."""
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    existing = rules_path.read_text(encoding="utf-8") if rules_path.exists() else ""
    if _BEGIN in existing:
        return "already_installed"
    sep = "\n\n" if existing.strip() else ""
    rules_path.write_text(existing + sep + _rules_block() + "\n", encoding="utf-8")
    return "installed"


def _unpatch_rules_file(rules_path: Path) -> str:
    if not rules_path.exists():
        return "not_found"
    text = rules_path.read_text(encoding="utf-8")
    if _BEGIN not in text:
        return "not_found"
    start = text.find(_BEGIN)
    end   = text.find(_END, start)
    if end == -1:
        return "not_found"
    end += len(_END)
    patched = text[:start].rstrip() + text[end:].lstrip("\n")
    rules_path.write_text(patched, encoding="utf-8")
    return "removed"


def _is_rules_patched(rules_path: Path) -> bool:
    return rules_path.exists() and _BEGIN in rules_path.read_text(encoding="utf-8")


# ─── OS-aware config paths ────────────────────────────────────────────────────

def _os_config(mac: str, win: str, linux: str) -> Path:
    s = platform.system()
    if s == "Darwin":
        return Path(mac.replace("~", str(Path.home())))
    if s == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(win.replace("%APPDATA%", appdata))
    return Path(linux.replace("~", str(Path.home())))


# ─── Client definitions ───────────────────────────────────────────────────────
#
# Each client is a dict:
#   label       — display name
#   detect      — callable() -> bool: is this client installed?
#   steps       — list of (label, install_fn, uninstall_fn, status_fn)
#

def _clients() -> dict[str, dict]:
    home = Path.home()

    # ── Claude Desktop ─────────────────────────────────────────────────────────
    claude_cfg = _os_config(
        mac="~/Library/Application Support/Claude/claude_desktop_config.json",
        win="%APPDATA%/Claude/claude_desktop_config.json",
        linux="~/.config/Claude/claude_desktop_config.json",
    )
    claude_rules = home / ".claude" / "CLAUDE.md"

    # ── Cursor ─────────────────────────────────────────────────────────────────
    # Global MCP config: ~/.cursor/mcp.json
    # Global rules:      ~/.cursor/rules/agentic-store.mdc
    cursor_cfg   = home / ".cursor" / "mcp.json"
    cursor_rules = home / ".cursor" / "rules" / "agentic-store.mdc"

    # ── Windsurf ───────────────────────────────────────────────────────────────
    # Global MCP config: ~/.codeium/windsurf/mcp_config.json
    # Global memories:   ~/.codeium/windsurf/memories/agentic-store.md
    windsurf_cfg   = home / ".codeium" / "windsurf" / "mcp_config.json"
    windsurf_rules = home / ".codeium" / "windsurf" / "memories" / "agentic-store.md"

    # ── VS Code Copilot ────────────────────────────────────────────────────────
    # Project-level MCP:   .vscode/mcp.json  (relative to repo root)
    # Project-level rules: .github/copilot-instructions.md
    vscode_cfg   = REPO_ROOT / ".vscode" / "mcp.json"
    vscode_rules = REPO_ROOT / ".github" / "copilot-instructions.md"

    return {
        "claude": {
            "label": "Claude Desktop",
            "detect": lambda: claude_cfg.exists(),
            "steps": [
                (
                    "MCP server  (~/.../claude_desktop_config.json)",
                    lambda: _patch_json_mcp(claude_cfg),
                    lambda: _unpatch_json_mcp(claude_cfg),
                    lambda: _is_json_mcp_patched(claude_cfg),
                ),
                (
                    "Rules       (~/.claude/CLAUDE.md)",
                    lambda: _patch_rules_file(claude_rules),
                    lambda: _unpatch_rules_file(claude_rules),
                    lambda: _is_rules_patched(claude_rules),
                ),
            ],
            "restart_note": "Restart Claude Desktop (Cmd+Q then reopen).",
        },
        "cursor": {
            "label": "Cursor",
            "detect": lambda: (home / ".cursor").exists(),
            "steps": [
                (
                    "MCP server  (~/.cursor/mcp.json)",
                    lambda: _patch_json_mcp(cursor_cfg),
                    lambda: _unpatch_json_mcp(cursor_cfg),
                    lambda: _is_json_mcp_patched(cursor_cfg),
                ),
                (
                    "Rules       (~/.cursor/rules/agentic-store.mdc)",
                    lambda: _patch_rules_file(cursor_rules),
                    lambda: _unpatch_rules_file(cursor_rules),
                    lambda: _is_rules_patched(cursor_rules),
                ),
            ],
            "restart_note": "Reload Cursor window (Cmd+Shift+P → Reload Window).",
        },
        "windsurf": {
            "label": "Windsurf",
            "detect": lambda: (home / ".codeium" / "windsurf").exists(),
            "steps": [
                (
                    "MCP server  (~/.codeium/windsurf/mcp_config.json)",
                    lambda: _patch_json_mcp(windsurf_cfg),
                    lambda: _unpatch_json_mcp(windsurf_cfg),
                    lambda: _is_json_mcp_patched(windsurf_cfg),
                ),
                (
                    "Memories    (~/.codeium/windsurf/memories/agentic-store.md)",
                    lambda: _patch_rules_file(windsurf_rules),
                    lambda: _unpatch_rules_file(windsurf_rules),
                    lambda: _is_rules_patched(windsurf_rules),
                ),
            ],
            "restart_note": "Reload Windsurf window (Cmd+Shift+P → Reload Window).",
        },
        "vscode": {
            "label": "VS Code Copilot",
            "detect": lambda: shutil.which("code") is not None,
            "steps": [
                (
                    "MCP server  (.vscode/mcp.json)",
                    lambda: _patch_json_mcp(vscode_cfg),
                    lambda: _unpatch_json_mcp(vscode_cfg),
                    lambda: _is_json_mcp_patched(vscode_cfg),
                ),
                (
                    "Rules       (.github/copilot-instructions.md)",
                    lambda: _patch_rules_file(vscode_rules),
                    lambda: _unpatch_rules_file(vscode_rules),
                    lambda: _is_rules_patched(vscode_rules),
                ),
            ],
            "restart_note": "Reload VS Code window (Cmd+Shift+P → Reload Window).",
        },
    }


# ─── Display ──────────────────────────────────────────────────────────────────

def _report(label: str, result: str) -> None:
    icons = {
        "installed":         "  ✓",
        "already_installed": "  ↩",
        "removed":           "  ✓",
        "not_found":         "  –",
        "parse_error":       "  !",
    }
    messages = {
        "installed":         f"{label} — installed",
        "already_installed": f"{label} — already installed (skipped)",
        "removed":           f"{label} — removed",
        "not_found":         f"{label} — not found (skipped)",
        "parse_error":       f"{label} — could not parse config (skipped)",
    }
    print(f"{icons.get(result, '  ?')}  {messages.get(result, f'{label} — {result}')}")


def _print_status(selected: list[str]) -> None:
    clients = _clients()
    print("\nAgenticStore Local Setup — Status\n")
    for key in selected:
        c = clients[key]
        detected = c["detect"]()
        print(f"  [{c['label']}]{'  (not detected)' if not detected else ''}")
        for label, _, _, status_fn in c["steps"]:
            ok = status_fn()
            print(f"    {'✓' if ok else '✗'}  {label}")
        print()


# ─── Main ─────────────────────────────────────────────────────────────────────

ALL_CLIENTS = ["claude", "cursor", "windsurf", "vscode"]


def main() -> None:
    p = argparse.ArgumentParser(
        description="Set up agentic-store-mcp for local AI coding clients",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run setup_local.py                        auto-detect + install all
  uv run setup_local.py --client cursor        Cursor only
  uv run setup_local.py --client claude,cursor Claude + Cursor
  uv run setup_local.py --status               show what's installed
  uv run setup_local.py --uninstall            remove everything
        """,
    )
    p.add_argument(
        "--client", "-c",
        metavar="CLIENTS",
        help=f"Comma-separated clients: {', '.join(ALL_CLIENTS)}. Default: auto-detect.",
        default=None,
    )
    p.add_argument("--uninstall", action="store_true", help="Remove all patches")
    p.add_argument("--status",    action="store_true", help="Show installation status and exit")
    args = p.parse_args()

    clients = _clients()

    # Resolve which clients to act on
    if args.client:
        selected = [s.strip().lower() for s in args.client.split(",") if s.strip()]
        unknown = [s for s in selected if s not in clients]
        if unknown:
            print(f"Unknown client(s): {', '.join(unknown)}")
            print(f"Valid options: {', '.join(ALL_CLIENTS)}")
            raise SystemExit(1)
    else:
        # Auto-detect installed clients
        selected = [k for k, c in clients.items() if c["detect"]()]
        if not selected:
            print("\nNo supported AI clients detected.")
            print(f"Use --client to force: {', '.join(ALL_CLIENTS)}\n")
            return

    if args.status:
        _print_status(selected)
        return

    print()
    for key in selected:
        c = clients[key]
        print(f"  [{c['label']}]")
        any_installed = False
        for label, install_fn, uninstall_fn, _ in c["steps"]:
            result = uninstall_fn() if args.uninstall else install_fn()
            _report(label, result)
            if result == "installed":
                any_installed = True
        if any_installed and not args.uninstall:
            print(f"  → {c['restart_note']}")
        print()


if __name__ == "__main__":
    main()
