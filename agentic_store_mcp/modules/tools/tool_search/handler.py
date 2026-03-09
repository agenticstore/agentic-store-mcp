"""
tool_search — discover and filter available MCP tools at runtime.

Walks the modules/ directory (same 2-or-3-level logic as server.py),
reads every schema.json, and returns a filtered, tagged catalog.

Tag derivation (from schema content):
  api_required  — schema["connectors"] is non-empty
  local_only    — connectors empty AND description contains "local" or "directory"
  write_tool    — schema has a "confirmed" param OR description has write-action keywords
  read_only     — default (not write_tool)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# modules/ is three levels up from this file:
#   tool_search/ → tools/ → modules/
MODULES_DIR = Path(__file__).parent.parent.parent

WRITE_KEYWORDS = re.compile(
    r"\b(create|update|manage|write|open|push|commit|edit|delete|close|label|triage)\b",
    re.IGNORECASE,
)


def _infer_tags(schema: dict) -> list[str]:
    """Derive capability tags from a tool's schema.json."""
    tags = []
    connectors = schema.get("connectors", [])
    description = schema.get("description", "")

    # Properties dict for checking param names
    props = schema.get("inputSchema", {}).get("properties", {})

    if connectors:
        tags.append("api_required")
    elif re.search(r"\b(local|directory)\b", description, re.IGNORECASE):
        tags.append("local_only")

    if "confirmed" in props or WRITE_KEYWORDS.search(description):
        tags.append("write_tool")
    else:
        tags.append("read_only")

    return tags


def _discover_tools() -> list[dict]:
    """Walk modules/ and return a list of tool descriptor dicts."""
    tools = []

    if not MODULES_DIR.exists():
        return tools

    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("."):
            continue
        slug = module_dir.name

        for child_dir in sorted(module_dir.iterdir()):
            if not child_dir.is_dir() or child_dir.name.startswith("."):
                continue

            if (child_dir / "handler.py").exists():
                # 2-level tool
                _add_tool(tools, child_dir, slug, submodule=None)
            else:
                # 3-level: submodule
                for tool_dir in sorted(child_dir.iterdir()):
                    if tool_dir.is_dir() and (tool_dir / "handler.py").exists():
                        _add_tool(tools, tool_dir, slug, submodule=child_dir.name)

    return tools


def _add_tool(tools: list, tool_dir: Path, module: str, submodule: str | None) -> None:
    schema_path = tool_dir / "schema.json"
    if not schema_path.exists():
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    name = schema.get("name") or tool_dir.name
    description = schema.get("description", "")
    connectors = schema.get("connectors", [])
    tags = _infer_tags(schema)

    tools.append({
        "name": name,
        "module": module,
        "submodule": submodule,
        "description": description,
        "connectors": connectors,
        "tags": tags,
    })


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for tool_search.

    Params:
        query   Keyword to match against name + description (case-insensitive). Optional.
        tags    Comma-separated tag filters: api_required, local_only, write_tool, read_only. Optional.
        module  Filter by top-level module: code, data, tools, memory. Optional.
    """
    query = (params.get("query") or "").strip().lower()
    tags_param = (params.get("tags") or "").strip().lower()
    module_filter = (params.get("module") or "").strip().lower()

    # Parse tag filters
    valid_tags = {"api_required", "local_only", "write_tool", "read_only"}
    requested_tags: set[str] = set()
    if tags_param:
        for t in tags_param.split(","):
            t = t.strip()
            if t in valid_tags:
                requested_tags.add(t)
            elif t:
                return {
                    "result": None,
                    "error": f"Unknown tag '{t}'. Valid tags: {', '.join(sorted(valid_tags))}",
                }

    all_tools = _discover_tools()
    results = []

    for tool in all_tools:
        # Module filter
        if module_filter and tool["module"] != module_filter:
            continue

        # Tag filter
        if requested_tags and not requested_tags.issubset(set(tool["tags"])):
            continue

        # Keyword filter (name + first line of description)
        if query:
            search_text = tool["name"] + " " + tool["description"]
            if query not in search_text.lower():
                continue

        results.append({
            "name": tool["name"],
            "module": tool["module"],
            "submodule": tool["submodule"],
            "connectors": tool["connectors"],
            "tags": tool["tags"],
            "description": tool["description"].split("\n")[0],  # first line only
        })

    # Build tag summary across all results
    tag_counts: dict[str, int] = {}
    for r in results:
        for tag in r["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return {
        "result": {
            "total": len(results),
            "filters": {k: v for k, v in {
                "query": query or None,
                "tags": list(requested_tags) or None,
                "module": module_filter or None,
            }.items() if v},
            "tag_summary": tag_counts,
            "tools": results,
        },
        "error": None,
    }
