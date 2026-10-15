import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).parent / "handler.py"
    spec = importlib.util.spec_from_file_location("data_profile_handler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profiles_csv_and_email_category(tmp_path):
    data = tmp_path / "people.csv"
    data.write_text("name,email\nAda,ada@example.test\nGrace,\n")
    result = load().run({"path": str(data)})
    assert result["error"] is None
    assert result["result"]["rows_profiled"] == 2
    assert result["result"]["pii_categories"] == {"email": 1}
