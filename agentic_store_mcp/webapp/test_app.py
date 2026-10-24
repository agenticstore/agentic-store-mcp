"""Focused tests for Relay's local dashboard routes."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

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
