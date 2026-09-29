"""update_learnings — append an insight or learning to the project learnings log."""
from __future__ import annotations

from datetime import datetime, timezone


def run(params: dict) -> dict:
    learning = (params.get("learning") or "").strip()
    if not learning:
        return {"result": None, "error": "learning is required"}

    category = (params.get("category") or "general").strip()
    source = (params.get("source") or "").strip()

    try:
        from agentic_store_mcp.memory_store import append_project_file, append_log

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        lines = [f"\n## [{category}] {date_str}\n", f"{learning}\n"]
        if source:
            lines.append(f"*Source: {source}*\n")

        append_project_file("learnings.md", "".join(lines))
        append_log({"event": "learning_added", "category": category, "source": source or None})

        return {
            "result": {
                "status": "added",
                "category": category,
                "learning": learning[:120] + ("…" if len(learning) > 120 else ""),
                "recorded_at": now.isoformat(),
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
