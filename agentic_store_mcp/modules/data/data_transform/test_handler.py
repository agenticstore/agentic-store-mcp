import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("data_transform_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_requires_confirmation_and_writes_new_file(tmp_path):
    source, output = tmp_path / "data.csv", tmp_path / "data.jsonl"
    source.write_text("name\nAda\n")
    handler = load()
    blocked = handler.run({"input_path": str(source), "output_path": str(output), "operation": "csv_to_jsonl"})
    written = handler.run({"input_path": str(source), "output_path": str(output), "operation": "csv_to_jsonl", "confirmed": True})
    assert "confirmed=true" in blocked["error"]
    assert written["result"]["rows_written"] == 1
    assert output.read_text() == '{"name": "Ada"}\n'
