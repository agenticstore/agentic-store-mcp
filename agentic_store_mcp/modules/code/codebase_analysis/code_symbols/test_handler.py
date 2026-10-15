import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("code_symbols_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finds_python_symbols(tmp_path):
    (tmp_path / "app.py").write_text("class Service:\n    pass\n\ndef execute():\n    return 1\n")
    result = load().run({"path": str(tmp_path)})
    assert result["error"] is None
    assert {item["name"] for item in result["result"]["symbols"]} == {"Service", "execute"}
