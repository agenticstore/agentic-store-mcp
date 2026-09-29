"""
restore_session — load full agent session context in one call.

Returns checkpoint, plan, milestones, learnings, recent facts, recent logs,
and recent changelog — everything needed to resume work immediately.
"""
from __future__ import annotations

_ALL_SECTIONS = ("checkpoint", "plan", "milestones", "learnings", "facts", "logs", "changelog")


def run(params: dict) -> dict:
    checkpoint_name = (params.get("checkpoint") or "latest").strip()
    include_raw = params.get("include") or []
    include = set(include_raw) if include_raw else set(_ALL_SECTIONS)

    # Validate include values
    unknown = include - set(_ALL_SECTIONS)
    if unknown:
        return {"result": None, "error": f"Unknown include values: {sorted(unknown)}. Valid: {list(_ALL_SECTIONS)}"}

    try:
        from agentic_store_mcp.memory_store import (
            load_checkpoint, list_facts, read_logs,
            read_project_file, append_log,
        )

        context: dict = {}

        if "checkpoint" in include:
            cp = load_checkpoint(checkpoint_name)
            context["checkpoint"] = cp
            context["checkpoint_name"] = checkpoint_name if checkpoint_name != "latest" else (
                cp.get("name") if cp else None
            )

        if "plan" in include:
            context["plan"] = read_project_file("plan.md") or None

        if "milestones" in include:
            context["milestones"] = read_project_file("milestones.md") or None

        if "learnings" in include:
            raw = read_project_file("learnings.md")
            # Return last ~2000 chars to stay token-efficient
            context["learnings"] = ("…" + raw[-2000:]) if len(raw) > 2000 else (raw or None)

        if "changelog" in include:
            raw = read_project_file("CHANGELOG.md")
            context["changelog"] = ("…" + raw[-1500:]) if len(raw) > 1500 else (raw or None)

        if "facts" in include:
            facts = list_facts()
            context["facts"] = {f["key"]: f["value"] for f in facts}

        if "logs" in include:
            context["recent_logs"] = read_logs(limit=15)

        append_log({"event": "session_restored", "checkpoint": checkpoint_name})

        # Build a human-readable summary
        cp_task = None
        if context.get("checkpoint"):
            cp_task = context["checkpoint"].get("task")

        return {
            "result": {
                "restored": True,
                "summary": {
                    "checkpoint": context.get("checkpoint_name"),
                    "task": cp_task,
                    "next_steps": context.get("checkpoint", {}).get("next_steps") if context.get("checkpoint") else None,
                    "fact_count": len(context.get("facts", {})),
                },
                "context": context,
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
