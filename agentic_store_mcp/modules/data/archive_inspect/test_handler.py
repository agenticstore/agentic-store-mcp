import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("archive_inspect_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
import zipfile


def test_lists_zip_without_extracting(tmp_path):
    archive = tmp_path / "files.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("notes.txt", "hello")
    result = load().run({"path": str(archive)})
    assert result["error"] is None
    assert result["result"]["entries"][0]["path"] == "notes.txt"
