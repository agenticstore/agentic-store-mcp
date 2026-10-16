"""Agent Board — a local, structured work tracker for AI agent development."""

import json
import os
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = {"backlog", "todo", "in_progress", "blocked", "in_review", "done", "cancelled"}
PRIORITIES = {"critical", "high", "medium", "low"}
TASK_TYPES = {"task", "bug", "feature", "research", "chore", "epic"}
LINK_TYPES = {"blocks", "blocked_by", "relates_to", "duplicates", "caused_by"}
WRITABLE_FIELDS = {
    "title", "description", "status", "priority", "type", "assignee", "labels",
    "parent_id", "sprint", "depends_on", "acceptance_criteria", "blockers", "artifacts",
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


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 2, "tasks": [], "activity": [], "created_at": _now(), "updated_at": _now()}
    try:
        board = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Board file is not valid JSON: {exc.msg}") from exc
    if not isinstance(board, dict) or not isinstance(board.get("tasks", []), list):
        raise ValueError("Board file must be an object with a tasks list")
    board.setdefault("version", 2)
    board.setdefault("tasks", [])
    board.setdefault("activity", [])
    board.setdefault("created_at", _now())
    board.setdefault("updated_at", _now())
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


def _find(board: dict[str, Any], task_id: Any) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("id is required")
    task = next((item for item in board["tasks"] if item.get("id") == task_id), None)
    if not task:
        raise ValueError(f"Unknown task id: {task_id}")
    return task


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
    task.setdefault("comments", [])
    task.setdefault("history", [])
    task.setdefault("issue_links", [])
    task.setdefault("created_at", _now())
    task["updated_at"] = _now()
    return task


def _validate_graph(tasks: list[dict[str, Any]]) -> None:
    ids = {task["id"] for task in tasks}
    if len(ids) != len(tasks):
        raise ValueError("Task ids must be unique")
    graph: dict[str, list[str]] = {}
    for task in tasks:
        if task.get("parent_id") and task["parent_id"] not in ids:
            raise ValueError(f"Task {task['id']} references unknown parent_id {task['parent_id']}")
        dependencies = task.get("depends_on", [])
        unknown = set(dependencies) - ids
        if unknown:
            raise ValueError(f"Task {task['id']} references unknown dependencies: {', '.join(sorted(unknown))}")
        if task["id"] in dependencies:
            raise ValueError(f"Task {task['id']} cannot depend on itself")
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


def _filtered_tasks(board: dict[str, Any], filters: Any) -> list[dict[str, Any]]:
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        raise ValueError("filters must be an object")
    allowed = {"status", "priority", "assignee", "label", "parent_id", "sprint", "ready"}
    unknown = set(filters) - allowed
    if unknown:
        raise ValueError(f"Unsupported filters: {', '.join(sorted(unknown))}")
    by_id = {task["id"]: task for task in board["tasks"]}
    tasks = board["tasks"]
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


def _summary(board: dict[str, Any]) -> dict[str, Any]:
    by_id = {task["id"]: task for task in board["tasks"]}
    tasks = board["tasks"]
    by_status = Counter(task["status"] for task in tasks)
    by_priority = Counter(task["priority"] for task in tasks)
    completed = by_status["done"]
    active = len([task for task in tasks if task["status"] not in {"done", "cancelled"}])
    blocked = [
        {"id": task["id"], "title": task["title"], "blockers": task.get("blockers", [])}
        for task in tasks if task["status"] == "blocked" or task.get("blockers")
    ]
    ready = [{"id": task["id"], "title": task["title"], "priority": task["priority"]} for task in tasks if _ready(task, by_id)]
    return {
        "read_only": True,
        "project": board.get("project"),
        "total": len(tasks),
        "active": active,
        "completed": completed,
        "completion_percent": round((completed / len(tasks)) * 100, 1) if tasks else 0,
        "by_status": dict(by_status),
        "by_priority": dict(by_priority),
        "by_sprint": dict(Counter(task.get("sprint") or "unassigned" for task in tasks)),
        "ready": ready,
        "blocked": blocked,
        "recent_activity": board["activity"][-20:],
    }


def run(args: dict[str, Any]) -> dict[str, Any]:
    path = _board_path(args.get("path"))
    action = args.get("action", "list")
    valid_actions = {"list", "get", "summary", "add", "update", "transition", "comment", "assign_sprint", "link_issue", "log_issue", "archive", "set_project"}
    if action not in valid_actions:
        raise ValueError(f"action must be one of: {', '.join(sorted(valid_actions))}")
    board = _load(path)

    if action == "list":
        tasks = _filtered_tasks(board, args.get("filters"))
        return {"read_only": True, "project": board.get("project"), "tasks": tasks, "total": len(tasks)}
    if action == "get":
        by_id = {task["id"]: task for task in board["tasks"]}
        task = _find(board, args.get("id"))
        return {"read_only": True, "project": board.get("project"), "task": _serialise_task(task, by_id)}
    if action == "summary":
        return _summary(board)

    if args.get("confirm_write") is not True:
        raise ValueError("Set confirm_write=true to modify Agent Board")

    if action == "add":
        task = _normalise_task(args.get("task", {}))
        board["tasks"].append(task)
        _validate_graph(board["tasks"])
        _activity(board, "task_added", task["id"], task["title"])
        result: dict[str, Any] = {"task": task}
    elif action == "update":
        task = _find(board, args.get("id"))
        changes = args.get("changes")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("changes must be a non-empty object")
        if "status" in changes:
            raise ValueError("Use action=transition to change status")
        index = board["tasks"].index(task)
        updated = _normalise_task(changes, existing=task)
        board["tasks"][index] = updated
        _validate_graph(board["tasks"])
        _activity(board, "task_updated", updated["id"], ", ".join(sorted(changes)))
        result = {"task": updated}
    elif action == "transition":
        task = _find(board, args.get("id"))
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
        task = _find(board, args.get("id"))
        comment = args.get("comment")
        if not isinstance(comment, str) or not comment.strip():
            raise ValueError("comment must be a non-empty string")
        task["comments"].append({"at": _now(), "body": comment.strip()})
        task["updated_at"] = _now()
        _activity(board, "comment_added", task["id"], comment.strip()[:120])
        result = {"task": task}
    elif action == "assign_sprint":
        task = _find(board, args.get("id"))
        sprint = args.get("sprint")
        if not isinstance(sprint, str) or not sprint.strip():
            raise ValueError("sprint must be a non-empty string")
        task["sprint"] = sprint.strip()
        task["updated_at"] = _now()
        _activity(board, "sprint_assigned", task["id"], task["sprint"])
        result = {"task": task}
    elif action == "link_issue":
        task = _find(board, args.get("id"))
        related = _find(board, args.get("related_id"))
        relationship = _validate_choice(args.get("relationship", "relates_to"), LINK_TYPES, "relationship")
        if related["id"] == task["id"]:
            raise ValueError("A ticket cannot link to itself")
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
        task = _normalise_task(issue_task)
        board["tasks"].append(task)
        _validate_graph(board["tasks"])
        _activity(board, "issue_logged", task["id"], task["title"])
        result = {"task": task, "issue_logged": True}
    elif action == "archive":
        task = _find(board, args.get("id"))
        previous = task["status"]
        task["status"] = "cancelled"
        task["updated_at"] = _now()
        task["history"].append({"at": _now(), "from": previous, "to": "cancelled", "reason": str(args.get("reason", "")).strip()})
        _activity(board, "task_archived", task["id"], task["title"])
        result = {"task": task}
    else:  # set_project
        project = args.get("project")
        if not isinstance(project, dict):
            raise ValueError("project must be an object")
        allowed = {"name", "description", "repository", "updated_by"}
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
