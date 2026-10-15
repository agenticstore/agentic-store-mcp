import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("semantic_search_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_ranks_relevant_file(tmp_path):
    (tmp_path / "auth.md").write_text("OAuth identity token refresh flow")
    (tmp_path / "colors.md").write_text("blue green red")
    result = load().run({"path": str(tmp_path), "query": "identity token"})
    assert result["result"]["matches"][0]["path"].endswith("auth.md")
