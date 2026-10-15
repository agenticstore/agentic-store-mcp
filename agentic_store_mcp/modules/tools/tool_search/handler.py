"""Ranked runtime discovery for AgenticStore MCP tools."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MODULES_DIR = Path(__file__).parent.parent.parent
_TOKEN = re.compile(r"[a-z0-9_]+")
WRITE_KEYWORDS = re.compile(r"\b(create|update|manage|write|open|push|commit|edit|delete|close|label|triage|transform)\b", re.I)
NETWORK_KEYWORDS = re.compile(r"\b(https?|url|remote|github|web|api|crawl|search engine)\b", re.I)
ALIASES = {
    "find": {"search", "scan", "inspect", "symbols"},
    "search": {"find", "semantic", "vector", "code", "file", "memory"},
    "semantic": {"vector", "embedding", "relevance", "search"},
    "database": {"sqlite", "sql", "query", "schema", "data"},
    "files": {"file", "read", "scan", "diff", "archive", "inspect"},
    "file": {"read", "scan", "diff", "archive", "inspect", "search"},
    "security": {"audit", "secret", "firewall", "scanner", "dependency"},
    "git": {"github", "commit", "repository", "pr"},
    "prompt": {"firewall", "redact", "audit", "recording"},
}
VALID_TAGS = {
    "api_required", "local_only", "network_access", "write_tool", "read_only",
    "requires_confirmation",
}


def _tokens(value: str) -> set[str]:
    normalized = value.lower().replace("_", " ").replace("-", " ").replace("/", " ")
    return set(_TOKEN.findall(normalized))


def _infer_tags(schema: dict[str, Any]) -> list[str]:
    connectors = schema.get("connectors", [])
    description = schema.get("description", "")
    properties = schema.get("inputSchema", {}).get("properties", {})
    tags = []
    if connectors:
        tags.append("api_required")
    if connectors or NETWORK_KEYWORDS.search(description):
        tags.append("network_access")
    else:
        tags.append("local_only")
    if "confirmed" in properties or "confirm_write" in properties:
        tags.extend(["requires_confirmation", "write_tool"])
    elif WRITE_KEYWORDS.search(description):
        tags.append("write_tool")
    else:
        tags.append("read_only")
    return tags


def _add_tool(tools: list[dict[str, Any]], tool_dir: Path, module: str, submodule: str | None) -> None:
    schema_path = tool_dir / "schema.json"
    if not schema_path.exists():
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not (tool_dir / "handler.py").exists():
        return
    input_schema = schema.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    tools.append({
        "name": schema.get("name") or tool_dir.name,
        "module": module,
        "submodule": submodule,
        "description": schema.get("description", ""),
        "connectors": schema.get("connectors", []),
        "tags": _infer_tags(schema),
        "required_inputs": input_schema.get("required", []),
        "input_names": sorted(properties),
    })


def _discover_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if not MODULES_DIR.exists():
        return tools
    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("."):
            continue
        for child_dir in sorted(module_dir.iterdir()):
            if not child_dir.is_dir() or child_dir.name.startswith("."):
                continue
            if (child_dir / "handler.py").exists():
                _add_tool(tools, child_dir, module_dir.name, None)
            else:
                for tool_dir in sorted(child_dir.iterdir()):
                    if tool_dir.is_dir() and (tool_dir / "handler.py").exists():
                        _add_tool(tools, tool_dir, module_dir.name, child_dir.name)
    return tools


def _expanded_query(query: str) -> set[str]:
    terms = _tokens(query)
    for term in tuple(terms):
        terms.update(ALIASES.get(term, set()))
    return terms


def _score(tool: dict[str, Any], raw_terms: set[str], expanded_terms: set[str]) -> tuple[int, list[str]]:
    name_terms = _tokens(tool["name"])
    description_terms = _tokens(tool["description"])
    metadata_terms = set(tool["tags"]) | set(tool["connectors"]) | {tool["module"], tool["submodule"] or ""}
    score, matched = 0, []
    for term in raw_terms:
        if term in name_terms:
            score += 12; matched.append(f"name:{term}")
        elif term in metadata_terms:
            score += 8; matched.append(f"capability:{term}")
        elif term in description_terms:
            score += 5; matched.append(f"description:{term}")
    for term in expanded_terms - raw_terms:
        if term in name_terms or term in description_terms or term in metadata_terms:
            score += 2; matched.append(f"related:{term}")
    return score, matched


def run(params: dict[str, Any]) -> dict[str, Any]:
    """Search tools with ranked natural-language matching and safety filters."""
    query = str(params.get("query") or "").strip()
    tags_param = str(params.get("tags") or "").strip().lower()
    module_filter = str(params.get("module") or "").strip().lower()
    submodule_filter = str(params.get("submodule") or "").strip().lower()
    connector_filter = str(params.get("connector") or "").strip().lower()
    max_results = max(1, min(int(params.get("max_results", 20)), 100))
    include_inputs = bool(params.get("include_inputs", False))
    requested_tags = {tag.strip() for tag in tags_param.split(",") if tag.strip()}
    unknown = requested_tags - VALID_TAGS
    if unknown:
        return {"result": None, "error": f"Unknown tag(s): {', '.join(sorted(unknown))}. Valid tags: {', '.join(sorted(VALID_TAGS))}"}

    all_tools = _discover_tools()
    modules = sorted({tool["module"] for tool in all_tools})
    if module_filter and module_filter not in modules:
        return {"result": None, "error": f"Unknown module '{module_filter}'. Valid modules: {', '.join(modules)}"}
    raw_terms, expanded_terms = _tokens(query), _expanded_query(query)
    ranked: list[dict[str, Any]] = []
    for tool in all_tools:
        if module_filter and tool["module"] != module_filter:
            continue
        if submodule_filter and tool["submodule"] != submodule_filter:
            continue
        if connector_filter and connector_filter not in {value.lower() for value in tool["connectors"]}:
            continue
        if requested_tags and not requested_tags.issubset(tool["tags"]):
            continue
        score, reasons = _score(tool, raw_terms, expanded_terms)
        if raw_terms and not reasons:
            continue
        ranked.append({**tool, "relevance_score": score, "match_reasons": reasons})
    ranked.sort(key=lambda item: (-item["relevance_score"], item["name"]))
    total = len(ranked)
    rendered = []
    for tool in ranked[:max_results]:
        item = {key: tool[key] for key in ("name", "module", "submodule", "connectors", "tags", "relevance_score", "match_reasons")}
        item["description"] = tool["description"].split("\n")[0]
        if include_inputs:
            item["required_inputs"] = tool["required_inputs"]
            item["input_names"] = tool["input_names"]
        rendered.append(item)
    tag_summary = {tag: sum(tag in tool["tags"] for tool in ranked) for tag in sorted(VALID_TAGS)}
    return {"result": {"total": total, "returned": len(rendered), "truncated": total > len(rendered),
            "available_modules": modules, "filters": {key: value for key, value in {
                "query": query or None, "tags": sorted(requested_tags) or None, "module": module_filter or None,
                "submodule": submodule_filter or None, "connector": connector_filter or None,
            }.items() if value}, "tag_summary": tag_summary, "tools": rendered}, "error": None}
