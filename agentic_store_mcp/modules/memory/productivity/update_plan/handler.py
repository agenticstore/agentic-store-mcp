"""update_plan — write or update the project plan document in agent memory."""
from __future__ import annotations

from datetime import datetime, timezone


def run(params: dict) -> dict:
    content = params.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return {"result": None, "error": "content is required"}

    append = bool(params.get("append", False))

    try:
        from agentic_store_mcp.memory_store import (
            write_project_file, append_project_file, read_project_file, append_log,
        )

        if append:
            existing = read_project_file("plan.md")
            if existing and not existing.endswith("\n"):
                content = "\n" + content
            append_project_file("plan.md", content)
        else:
            write_project_file("plan.md", content)

        append_log({"event": "plan_updated", "mode": "append" if append else "replace"})

        updated = read_project_file("plan.md")
        return {
            "result": {
                "status": "updated",
                "mode": "append" if append else "replace",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "length": len(updated),
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
