"""
update_milestones — update the milestones tracker in agent memory.

Two modes:
  - Full replace: provide content= to overwrite the entire milestones.md
  - Inline update: provide milestone= + status= to patch a specific line in-place
"""
from __future__ import annotations

import re
from datetime import datetime, timezone


def _patch_status(text: str, milestone: str, status: str, notes: str) -> tuple[str, bool]:
    """
    Find the first line containing `milestone` and replace its status marker.
    Returns (updated_text, was_found).
    Looks for patterns like: | Milestone | ... | OLD_STATUS |
    or lines like: ## M1: Milestone Name — **Status:** OLD
    Falls back to appending a note at the end of the matching section.
    """
    lines = text.splitlines(keepends=True)
    found = False

    # Strategy 1: markdown table row  |  name  |  ...  |  status  |
    for i, line in enumerate(lines):
        if milestone.lower() in line.lower() and "|" in line:
            # Replace last cell content (status column)
            parts = line.split("|")
            if len(parts) >= 4:
                parts[-2] = f" {status} "
                lines[i] = "|".join(parts)
                found = True
                if notes:
                    lines.insert(i + 1, f"| | | {notes} |\n")
                break

    # Strategy 2: heading line containing the milestone name
    if not found:
        for i, line in enumerate(lines):
            if milestone.lower() in line.lower() and line.startswith("#"):
                # Look ahead for a Status: line within next 5 lines
                for j in range(i + 1, min(i + 6, len(lines))):
                    if re.search(r"\*\*status\*\*|status:", lines[j], re.IGNORECASE):
                        lines[j] = re.sub(
                            r"(?i)(\*\*status\*\*:?\s*)(.+)",
                            lambda m: f"{m.group(1)}{status}",
                            lines[j],
                        )
                        found = True
                        if notes:
                            lines.insert(j + 1, f"> Note: {notes}\n")
                        break
                break

    return "".join(lines), found


def run(params: dict) -> dict:
    content = params.get("content")
    milestone = (params.get("milestone") or "").strip()
    status = (params.get("status") or "").strip()
    notes = (params.get("notes") or "").strip()

    if not content and not milestone:
        return {"result": None, "error": "Provide either content (full replace) or milestone + status (inline update)"}

    try:
        from agentic_store_mcp.memory_store import (
            write_project_file, read_project_file, append_log,
        )

        if content:
            # Full replace
            write_project_file("milestones.md", content)
            append_log({"event": "milestones_updated", "mode": "replace"})
            return {
                "result": {"status": "updated", "mode": "replace",
                           "updated_at": datetime.now(timezone.utc).isoformat()},
                "error": None,
            }

        # Inline patch
        if not status:
            return {"result": None, "error": "status is required when using milestone="}

        existing = read_project_file("milestones.md")
        if not existing.strip():
            return {"result": None, "error": "milestones.md is empty — use content= to create it first"}

        updated, found = _patch_status(existing, milestone, status, notes)

        if not found:
            # Append a note at the bottom
            suffix = f"\n\n## {milestone}\n**Status:** {status}\n"
            if notes:
                suffix += f"{notes}\n"
            updated = existing.rstrip() + suffix

        write_project_file("milestones.md", updated)
        append_log({"event": "milestone_updated", "milestone": milestone, "status": status})

        return {
            "result": {
                "status": "updated",
                "milestone": milestone,
                "new_status": status,
                "found_inline": found,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
