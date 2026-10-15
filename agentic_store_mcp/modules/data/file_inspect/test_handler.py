import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("file_inspect_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspects_text_file(tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("one\ntwo\n")
    result = load().run({"path": str(file)})
    assert result["error"] is None
    assert result["result"]["kind"] == "text"
    assert result["result"]["line_count"] == 2
    assert len(result["result"]["sha256"]) == 64
