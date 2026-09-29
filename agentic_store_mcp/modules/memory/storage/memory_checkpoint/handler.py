"""memory_checkpoint — save a named session snapshot."""
from __future__ import annotations


def run(params: dict) -> dict:
    task = (params.get("task") or "").strip()
    if not task:
        return {"result": None, "error": "task is required"}

    name = (params.get("name") or "").strip() or None

    data = {
        "task": task,
        "decisions": params.get("decisions") or [],
        "next_steps": params.get("next_steps") or [],
        "client": params.get("client") or "",
        "context": {
            "active_files": params.get("active_files") or [],
            "notes": params.get("notes") or "",
        },
    }

    try:
        from agentic_store_mcp.memory_store import save_checkpoint
        used_name = save_checkpoint(name, data)
        return {
            "result": {
                "status": "saved",
                "name": used_name,
                "task": task,
            },
            "error": None,
        }
    except ValueError as e:
        return {"result": None, "error": str(e)}
    except Exception as e:
        return {"result": None, "error": str(e)}
