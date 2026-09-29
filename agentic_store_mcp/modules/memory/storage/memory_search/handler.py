"""memory_search — full-text search across all memory sources."""
from __future__ import annotations


def run(params: dict) -> dict:
    query = (params.get("query") or "").strip()
    if not query:
        return {"result": None, "error": "query is required"}

    try:
        from agentic_store_mcp.memory_store import search_all
        results = search_all(query)
        return {
            "result": {
                "query": query,
                "total": len(results),
                "results": results,
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
