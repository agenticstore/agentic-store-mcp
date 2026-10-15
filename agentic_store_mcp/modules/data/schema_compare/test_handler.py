import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("schema_compare_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reports_schema_difference(tmp_path):
    left, right = tmp_path / "left.csv", tmp_path / "right.csv"
    left.write_text("id,name\n1,Ada\n")
    right.write_text("id,email\n1,ada@example.test\n")
    result = load().run({"left_path": str(left), "right_path": str(right)})
    assert result["error"] is None
    assert result["result"]["left_only"] == ["name"]
    assert result["result"]["right_only"] == ["email"]
