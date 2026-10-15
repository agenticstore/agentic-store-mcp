import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("file_diff_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_returns_unified_diff(tmp_path):
    left, right = tmp_path / "left.txt", tmp_path / "right.txt"
    left.write_text("one\ntwo\n")
    right.write_text("one\nthree\n")
    result = load().run({"left_path": str(left), "right_path": str(right)})
    assert result["error"] is None
    assert "-two" in result["result"]["diff"]
    assert "+three" in result["result"]["diff"]
