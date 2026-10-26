"""Focused tests for Relay's local dashboard routes."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

APP_FILE = Path(__file__).parent / "app.py"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_app():
    spec = importlib.util.spec_from_file_location("relay_webapp", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_relay_window_title_matches_the_relay_brand() -> None:
    expected_title = "Relay- Agentic store"
    base_template = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    index_template = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")

    base_title = f"<title>{{% block title %}}{expected_title}{{% endblock %}}</title>"
    assert base_title in base_template
    assert f"{{% block title %}}{expected_title}{{% endblock %}}" in index_template


def test_relay_board_customizer_and_archive_controls_are_available_in_the_ui() -> None:
    index_template = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    app_script = (APP_FILE.parent / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="cp-customize-board"' in index_template
    assert 'id="cp-column-visibility-options"' in index_template
    assert 'data-cp-view="archived"' in index_template
    assert 'data-cp-action="archive_ticket"' in app_script
    assert 'Archive ticket' in app_script
    assert 'controlPlane.view === "archived"' in app_script
    assert 'task.status === "archived"' in app_script
    assert '["done", "Done"], ["archived", "Archived"]' in app_script
    assert 'CP_COLUMN_VISIBILITY_STORAGE_KEY' in app_script


def test_planner_launch_records_a_gated_local_session(tmp_path, monkeypatch):
    app = load_app()
    control_dir = tmp_path / "relay-control"
    monkeypatch.setattr(app, "CONTROL_PLANE_DIR", control_dir)
    monkeypatch.setattr(app, "CONTROL_BOARD_PATH", control_dir / "agent-board.json")
    monkeypatch.setattr(app.shutil, "which", lambda client: f"/mock/bin/{client}")

    request = app.LaunchPlannerRequest(
        goal="Plan a release dashboard with automated validation and clear ownership.",
        success_criteria="Operators can review release risk before deployment.",
        product_surfaces=["web application", "API"],
        quality_gates=["automated unit tests", "documentation and release notes"],
        client="codex",
    )
    with patch.object(app.subprocess, "Popen") as process:
        result = asyncio.run(app.api_control_launch_planner(request))

    assert result["launched"] is True
    assert result["session_id"].startswith("planner-codex-")
    assert "--no-daemon" in Path(result["script_path"]).read_text(encoding="utf-8")
    assert "do not write" in Path(result["harness_path"]).read_text(encoding="utf-8")
    process.assert_called_once()

    handler_spec = importlib.util.spec_from_file_location(
        "relay_board", Path(__file__).parents[1] / "modules/tools/task_board/handler.py"
    )
    handler = importlib.util.module_from_spec(handler_spec)
    assert handler_spec.loader
    handler_spec.loader.exec_module(handler)
    summary = handler.run(
        {"action": "summary", "path": str(control_dir / "agent-board.json")}
    )
    session = summary["recent_planning_sessions"][-1]
    assert session["agent_client"] == "codex"
    assert "release dashboard" in session["brief"]


def test_handoff_without_workspace_explains_how_to_fix_it(tmp_path, monkeypatch):
    app = load_app()
    control_dir = tmp_path / "relay-control"
    board_path = control_dir / "agent-board.json"
    monkeypatch.setattr(app, "CONTROL_PLANE_DIR", control_dir)
    monkeypatch.setattr(app, "CONTROL_BOARD_PATH", board_path)
    monkeypatch.setattr(app.shutil, "which", lambda client: f"/mock/bin/{client}")

    handler_spec = importlib.util.spec_from_file_location(
        "relay_board", Path(__file__).parents[1] / "modules/tools/task_board/handler.py"
    )
    handler = importlib.util.module_from_spec(handler_spec)
    assert handler_spec.loader
    handler_spec.loader.exec_module(handler)
    ticket = handler.run(
        {
            "action": "add",
            "path": str(board_path),
            "task": {"title": "Ticket without a workspace"},
            "confirm_write": True,
        }
    )["task"]

    request = app.LaunchHandoffRequest(
        ticket_id=ticket["id"], recipient="codex-agent", client="codex"
    )
    try:
        asyncio.run(app.api_control_launch_handoff(request))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == (
            "Assign a workspace to this ticket before launching a handoff"
        )
    else:
        raise AssertionError(
            "Expected a ticket without a workspace to reject the handoff"
        )
