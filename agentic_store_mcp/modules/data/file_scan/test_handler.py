import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("file_scan_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_inventories_files(tmp_path):
    (tmp_path / "one.py").write_text("x")
    result = load().run({"path": str(tmp_path)})
    assert result["result"]["file_count"] == 1
