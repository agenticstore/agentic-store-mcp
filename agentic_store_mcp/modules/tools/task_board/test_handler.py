"""Tests for Relay task_board state and planner audit actions."""

import base64
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_git_evidence_records_the_last_commit_timestamp(tmp_path, monkeypatch):
    handler = load_handler()
    repository = tmp_path / "repository"
    repository.mkdir()
    output = {
        ("rev-parse", "--show-toplevel"): str(repository),
        ("branch", "--show-current"): "feature/example",
        ("rev-parse", "HEAD"): "c0ffee1234567890",
        ("log", "-1", "--format=%s"): "feat: record commit dates",
        ("log", "-1", "--format=%cI"): "2026-10-26T05:20:00+00:00",
        ("status", "--short"): "",
        ("diff", "--stat"): "",
        ("diff", "--name-only"): "",
    }

    def fake_run(command, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=f"{output[tuple(command[3:])]}\n")

    monkeypatch.setattr(handler.subprocess, "run", fake_run)

    evidence = handler._git_evidence(str(repository))

    assert evidence["branch"] == "feature/example"
    assert evidence["commit_at"] == "2026-10-26T05:20:00+00:00"


def test_ticket_file_round_trip_and_invalid_upload(tmp_path):
    handler = load_handler()
    board_path = tmp_path / "relay.json"
    created = handler.run({
        "action": "add",
        "path": str(board_path),
        "task": {"title": "Screenshot review"},
        "confirm_write": True,
    })
    ticket_id = created["task"]["id"]
    image = b"\x89PNG\r\n\x1a\nexample"
    uploaded = handler.run({
        "action": "attach_file", "path": str(board_path), "id": ticket_id,
        "file_name": "../screen.png",
        "data_base64": base64.b64encode(image).decode(),
        "confirm_write": True,
    })
    attachment = uploaded["attachment"]
    assert attachment["label"] == "screen.png"
    assert attachment["media_type"] == "image/png"
    assert Path(attachment["reference"]).read_bytes() == image
    fetched = handler.run({"action": "get", "path": str(board_path), "id": ticket_id})
    assert fetched["task"]["attachments"][-1]["id"] == attachment["id"]
    read = handler.run({
        "action": "read_attachment", "path": str(board_path), "id": ticket_id,
        "attachment_id": attachment["id"],
    })
    assert base64.b64decode(read["data_base64"]) == image

    with pytest.raises(ValueError, match="base64"):
        handler.run({
            "action": "attach_file", "path": str(board_path), "id": ticket_id,
            "file_name": "bad.txt", "data_base64": "!!!", "confirm_write": True,
        })
    with pytest.raises(ValueError, match="Unknown file attachment"):
        handler.run({
            "action": "read_attachment", "path": str(board_path), "id": ticket_id,
            "attachment_id": "not-here",
        })
