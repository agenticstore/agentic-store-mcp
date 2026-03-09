"""
discovery.py — builds the tool catalog by walking the modules/ directory.

Reads every schema.json (same 2-or-3-level logic as server.py and tool_search),
then enriches each tool with connector status from secrets.
"""
from __future__ import annotations

import json
from pathlib import Path

# modules/ is two levels up from this file:
#   webapp/ → agentic_store_mcp/ → project root → (but modules/ is in agentic_store_mcp/)
# Actually: webapp/ → agentic_store_mcp/ and modules/ is inside agentic_store_mcp/
MODULES_DIR = Path(__file__).parent.parent / "modules"


def _read_schema(schema_path: Path) -> dict | None:
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _discover_raw() -> list[dict]:
    """Walk modules/ and return raw tool descriptors."""
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
                schema = _read_schema(child_dir / "schema.json")
                if schema:
                    tools.append({
                        "module": slug,
                        "submodule": None,
                        "schema": schema,
                    })
            else:
                for tool_dir in sorted(child_dir.iterdir()):
                    if tool_dir.is_dir() and (tool_dir / "handler.py").exists():
                        schema = _read_schema(tool_dir / "schema.json")
                        if schema:
                            tools.append({
                                "module": slug,
                                "submodule": child_dir.name,
                                "schema": schema,
                            })
    return tools


def build_catalog() -> list[dict]:
    """
    Return tool catalog with connector status.

    Each entry:
    {
        name, description, module, submodule,
        connectors: [slug, ...],
        connector_status: {slug: bool (has_token)},
    }
    """
    from agentic_store_mcp.secrets import get_token
    from agentic_store_mcp.connectors import REGISTRY

    tools = []
    for raw in _discover_raw():
        schema = raw["schema"]
        name = schema.get("name") or ""
        description = schema.get("description", "")
        connector_slugs = schema.get("connectors", [])

        # Check token presence for each declared connector
        connector_status: dict[str, bool] = {}
        for slug in connector_slugs:
            c = REGISTRY.get(slug)
            if c and c.fields:
                service_key = f"{slug}_{c.fields[0].name}"
                connector_status[slug] = get_token(service_key) is not None
            else:
                connector_status[slug] = False

        tools.append({
            "name": name,
            "description": description.split("\n")[0],  # first line only
            "module": raw["module"],
            "submodule": raw["submodule"],
            "connectors": connector_slugs,
            "connector_status": connector_status,
        })

    return tools


def list_modules() -> list[str]:
    """Return unique top-level module names."""
    seen = set()
    result = []
    for t in _discover_raw():
        m = t["module"]
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result
