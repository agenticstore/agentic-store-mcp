"""memory_log — append to or read from the agent session log."""
from __future__ import annotations


def run(params: dict) -> dict:
    mode = (params.get("mode") or "append").strip().lower()

    try:
        if mode == "read":
            from agentic_store_mcp.memory_store import read_logs
            limit = int(params.get("limit") or 20)
            entries = read_logs(limit)
            return {
                "result": {"total": len(entries), "entries": entries},
                "error": None,
            }

        if mode == "append":
            from agentic_store_mcp.memory_store import append_log
            event = (params.get("event") or "").strip()
            if not event:
                return {"result": None, "error": "event is required when mode=append"}
            entry: dict = {"event": event}
            if params.get("detail"):
                entry["detail"] = params["detail"]
            if params.get("data"):
                entry["data"] = params["data"]
            append_log(entry)
            return {"result": {"status": "logged", "event": event}, "error": None}

        return {"result": None, "error": f"Unknown mode: {mode!r}. Use 'append' or 'read'."}
    except Exception as e:
        return {"result": None, "error": str(e)}
