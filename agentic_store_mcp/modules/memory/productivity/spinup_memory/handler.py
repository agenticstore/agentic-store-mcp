"""
spinup_memory — initialize centralized agent memory for a project.

Seeds project facts, creates a strategy template, and logs session start.
Safe to run multiple times (idempotent unless reset=True).
"""
from __future__ import annotations

from datetime import datetime, timezone


_STRATEGY_TEMPLATE = """\
# {project_name} — Agent Strategy

## Goals
{goals_block}

## Stack
{stack}

## Constraints
- (add project constraints here)

## Preferred Patterns
- (add patterns and conventions here)

## Notes
- (anything agents should know before starting work)
"""


def run(params: dict) -> dict:
    project_name = (params.get("project_name") or "").strip()
    if not project_name:
        return {"result": None, "error": "project_name is required"}

    description = (params.get("description") or "").strip()
    stack = (params.get("stack") or "").strip()
    goals = params.get("goals") or []
    reset = bool(params.get("reset", False))

    try:
        from agentic_store_mcp.memory_store import (
            write_fact, list_facts, append_log, write_strategy, read_strategy,
            write_project_file, read_project_file, MEMORY_DIR,
        )

        existing_facts = list_facts()
        is_new = len(existing_facts) == 0

        if reset or is_new:
            # Write core project facts
            now = datetime.now(timezone.utc).isoformat()
            write_fact("project_name", project_name, category="project")
            if description:
                write_fact("project_description", description, category="project")
            if stack:
                write_fact("project_stack", stack, category="project")
            if goals:
                write_fact("project_goals", goals, category="project")
            write_fact("memory_initialized_at", now, category="project")

            # Write strategy template (only if empty or reset)
            if reset or not read_strategy().strip():
                goals_block = "\n".join(f"- {g}" for g in goals) if goals else "- (define your goals here)"
                write_strategy(_STRATEGY_TEMPLATE.format(
                    project_name=project_name,
                    goals_block=goals_block,
                    stack=stack or "(not specified)",
                ))

            # Initialize plan and milestones stubs if missing
            if reset or not read_project_file("plan.md").strip():
                write_project_file("plan.md", f"# {project_name} — Plan\n\n(update with update_plan)\n")
            if reset or not read_project_file("milestones.md").strip():
                write_project_file("milestones.md", f"# {project_name} — Milestones\n\n(update with update_milestones)\n")
            if reset or not read_project_file("learnings.md").strip():
                write_project_file("learnings.md", f"# {project_name} — Learnings\n\n")
            if reset or not read_project_file("CHANGELOG.md").strip():
                write_project_file("CHANGELOG.md", f"# {project_name} — Changelog\n\n")

        # Always log the session start
        append_log({"event": "session_started", "project": project_name, "reset": reset})

        return {
            "result": {
                "status": "initialized" if (reset or is_new) else "already_exists",
                "project_name": project_name,
                "memory_dir": str(MEMORY_DIR),
                "reset": reset,
                "files": ["facts.json", "strategy.md", "plan.md", "milestones.md", "learnings.md", "CHANGELOG.md"],
                "tip": "Call restore_session to load full context at any time.",
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
