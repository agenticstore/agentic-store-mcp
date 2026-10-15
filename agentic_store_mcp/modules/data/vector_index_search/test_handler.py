import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("vector_index_search_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_rejects_remote_embedding_endpoint(tmp_path):
    result = load().run({"action": "search", "index_path": str(tmp_path / "index.json"), "query": "hello", "endpoint": "https://example.com/embed"})
    assert "localhost" in result["error"]
