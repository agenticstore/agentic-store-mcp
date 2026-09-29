"""update_change_log — append a formatted entry to the project changelog."""
from __future__ import annotations

from datetime import datetime, timezone

_TYPE_EMOJI = {
    "feat": "✨",
    "fix": "🐛",
    "refactor": "♻️",
    "docs": "📝",
    "test": "🧪",
    "chore": "🔧",
    "breaking": "💥",
}

_VALID_TYPES = set(_TYPE_EMOJI.keys())


def run(params: dict) -> dict:
    description = (params.get("description") or "").strip()
    change_type = (params.get("change_type") or "").strip().lower()
    version = (params.get("version") or "").strip()
    scope = (params.get("scope") or "").strip()

    if not description:
        return {"result": None, "error": "description is required"}
    if not change_type:
        return {"result": None, "error": "change_type is required"}
    if change_type not in _VALID_TYPES:
        return {"result": None, "error": f"Invalid change_type '{change_type}'. Valid: {sorted(_VALID_TYPES)}"}

    try:
        from agentic_store_mcp.memory_store import (
            read_project_file, write_project_file, append_log,
        )

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        emoji = _TYPE_EMOJI[change_type]
        scope_tag = f"**{scope}**" if scope else ""
        entry_line = f"- {emoji} `{change_type}`{': ' + scope_tag if scope_tag else ''}: {description}"

        existing = read_project_file("CHANGELOG.md")

        if version:
            # Look for an existing version header to append under
            version_header = f"## {version}"
            if version_header in existing:
                # Insert entry after the version header line
                idx = existing.index(version_header) + len(version_header)
                # Find next newline after header
                nl = existing.find("\n", idx)
                if nl == -1:
                    updated = existing + f"\n{entry_line}\n"
                else:
                    updated = existing[:nl + 1] + entry_line + "\n" + existing[nl + 1:]
            else:
                # Prepend a new version section after the H1 title
                section = f"\n## {version} — {date_str}\n{entry_line}\n"
                lines = existing.splitlines(keepends=True)
                insert_at = 1  # after H1
                for i, line in enumerate(lines):
                    if line.startswith("## "):
                        insert_at = i
                        break
                lines.insert(insert_at, section)
                updated = "".join(lines)
        else:
            # Prepend under an Unreleased section
            unreleased_header = "## Unreleased"
            if unreleased_header in existing:
                idx = existing.index(unreleased_header) + len(unreleased_header)
                nl = existing.find("\n", idx)
                if nl == -1:
                    updated = existing + f"\n{entry_line}\n"
                else:
                    updated = existing[:nl + 1] + entry_line + "\n" + existing[nl + 1:]
            else:
                section = f"\n## Unreleased\n{entry_line}\n"
                lines = existing.splitlines(keepends=True)
                insert_at = 1
                for i, line in enumerate(lines):
                    if line.startswith("## "):
                        insert_at = i
                        break
                lines.insert(insert_at, section)
                updated = "".join(lines)

        write_project_file("CHANGELOG.md", updated)
        append_log({"event": "changelog_updated", "type": change_type, "version": version or None})

        return {
            "result": {
                "status": "logged",
                "change_type": change_type,
                "version": version or "Unreleased",
                "entry": entry_line,
                "recorded_at": now.isoformat(),
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
