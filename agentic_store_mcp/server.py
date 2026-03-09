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

    start_server(modules=modules, tools=tools)


if __name__ == "__main__":
    main()
