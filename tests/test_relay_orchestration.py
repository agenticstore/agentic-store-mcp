"""Regression coverage for Relay's isolated handoff and dashboard startup rules."""

import asyncio
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
APP_FILE = ROOT / "agentic_store_mcp/webapp/app.py"
RUN_FILE = ROOT / "agentic_store_mcp/webapp/run.py"
HANDLER_FILE = ROOT / "agentic_store_mcp/modules/tools/task_board/handler.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def git(directory: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(repository)], check=True
    )
    (repository / "README.md").write_text("source\n", encoding="utf-8")
    git(repository, "add", "README.md")
    git(
        repository,
        "-c",
        "user.name=Relay Test",
        "-c",
        "user.email=relay@example.test",
        "commit",
        "-m",
        "Initial baseline",
    )
    return repository


def test_occupied_relay_port_offers_reuse_instead_of_stopping_a_process(monkeypatch):
    run = load_module("relay_run_reuse", RUN_FILE)
    monkeypatch.setattr(run, "_port_available", lambda host, port: False)
    monkeypatch.setattr(
        run, "_relay_session_url", lambda host, port: "http://127.0.0.1:8765"
    )

    with pytest.raises(SystemExit, match="Reuse that shared UI"):
        run._select_port("127.0.0.1", 8765, auto_port=False)


def test_auto_port_uses_a_separate_port_only_when_requested(monkeypatch):
    run = load_module("relay_run_auto_port", RUN_FILE)
    monkeypatch.setattr(run, "_port_available", lambda host, port: False)
    monkeypatch.setattr(
        run, "_relay_session_url", lambda host, port: "http://127.0.0.1:8765"
    )
    monkeypatch.setattr(run, "_find_available_port", lambda host: 48765)

    assert run._select_port("127.0.0.1", 8765, auto_port=True) == 48765


def test_local_handoff_creates_isolated_worktree_and_records_baseline(
    tmp_path, monkeypatch
):
    app = load_module("relay_app_handoff", APP_FILE)
    handler = load_module("relay_handler_handoff", HANDLER_FILE)
    control_dir = tmp_path / "relay-control"
    board_path = control_dir / "agent-board.json"
    repository = create_repository(tmp_path)
    baseline = git(repository, "rev-parse", "main")
    monkeypatch.setattr(app, "CONTROL_PLANE_DIR", control_dir)
    monkeypatch.setattr(app, "CONTROL_BOARD_PATH", board_path)
    monkeypatch.setattr(app.shutil, "which", lambda client: f"/mock/bin/{client}")

    workspace = handler.run(
        {
            "action": "add_workspace",
            "path": str(board_path),
            "workspace": {
                "name": "Local source",
                "source": "local",
                "local_directory": str(repository),
            },
            "confirm_write": True,
        }
    )["workspace"]
    ticket = handler.run(
        {
            "action": "add",
            "path": str(board_path),
            "task": {"title": "Isolate a handoff", "workspace_id": workspace["id"]},
            "confirm_write": True,
        }
    )["task"]

    request = app.LaunchHandoffRequest(
        ticket_id=ticket["id"], recipient="codex-agent", client="codex"
    )
    try:
        with patch.object(app, "_open_terminal") as process:
            result = asyncio.run(app.api_control_launch_handoff(request))

        process.assert_called_once()
        working_directory = Path(result["working_directory"])
        assert working_directory != repository
        assert working_directory.is_dir()
        assert result["workspace_source"] == "local_worktree"
        assert result["branch"].startswith(f"feature/{ticket['id']}-")
        assert result["base_commit"] == baseline
        assert git(working_directory, "branch", "--show-current") == result["branch"]

        recorded = handler.run(
            {"action": "get", "path": str(board_path), "id": ticket["id"]}
        )["task"]
        assert recorded["handoffs"][-1]["working_directory"] == str(working_directory)
        assert recorded["git_evidence"][-1]["base_ref"] == baseline
        assert recorded["git_evidence"][-1]["branch"] == result["branch"]
    finally:
        if "working_directory" in locals() and working_directory.exists():
            subprocess.run(
                [
                    "git", "-C", str(repository), "worktree", "remove", "--force",
                    str(working_directory),
                ],
                check=True,
            )
