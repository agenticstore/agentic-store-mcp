"""memory_restore — load a saved checkpoint to restore session context."""
from __future__ import annotations


def run(params: dict) -> dict:
    name = (params.get("name") or "").strip()
    if not name:
        return {"result": None, "error": "name is required (use 'latest' for most recent)"}

    try:
        from agentic_store_mcp.memory_store import load_checkpoint, list_checkpoints
        data = load_checkpoint(name)
        if data is None:
            if name == "latest":
                return {"result": None, "error": "No checkpoints found"}
            return {"result": None, "error": f"Checkpoint not found: {name!r}"}

        checkpoints = list_checkpoints()
        return {
            "result": {
                "status": "restored",
                "checkpoint": data,
                "available_checkpoints": [c["name"] for c in checkpoints],
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
