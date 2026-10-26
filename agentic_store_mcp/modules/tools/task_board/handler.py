"""Relay — a local project system of record for AI agent development."""

import json
import os
import subprocess
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = {
    "archived", "backlog", "blocked", "cancelled", "done", "in_progress",
    "in_review", "todo",
}
PRIORITIES = {"critical", "high", "medium", "low"}
TASK_TYPES = {"task", "bug", "feature", "research", "chore", "epic"}
LINK_TYPES = {"blocks", "blocked_by", "relates_to", "duplicates", "caused_by"}
WRITABLE_FIELDS = {
    "title", "description", "status", "priority", "type", "assignee", "labels",
    "parent_id", "sprint", "depends_on", "acceptance_criteria", "blockers", "artifacts",
    "assignee", "risk_level", "complexity", "workspace_id", "board_id",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _board_path(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path is required")
    path = Path(value).expanduser().resolve()
    if path.exists() and path.is_dir():
        raise ValueError("path must be a JSON file, not a directory")
    return path


def _new_delivery_board(name: str = "Delivery", board_id: str | None = None) -> dict[str, Any]:
    timestamp = _now()
    return {
        "id": board_id or uuid.uuid4().hex[:10],
        "name": name,
        "description": "The primary delivery board for this project.",
        "color": "violet",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _ensure_boards(board: dict[str, Any]) -> None:
    boards = board.get("boards")
    if not isinstance(boards, list) or not boards:
        project_name = str((board.get("project") or {}).get("name") or "").strip()
        board["boards"] = [_new_delivery_board(project_name or "Delivery", "default")]
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in board["boards"]:
        if not isinstance(item, dict):
            raise ValueError("boards must contain objects")
        board_id = item.get("id")
        name = item.get("name")
        if not isinstance(board_id, str) or not board_id or board_id in seen:
            raise ValueError("Each board must have a unique id")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each board must have a name")
        seen.add(board_id)
        normalized.append({
            "id": board_id,
            "name": name.strip(),
            "description": str(item.get("description") or "").strip(),
            "color": str(item.get("color") or "violet").strip() or "violet",
            "created_at": item.get("created_at") or _now(),
            "updated_at": item.get("updated_at") or _now(),
        })
    board["boards"] = normalized
    default_id = normalized[0]["id"]
    for task in board.get("tasks", []):
        task.setdefault("board_id", default_id)
        if task["board_id"] not in seen:
            task["board_id"] = default_id
    board["version"] = max(int(board.get("version", 1)), 4)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        board = {"version": 4, "tasks": [], "workspaces": [], "activity": [], "planning_sessions": [], "created_at": _now(), "updated_at": _now()}
        _ensure_boards(board)
        return board
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        board = {"version": 4, "tasks": [], "workspaces": [], "activity": [], "planning_sessions": [], "created_at": _now(), "updated_at": _now()}
        _ensure_boards(board)
        return board
    try:
        board = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Board file is not valid JSON: {exc.msg}") from exc
    if not isinstance(board, dict) or not isinstance(board.get("tasks", []), list):
        raise ValueError("Board file must be an object with a tasks list")
    board.setdefault("tasks", [])
    board.setdefault("workspaces", [])
    board.setdefault("activity", [])
    board.setdefault("planning_sessions", [])
    board.setdefault("created_at", _now())
    board.setdefault("updated_at", _now())
    _ensure_boards(board)
    return board


def _save(path: Path, board: dict[str, Any]) -> None:
    board["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _activity(board: dict[str, Any], action: str, task_id: str | None, detail: str) -> None:
    board["activity"].append({"at": _now(), "action": action, "task_id": task_id, "detail": detail})
    board["activity"] = board["activity"][-500:]


def _find(board: dict[str, Any], task_id: Any, board_id: str | None = None) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("id is required")
    task = next((item for item in board["tasks"] if item.get("id") == task_id), None)
    if not task:
        raise ValueError(f"Unknown task id: {task_id}")
    if board_id is not None and task.get("board_id") != board_id:
        raise ValueError("Ticket belongs to a different Relay board")
    return task


def _selected_board(board: dict[str, Any], value: Any = None) -> dict[str, Any]:
    board_id = value if isinstance(value, str) and value.strip() else board["boards"][0]["id"]
    selected = next((item for item in board["boards"] if item["id"] == board_id), None)
    if not selected:
        raise ValueError(f"Unknown board id: {board_id}")
    return selected


def _validate_choice(value: Any, allowed: set[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return value


def _normalise_task(raw: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("task must be an object")
    unknown = set(raw) - WRITABLE_FIELDS - {"id"}
    if unknown:
        raise ValueError(f"Unsupported task fields: {', '.join(sorted(unknown))}")
    task = dict(existing or {})
    task.update(raw)
    title = task.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("task title is required")
    task["title"] = title.strip()
    task["description"] = str(task.get("description", "")).strip()
    task["status"] = _validate_choice(task.get("status", "todo"), STATUSES, "status")
    task["priority"] = _validate_choice(task.get("priority", "medium"), PRIORITIES, "priority")
    task["type"] = _validate_choice(task.get("type", "task"), TASK_TYPES, "type")
    assignee = task.get("assignee")
    if assignee is not None and (not isinstance(assignee, str) or not assignee.strip()):
        raise ValueError("assignee must be a non-empty string when provided")
    task["assignee"] = assignee.strip() if isinstance(assignee, str) else None
    parent_id = task.get("parent_id")
    if parent_id is not None and (not isinstance(parent_id, str) or not parent_id.strip()):
        raise ValueError("parent_id must be a non-empty string when provided")
    task["parent_id"] = parent_id.strip() if isinstance(parent_id, str) else None
    sprint = task.get("sprint")
    if sprint is not None and (not isinstance(sprint, str) or not sprint.strip()):
        raise ValueError("sprint must be a non-empty string when provided")
    task["sprint"] = sprint.strip() if isinstance(sprint, str) else None
    for field in ("labels", "depends_on", "acceptance_criteria", "blockers", "artifacts"):
        task[field] = _as_string_list(task.get(field), field)
    task.setdefault("id", uuid.uuid4().hex[:10])
    workspace_id = task.get("workspace_id")
    if workspace_id is not None and (not isinstance(workspace_id, str) or not workspace_id.strip()):
        raise ValueError("workspace_id must be a non-empty string when provided")
    task["workspace_id"] = workspace_id.strip() if isinstance(workspace_id, str) else None
    board_id = task.get("board_id")
    if board_id is not None and (not isinstance(board_id, str) or not board_id.strip()):
        raise ValueError("board_id must be a non-empty string when provided")
    task["board_id"] = board_id.strip() if isinstance(board_id, str) else None
    task.setdefault("comments", [])
    task.setdefault("history", [])
    task.setdefault("agent_runs", [])
    task.setdefault("handoffs", [])
    task.setdefault("git_evidence", [])
    task.setdefault("validations", [])
    task.setdefault("attachments", [])
    task.setdefault("risk_level", "medium")
    task.setdefault("complexity", "medium")
    if task["risk_level"] not in {"low", "medium", "high", "critical"}:
        raise ValueError("risk_level must be low, medium, high, or critical")
    if task["complexity"] not in {"small", "medium", "large", "xl"}:
        raise ValueError("complexity must be small, medium, large, or xl")
    task.setdefault("claimed_by", None)
    task.setdefault("claimed_at", None)
    task.setdefault("last_activity_at", _now())
    task.setdefault("history", [])
    task.setdefault("issue_links", [])
    task.setdefault("created_at", _now())
    task["updated_at"] = _now()
    task["last_activity_at"] = task["updated_at"]
    return task


def _validate_graph(tasks: list[dict[str, Any]]) -> None:
    ids = {task["id"] for task in tasks}
    if len(ids) != len(tasks):
        raise ValueError("Task ids must be unique")
    by_id = {task["id"]: task for task in tasks}
    graph: dict[str, list[str]] = {}
    for task in tasks:
        if task.get("parent_id") and task["parent_id"] not in ids:
            raise ValueError(f"Task {task['id']} references unknown parent_id {task['parent_id']}")
        if task.get("parent_id") and by_id[task["parent_id"]].get("board_id") != task.get("board_id"):
            raise ValueError("Parent and child tickets must be on the same Relay board")
        dependencies = task.get("depends_on", [])
        unknown = set(dependencies) - ids
        if unknown:
            raise ValueError(f"Task {task['id']} references unknown dependencies: {', '.join(sorted(unknown))}")
        if task["id"] in dependencies:
            raise ValueError(f"Task {task['id']} cannot depend on itself")
        if any(by_id[dependency].get("board_id") != task.get("board_id") for dependency in dependencies):
            raise ValueError("Ticket dependencies must stay within the same Relay board")
        for link in task.get("issue_links", []):
            if not isinstance(link, dict) or link.get("task_id") not in ids:
                raise ValueError(f"Task {task['id']} contains an invalid issue link")
            if link["task_id"] == task["id"]:
                raise ValueError(f"Task {task['id']} cannot link to itself")
            if link.get("relationship") not in LINK_TYPES:
                raise ValueError(f"Task {task['id']} contains an invalid issue-link relationship")
        graph[task["id"]] = dependencies

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("Task dependencies cannot contain a cycle")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for task_id in graph:
        visit(task_id)


def _ready(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    if task["status"] not in {"backlog", "todo"} or task.get("blockers"):
        return False
    return all(by_id[dependency]["status"] == "done" for dependency in task.get("depends_on", []))


def _serialise_task(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = dict(task)
    result["ready"] = _ready(task, by_id)
    result["dependency_status"] = [
        {"id": dependency, "status": by_id[dependency]["status"], "title": by_id[dependency]["title"]}
        for dependency in task.get("depends_on", [])
    ]
    return result


def _filtered_tasks(board: dict[str, Any], filters: Any, board_id: str | None = None) -> list[dict[str, Any]]:
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        raise ValueError("filters must be an object")
    allowed = {"status", "priority", "assignee", "label", "parent_id", "sprint", "ready"}
    unknown = set(filters) - allowed
    if unknown:
        raise ValueError(f"Unsupported filters: {', '.join(sorted(unknown))}")
    by_id = {task["id"]: task for task in board["tasks"]}
    tasks = [task for task in board["tasks"] if board_id is None or task.get("board_id") == board_id]
    for field in ("status", "priority"):
        if field in filters:
            values = filters[field] if isinstance(filters[field], list) else [filters[field]]
            tasks = [task for task in tasks if task.get(field) in values]
    for field in ("assignee", "parent_id", "sprint"):
        if field in filters:
            tasks = [task for task in tasks if task.get(field) == filters[field]]
    if "label" in filters:
        tasks = [task for task in tasks if filters["label"] in task.get("labels", [])]
    if "ready" in filters:
        if not isinstance(filters["ready"], bool):
            raise ValueError("filters.ready must be boolean")
        tasks = [task for task in tasks if _ready(task, by_id) is filters["ready"]]
    return [_serialise_task(task, by_id) for task in tasks]


def _git_evidence(repo_path: Any, base_ref: Any = None) -> dict[str, Any]:
    if not isinstance(repo_path, str) or not repo_path.strip():
        raise ValueError("repo_path is required")
    repo = Path(repo_path).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError("repo_path must be an existing directory")

    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments], capture_output=True, text=True,
            timeout=8, check=False,
        )
        if result.returncode:
            return ""
        return result.stdout.strip()

    root = git("rev-parse", "--show-toplevel")
    if not root:
        raise ValueError("repo_path is not inside a Git repository")
    compare = str(base_ref).strip() if isinstance(base_ref, str) and base_ref.strip() else None
    diff_args = ["diff", "--stat"] + ([f"{compare}..HEAD"] if compare else [])
    files_args = ["diff", "--name-only"] + ([f"{compare}..HEAD"] if compare else [])
    return {
        "captured_at": _now(), "repository": root, "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"), "commit_subject": git("log", "-1", "--format=%s"),
        "commit_at": git("log", "-1", "--format=%cI"),
        "base_ref": compare, "working_tree": git("status", "--short")[:8000],
        "diff_stat": git(*diff_args)[:8000], "changed_files": git(*files_args).splitlines()[:200],
    }


def _touch(task: dict[str, Any]) -> None:
    task["updated_at"] = _now()
    task["last_activity_at"] = task["updated_at"]


def _workspace(board: dict[str, Any], workspace_id: Any) -> dict[str, Any]:
    if not isinstance(workspace_id, str) or not workspace_id:
        raise ValueError("workspace_id is required")
    item = next((entry for entry in board.get("workspaces", []) if entry["id"] == workspace_id), None)
    if not item:
        raise ValueError(f"Unknown workspace id: {workspace_id}")
    return item


def _workspace_snapshot(workspace: dict[str, Any]) -> dict[str, Any]:
    return {key: workspace.get(key) for key in ("id", "name", "source", "local_directory", "repository_url", "branch_rules")}


def _assign_workspace(board: dict[str, Any], task: dict[str, Any]) -> None:
    if task.get("workspace_id"):
        task["workspace_snapshot"] = _workspace_snapshot(_workspace(board, task["workspace_id"]))


def _summary(board: dict[str, Any], board_id: str | None = None) -> dict[str, Any]:
    by_id = {task["id"]: task for task in board["tasks"]}
    tasks = [task for task in board["tasks"] if board_id is None or task.get("board_id") == board_id]
    by_status = Counter(task["status"] for task in tasks)
    by_priority = Counter(task["priority"] for task in tasks)
    completed = by_status["done"]
    inactive_statuses = {"archived", "cancelled", "done"}
    active = sum(task["status"] not in inactive_statuses for task in tasks)
    blocked = [
        {"id": task["id"], "title": task["title"], "blockers": task.get("blockers", [])}
        for task in tasks if task["status"] == "blocked" or task.get("blockers")
    ]
    ready = [{"id": task["id"], "title": task["title"], "priority": task["priority"]} for task in tasks if _ready(task, by_id)]
    return {
        "read_only": True,
        "project": board.get("project"),
        "workspaces": board.get("workspaces", []),
        "boards": board.get("boards", []),
        "board_id": board_id,
        "total": len(tasks),
        "active": active,
        "completed": completed,
        "completion_percent": round((completed / len(tasks)) * 100, 1) if tasks else 0,
        "by_status": dict(by_status),
        "by_priority": dict(by_priority),
        "by_sprint": dict(Counter(task.get("sprint") or "unassigned" for task in tasks)),
        "ready": ready,
        "blocked": blocked,
        "unassigned": [{"id": task["id"], "title": task["title"]} for task in tasks if not task.get("assignee")],
        "claimed": sum(1 for task in tasks if task.get("claimed_by")),
        "recent_activity": board["activity"][-20:],
        "recent_planning_sessions": board.get("planning_sessions", [])[-10:],
    }


def run(args: dict[str, Any]) -> dict[str, Any]:
    path = _board_path(args.get("path"))
    action = args.get("action", "list")
    valid_actions = {"list", "get", "summary", "add", "update", "transition", "comment", "assign_sprint", "link_issue", "log_issue", "archive", "set_project", "claim_ticket", "release_ticket", "start_ticket", "complete_ticket", "review_ticket", "handoff_ticket", "attach_git_evidence", "record_validation", "attach_artifact", "create_from_finding", "plan_epic", "resume_ticket", "add_workspace", "update_workspace", "delete_workspace", "add_board", "update_board", "delete_board", "log_planning_session"}
    if action not in valid_actions:
        raise ValueError(f"action must be one of: {', '.join(sorted(valid_actions))}")
    board = _load(path)

    if action in {"add_board", "update_board", "delete_board"}:
        if args.get("confirm_write") is not True:
            raise ValueError("Set confirm_write=true to modify Relay")
        if action == "add_board":
            payload = args.get("board")
            if not isinstance(payload, dict):
                raise ValueError("board must be an object")
            unknown = set(payload) - {"name", "description", "color"}
            if unknown:
                raise ValueError(f"Unsupported board fields: {', '.join(sorted(unknown))}")
            name = payload.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("board.name is required")
            if any(item["name"].casefold() == name.strip().casefold() for item in board["boards"]):
                raise ValueError("A Relay board with that name already exists")
            item = _new_delivery_board(name.strip())
            item["description"] = str(payload.get("description") or "").strip()
            item["color"] = str(payload.get("color") or "violet").strip() or "violet"
            board["boards"].append(item)
            _activity(board, "board_added", None, item["name"])
            _save(path, board)
            return {"written": True, "path": str(path), "board": item, "boards": board["boards"]}
        selected = _selected_board(board, args.get("board_id"))
        if action == "update_board":
            payload = args.get("board")
            if not isinstance(payload, dict) or not payload:
                raise ValueError("board must be a non-empty object")
            unknown = set(payload) - {"name", "description", "color"}
            if unknown:
                raise ValueError(f"Unsupported board fields: {', '.join(sorted(unknown))}")
            if "name" in payload:
                name = payload["name"]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("board.name must be a non-empty string")
                if any(item["id"] != selected["id"] and item["name"].casefold() == name.strip().casefold() for item in board["boards"]):
                    raise ValueError("A Relay board with that name already exists")
                selected["name"] = name.strip()
            if "description" in payload:
                selected["description"] = str(payload["description"] or "").strip()
            if "color" in payload:
                selected["color"] = str(payload["color"] or "violet").strip() or "violet"
            selected["updated_at"] = _now()
            _activity(board, "board_updated", None, selected["name"])
            _save(path, board)
            return {"written": True, "path": str(path), "board": selected, "boards": board["boards"]}
        tickets = [item["id"] for item in board["tasks"] if item.get("board_id") == selected["id"]]
        if tickets:
            raise ValueError(f"Cannot delete a board with tickets or epics: {', '.join(tickets[:12])}")
        if len(board["boards"]) == 1:
            raise ValueError("Relay needs at least one board")
        board["boards"].remove(selected)
        _activity(board, "board_deleted", None, selected["name"])
        _save(path, board)
        return {"written": True, "path": str(path), "deleted_board": selected, "boards": board["boards"]}

    selected_board = _selected_board(board, args.get("board_id"))
    board_id = selected_board["id"]
    if action == "list":
        tasks = _filtered_tasks(board, args.get("filters"), board_id)
        return {"read_only": True, "project": board.get("project"), "workspaces": board.get("workspaces", []), "boards": board["boards"], "active_board": selected_board, "tasks": tasks, "total": len(tasks)}
    if action == "get":
        by_id = {task["id"]: task for task in board["tasks"]}
        task = _find(board, args.get("id"), board_id)
        return {"read_only": True, "project": board.get("project"), "boards": board["boards"], "active_board": selected_board, "task": _serialise_task(task, by_id)}
    if action == "summary":
        summary = _summary(board, board_id)
        summary.update({"boards": board["boards"], "active_board": selected_board})
        return summary
    if action == "review_ticket":
        task = _find(board, args.get("id"), board_id)
        missing = []
        if task.get("acceptance_criteria") and not task.get("validations"):
            missing.append("validation evidence for acceptance criteria")
        if task["status"] == "done" and not task.get("validations"):
            missing.append("completion validation")
        return {"read_only": True, "task": task, "review": {"ready_for_review": not missing and not task.get("blockers"), "missing": missing, "has_git_evidence": bool(task.get("git_evidence")), "has_handoff": bool(task.get("handoffs"))}}
    if action == "resume_ticket":
        task = _find(board, args.get("id"), board_id)
        return {"read_only": True, "ticket": _serialise_task(task, {item["id"]: item for item in board["tasks"]}), "resume_context": {"latest_handoff": task.get("handoffs", [])[-1:] , "latest_comments": task.get("comments", [])[-5:], "validations": task.get("validations", [])[-5:], "git_evidence": task.get("git_evidence", [])[-1:]}}

    if args.get("confirm_write") is not True:
        raise ValueError("Set confirm_write=true to modify Relay")

    if action == "add":
        task = _normalise_task({**args.get("task", {}), "board_id": board_id})
        _assign_workspace(board, task)
        board["tasks"].append(task)
        _validate_graph(board["tasks"])
        _activity(board, "task_added", task["id"], task["title"])
        result: dict[str, Any] = {"task": task}
    elif action == "update":
        task = _find(board, args.get("id"), board_id)
        changes = args.get("changes")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("changes must be a non-empty object")
        if "status" in changes:
            raise ValueError("Use action=transition to change status")
        if "board_id" in changes:
            raise ValueError("Tickets cannot be moved between Relay boards during update")
        index = board["tasks"].index(task)
        updated = _normalise_task(changes, existing=task)
        _assign_workspace(board, updated)
        board["tasks"][index] = updated
        _validate_graph(board["tasks"])
        _activity(board, "task_updated", updated["id"], ", ".join(sorted(changes)))
        result = {"task": updated}
    elif action == "transition":
        task = _find(board, args.get("id"), board_id)
        target = _validate_choice(args.get("status"), STATUSES, "status")
        if target == "done":
            incomplete = [dependency for dependency in task.get("depends_on", []) if _find(board, dependency)["status"] != "done"]
            if incomplete and args.get("allow_incomplete_dependencies") is not True:
                raise ValueError(f"Cannot mark done while dependencies are incomplete: {', '.join(incomplete)}")
        previous = task["status"]
        task["status"] = target
        task["updated_at"] = _now()
        task["history"].append({"at": _now(), "from": previous, "to": target, "reason": str(args.get("reason", "")).strip()})
        _activity(board, "task_transitioned", task["id"], f"{previous} -> {target}")
        result = {"task": task}
    elif action == "comment":
        task = _find(board, args.get("id"), board_id)
        comment = args.get("comment")
        if not isinstance(comment, str) or not comment.strip():
            raise ValueError("comment must be a non-empty string")
        task["comments"].append({"at": _now(), "body": comment.strip()})
        task["updated_at"] = _now()
        _activity(board, "comment_added", task["id"], comment.strip()[:120])
        result = {"task": task}
    elif action == "assign_sprint":
        task = _find(board, args.get("id"), board_id)
        sprint = args.get("sprint")
        if not isinstance(sprint, str) or not sprint.strip():
            raise ValueError("sprint must be a non-empty string")
        task["sprint"] = sprint.strip()
        task["updated_at"] = _now()
        _activity(board, "sprint_assigned", task["id"], task["sprint"])
        result = {"task": task}
    elif action == "link_issue":
        task = _find(board, args.get("id"), board_id)
        related = _find(board, args.get("related_id"), board_id)
        relationship = _validate_choice(args.get("relationship", "relates_to"), LINK_TYPES, "relationship")
        if related["id"] == task["id"]:
            raise ValueError("A ticket cannot link to itself")
        if related.get("board_id") != task.get("board_id"):
            raise ValueError("Linked tickets must stay on the same Relay board")
        link = {"task_id": related["id"], "relationship": relationship, "linked_at": _now()}
        if link not in task["issue_links"]:
            task["issue_links"].append(link)
        task["updated_at"] = _now()
        _validate_graph(board["tasks"])
        _activity(board, "issue_linked", task["id"], f"{relationship}: {related['id']}")
        result = {"task": task, "linked_issue": {"id": related["id"], "title": related["title"]}}
    elif action == "log_issue":
        issue = args.get("issue")
        if not isinstance(issue, dict):
            raise ValueError("issue must be an object")
        issue_task = dict(issue)
        issue_task.setdefault("type", "bug")
        task = _normalise_task({**issue_task, "board_id": board_id})
        board["tasks"].append(task)
        _validate_graph(board["tasks"])
        _activity(board, "issue_logged", task["id"], task["title"])
        result = {"task": task, "issue_logged": True}
    elif action == "claim_ticket":
        task = _find(board, args.get("id"), board_id)
        agent = args.get("agent")
        if not isinstance(agent, str) or not agent.strip():
            raise ValueError("agent is required")
        if task.get("claimed_by") and task["claimed_by"] != agent.strip():
            raise ValueError(f"Ticket is already claimed by {task['claimed_by']}")
        task["claimed_by"] = agent.strip()
        task["claimed_at"] = _now()
        _touch(task)
        _activity(board, "ticket_claimed", task["id"], task["claimed_by"])
        result = {"task": task}
    elif action == "release_ticket":
        task = _find(board, args.get("id"), board_id)
        former = task.get("claimed_by")
        task["claimed_by"] = None
        task["claimed_at"] = None
        _touch(task)
        _activity(board, "ticket_released", task["id"], former or "unclaimed")
        result = {"task": task}
    elif action == "start_ticket":
        task = _find(board, args.get("id"), board_id)
        agent = args.get("agent")
        if not isinstance(agent, str) or not agent.strip():
            raise ValueError("agent is required")
        if not task.get("claimed_by"):
            task["claimed_by"], task["claimed_at"] = agent.strip(), _now()
        run_record = {"id": uuid.uuid4().hex[:10], "agent": agent.strip(), "started_at": _now(), "status": "running", "checkpoint": str(args.get("checkpoint", "")).strip() or None}
        task["agent_runs"].append(run_record)
        if task["status"] in {"backlog", "todo"}:
            task["status"] = "in_progress"
        _touch(task)
        _activity(board, "agent_run_started", task["id"], agent.strip())
        result = {"task": task, "agent_run": run_record}
    elif action == "complete_ticket":
        task = _find(board, args.get("id"), board_id)
        if task.get("acceptance_criteria") and not task.get("validations") and args.get("allow_unverified") is not True:
            raise ValueError("Record validation evidence or set allow_unverified=true before completion")
        previous = task["status"]
        task["status"] = "done"
        for run_record in task["agent_runs"]:
            if run_record.get("status") == "running":
                run_record["status"], run_record["completed_at"] = "completed", _now()
        task["history"].append({"at": _now(), "from": previous, "to": "done", "reason": str(args.get("reason", "")).strip()})
        _touch(task)
        _activity(board, "ticket_completed", task["id"], task["title"])
        result = {"task": task}
    elif action == "handoff_ticket":
        task = _find(board, args.get("id"), board_id)
        recipient, note = args.get("recipient"), args.get("note")
        if not isinstance(recipient, str) or not recipient.strip() or not isinstance(note, str) or not note.strip():
            raise ValueError("recipient and note are required")
        handoff = {"at": _now(), "from": task.get("claimed_by"), "to": recipient.strip(), "note": note.strip(), "blockers": _as_string_list(args.get("handoff_blockers"), "handoff_blockers"), "session_id": str(args.get("session_id", "")).strip() or None, "agent_client": str(args.get("agent_client", "")).strip() or None, "working_directory": str(args.get("working_directory", "")).strip() or None, "workspace_source": str(args.get("workspace_source", "")).strip() or None, "repository_url": str(args.get("repository_url", "")).strip() or None, "branch_rules": str(args.get("branch_rules", "")).strip() or None}
        task["handoffs"].append(handoff)
        task["claimed_by"], task["claimed_at"] = recipient.strip(), _now()
        if handoff["session_id"]:
            task["agent_runs"].append({"id": handoff["session_id"], "agent": recipient.strip(), "client": handoff["agent_client"], "started_at": _now(), "status": "launched", "working_directory": handoff["working_directory"], "workspace_source": handoff["workspace_source"], "repository_url": handoff["repository_url"]})
        _touch(task)
        _activity(board, "ticket_handed_off", task["id"], recipient.strip())
        result = {"task": task, "handoff": handoff}
    elif action == "attach_git_evidence":
        task = _find(board, args.get("id"), board_id)
        evidence = _git_evidence(args.get("repo_path"), args.get("base_ref"))
        task["git_evidence"].append(evidence)
        _touch(task)
        _activity(board, "git_evidence_attached", task["id"], evidence.get("branch") or "detached")
        result = {"task": task, "git_evidence": evidence}
    elif action == "record_validation":
        task = _find(board, args.get("id"), board_id)
        status = _validate_choice(args.get("validation_status"), {"passed", "failed", "skipped"}, "validation_status")
        kind, summary = args.get("validation_kind"), args.get("validation_summary")
        if not isinstance(kind, str) or not kind.strip() or not isinstance(summary, str) or not summary.strip():
            raise ValueError("validation_kind and validation_summary are required")
        validation = {"at": _now(), "kind": kind.strip(), "status": status, "summary": summary.strip(), "output": str(args.get("validation_output", ""))[:8000]}
        task["validations"].append(validation)
        _touch(task)
        _activity(board, "validation_recorded", task["id"], f"{kind}: {status}")
        result = {"task": task, "validation": validation}
    elif action == "attach_artifact":
        task = _find(board, args.get("id"), board_id)
        label, reference = args.get("artifact_label"), args.get("artifact_reference")
        if not isinstance(label, str) or not label.strip() or not isinstance(reference, str) or not reference.strip():
            raise ValueError("artifact_label and artifact_reference are required")
        artifact = {"at": _now(), "label": label.strip(), "reference": reference.strip()}
        task["attachments"].append(artifact)
        _touch(task)
        _activity(board, "artifact_attached", task["id"], label.strip())
        result = {"task": task, "artifact": artifact}
    elif action == "create_from_finding":
        source, title = args.get("source"), args.get("title")
        if not isinstance(source, str) or not source.strip() or not isinstance(title, str) or not title.strip():
            raise ValueError("source and title are required")
        task = _normalise_task({"title": title, "description": str(args.get("description", "")), "type": "bug", "priority": args.get("priority", "high"), "artifacts": [f"finding:{source.strip()}"], "board_id": board_id})
        board["tasks"].append(task)
        _activity(board, "finding_created_ticket", task["id"], source.strip())
        result = {"task": task, "source": source.strip()}
    elif action == "plan_epic":
        epic = _normalise_task({**(args.get("epic") if isinstance(args.get("epic"), dict) else {}), "type": "epic", "board_id": board_id})
        children = args.get("children")
        if not isinstance(children, list) or not children:
            raise ValueError("children must be a non-empty list")
        board["tasks"].append(epic)
        created = [epic]
        for child in children:
            child_task = _normalise_task({**child, "parent_id": epic["id"], "board_id": board_id})
            board["tasks"].append(child_task)
            created.append(child_task)
        _validate_graph(board["tasks"])
        _activity(board, "epic_planned", epic["id"], f"{len(children)} child tickets")
        result = {"epic": epic, "tickets": created}
    elif action in {"add_workspace", "update_workspace"}:
        workspace_data = args.get("workspace")
        if not isinstance(workspace_data, dict):
            raise ValueError("workspace must be an object")
        allowed = {"name", "source", "local_directory", "repository_url", "branch_rules"}
        unknown = set(workspace_data) - allowed
        if unknown:
            raise ValueError(f"Unsupported workspace fields: {', '.join(sorted(unknown))}")
        existing_workspace = _workspace(board, args.get("workspace_id")) if action == "update_workspace" else None
        name = workspace_data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("workspace.name is required")
        source = _validate_choice(workspace_data.get("source", "local"), {"local", "remote"}, "workspace.source")
        local_directory = str(workspace_data.get("local_directory") or "").strip() or None
        repository_url = str(workspace_data.get("repository_url") or "").strip() or None
        if source == "remote" and not repository_url:
            raise ValueError("workspace.repository_url is required for remote workspaces")
        if source == "local" and not local_directory and not repository_url:
            raise ValueError("a local directory or fallback repository URL is required")
        item = {
            "id": existing_workspace["id"] if existing_workspace else uuid.uuid4().hex[:10],
            "name": name.strip(), "source": source, "local_directory": local_directory,
            "repository_url": repository_url,
            "branch_rules": str(workspace_data.get("branch_rules") or "").strip() or None,
            "created_at": existing_workspace.get("created_at", _now()) if existing_workspace else _now(),
        }
        if existing_workspace:
            item["updated_at"] = _now()
            board["workspaces"][board["workspaces"].index(existing_workspace)] = item
            _activity(board, "workspace_updated", None, item["name"])
        else:
            board["workspaces"].append(item)
            _activity(board, "workspace_added", None, item["name"])
        result = {"workspace": item}
    elif action == "delete_workspace":
        workspace = _workspace(board, args.get("workspace_id"))
        open_tasks = [task["id"] for task in board["tasks"] if task.get("workspace_id") == workspace["id"] and task["status"] not in {"done", "cancelled"}]
        if open_tasks:
            raise ValueError(f"Cannot delete workspace with open tickets: {', '.join(open_tasks)}")
        board["workspaces"].remove(workspace)
        _activity(board, "workspace_deleted", None, workspace["name"])
        result = {"deleted_workspace": _workspace_snapshot(workspace)}
    elif action == "log_planning_session":
        brief = args.get("planning_brief")
        if not isinstance(brief, str) or not brief.strip():
            raise ValueError("planning_brief must be a non-empty string")
        client = str(args.get("agent_client") or "agent").strip() or "agent"
        session = {
            "id": str(args.get("session_id") or uuid.uuid4().hex[:12]).strip(),
            "at": _now(),
            "board_id": board_id,
            "agent_client": client,
            "brief": brief.strip()[:12000],
            "status": "launched",
        }
        board["planning_sessions"].append(session)
        board["planning_sessions"] = board["planning_sessions"][-100:]
        _activity(board, "planning_session_launched", None, brief.strip()[:120])
        result = {"planning_session": session}
    elif action == "archive":
        task = _find(board, args.get("id"), board_id)
        previous = task["status"]
        task["status"] = "archived"
        task["updated_at"] = _now()
        task["history"].append({
            "at": _now(), "from": previous, "to": "archived",
            "reason": str(args.get("reason", "")).strip(),
        })
        _activity(board, "task_archived", task["id"], task["title"])
        result = {"task": task}
    else:  # set_project
        project = args.get("project")
        if not isinstance(project, dict):
            raise ValueError("project must be an object")
        allowed = {"name", "description", "repository", "updated_by", "workspace_source", "local_directory", "remote_repository", "branch_rules"}
        unknown = set(project) - allowed
        if unknown:
            raise ValueError(f"Unsupported project fields: {', '.join(sorted(unknown))}")
        if "name" in project and (not isinstance(project["name"], str) or not project["name"].strip()):
            raise ValueError("project.name must be a non-empty string")
        board["project"] = {**board.get("project", {}), **project}
        _activity(board, "project_updated", None, board["project"].get("name", "project"))
        result = {"project": board["project"]}

    _save(path, board)
    return {"written": True, "path": str(path), "total": len(board["tasks"]), **result}
