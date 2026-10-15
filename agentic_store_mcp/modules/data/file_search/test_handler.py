import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("file_search_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finds_literal_query(tmp_path):
    (tmp_path / "app.py").write_text("TOKEN = 'value'\n")
    result = load().run({"path": str(tmp_path), "query": "token", "file_extensions": [".py"]})
    assert result["error"] is None
    assert result["result"]["match_count"] == 1
    assert result["result"]["matches"][0]["line"] == 1
