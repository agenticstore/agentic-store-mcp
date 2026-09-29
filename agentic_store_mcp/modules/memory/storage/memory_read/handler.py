"""memory_read — retrieve facts from agent memory."""
from __future__ import annotations


def run(params: dict) -> dict:
    key = (params.get("key") or "").strip()
    category = (params.get("category") or "facts").strip()

    try:
        from agentic_store_mcp.memory_store import read_fact, list_facts

        if key:
            fact = read_fact(key)
            if fact is None:
                return {"result": None, "error": f"No fact found for key: {key!r}"}
            return {"result": fact, "error": None}

        facts = list_facts(category)
        return {
            "result": {
                "total": len(facts),
                "category": category if category != "facts" else None,
                "facts": facts,
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
