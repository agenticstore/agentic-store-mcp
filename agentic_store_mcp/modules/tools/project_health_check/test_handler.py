import importlib.util
import json
from pathlib import Path


HANDLER = Path(__file__).parent / "handler.py"


def load():
    spec = importlib.util.spec_from_file_location("project_health_check_handler", HANDLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_detects_python_node_and_declared_commands(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (tmp_path / "uv.lock").write_text("version = 1\n")
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest", "lint": "eslint"}}))

    result = load().run({"path": str(tmp_path), "include_runtime_versions": False})

    assert result["error"] is None
    assert result["result"]["stacks"] == ["python", "node"]
    assert result["result"]["declared_commands"]["node_scripts"]["test"] == "vitest"
    assert "uv run pytest" in result["result"]["declared_commands"]["recommended"]


def test_missing_directory_returns_actionable_error(tmp_path):
    result = load().run({"path": str(tmp_path / "missing")})
    assert result["result"] is None
    assert "Directory not found" in result["error"]
