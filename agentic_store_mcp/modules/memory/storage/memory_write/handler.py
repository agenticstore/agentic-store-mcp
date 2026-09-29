"""memory_write — persist a key-value fact to agent memory."""
from __future__ import annotations
from typing import Any


def run(params: dict) -> dict:
    key = params.get("key", "").strip()
    if not key:
        return {"result": None, "error": "key is required"}

    value: Any = params.get("value")
    if value is None:
        return {"result": None, "error": "value is required"}

    category = params.get("category", "facts")

    try:
        from agentic_store_mcp.memory_store import write_fact, read_fact
        write_fact(key, value, category)
        stored = read_fact(key)
        return {
            "result": {
                "status": "written",
                "key": key,
                "category": category,
                "updated_at": stored["updated_at"] if stored else None,
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
