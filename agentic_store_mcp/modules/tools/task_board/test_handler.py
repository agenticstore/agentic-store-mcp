"""Tests for Relay task_board state and planner audit actions."""

import importlib.util
from pathlib import Path

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("relay_task_board_handler", HANDLER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_planner_session_is_scoped_and_audited(tmp_path):
    handler = load_handler()
    board_path = tmp_path / "relay.json"

    first = handler.run(
        {
            "action": "add_board",
            "path": str(board_path),
            "board": {"name": "First initiative"},
            "confirm_write": True,
        }
    )["board"]
    second = handler.run(
        {
            "action": "add_board",
            "path": str(board_path),
            "board": {"name": "Second initiative"},
            "confirm_write": True,
        }
    )["board"]

    recorded = handler.run(
        {
            "action": "log_planning_session",
            "path": str(board_path),
            "board_id": second["id"],
            "planning_brief": (
                "Build a testable release dashboard with clear ownership."
            ),
            "agent_client": "codex",
            "session_id": "planner-codex-test",
            "confirm_write": True,
        }
    )

    assert recorded["planning_session"]["board_id"] == second["id"]
    summary = handler.run(
        {"action": "summary", "path": str(board_path), "board_id": second["id"]}
    )
    assert summary["recent_planning_sessions"][-1]["id"] == "planner-codex-test"
    assert summary["recent_planning_sessions"][-1]["agent_client"] == "codex"
    assert first["id"] != second["id"]


def test_plan_epic_creates_one_epic_and_children_once(tmp_path):
    handler = load_handler()
    board_path = tmp_path / "relay.json"

    result = handler.run(
        {
            "action": "plan_epic",
            "path": str(board_path),
            "epic": {"title": "Release readiness"},
            "children": [
                {"title": "Implement dashboard", "type": "feature"},
                {"title": "Add unit tests", "type": "task"},
                {"title": "Update documentation", "type": "task"},
            ],
            "confirm_write": True,
        }
    )

    assert result["total"] == 4
    listing = handler.run({"action": "list", "path": str(board_path)})
    assert len(listing["tasks"]) == 4
    epic = next(ticket for ticket in listing["tasks"] if ticket["type"] == "epic")
    children = [
        ticket for ticket in listing["tasks"] if ticket["parent_id"] == epic["id"]
    ]
    assert {ticket["title"] for ticket in children} == {
        "Implement dashboard",
        "Add unit tests",
        "Update documentation",
    }


def test_archive_status_is_available_and_excluded_from_active_work(tmp_path):
    handler = load_handler()
    board_path = tmp_path / "relay.json"
    task = handler.run(
        {
            "action": "add",
            "path": str(board_path),
            "task": {"title": "Old release notes"},
            "confirm_write": True,
        }
    )["task"]

    archived = handler.run(
        {
            "action": "archive",
            "path": str(board_path),
            "id": task["id"],
            "reason": "No longer active",
            "confirm_write": True,
        }
    )["task"]
    summary = handler.run({"action": "summary", "path": str(board_path)})

    assert archived["status"] == "archived"
    assert archived["history"][-1]["to"] == "archived"
    assert summary["by_status"]["archived"] == 1
    assert summary["active"] == 0
