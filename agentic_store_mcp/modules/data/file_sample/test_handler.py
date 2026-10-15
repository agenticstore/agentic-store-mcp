import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("file_sample_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_seeded_sample_is_repeatable(tmp_path):
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text(name)
    params = {"path": str(tmp_path), "count": 2, "seed": "stable"}
    assert load().run(params)["result"]["files"] == load().run(params)["result"]["files"]
