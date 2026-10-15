import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("file_read_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_reads_requested_line_range(tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("one\ntwo\nthree\n")
    result = load().run({"path": str(file), "start_line": 2, "max_lines": 1})
    assert result["result"]["content"] == "two\n"
